"""
Multi-Agent LangGraph System
Orchestrates the full agent pipeline: profile loading, RAG retrieval,
LangGraph invocation, interaction logging, and streaming.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional, Tuple

from backend.config import config
from backend.langfuse_setup import create_trace, update_trace, traced_span

logger = logging.getLogger(__name__)


def run_agent_pipeline(
    query: str,
    user_id: str,
    session_id: Optional[str] = None,
    model_id: Optional[str] = None,
) -> Tuple[Generator[str, None, None], List[Dict[str, Any]]]:
    """Run the full multi-agent pipeline and return (stream_generator, sources).

    Steps:
        1. Load student profile (quiz_results + Neo4j)
        2. Run S3Retriever RAG to get context + sources
        3. Build AgentState and invoke the compiled LangGraph
        4. Log interaction to PostgreSQL
        5. Return a streaming generator with __AGENT_META__ prefix
    """
    start_time = time.time()

    # Root Langfuse trace for the entire agent pipeline
    main_trace = create_trace(
        "agent-pipeline",
        user_id=user_id,
        session_id=session_id,
        input={"query": query},
        tags=["agent", "langgraph"],
    )

    # ── 1. Student profile ────────────────────────────────────────
    from backend.agents.profile import load_student_profile

    with traced_span(main_trace, "load-student-profile", input={"user_id": user_id}) as profile_span:
        profile = load_student_profile(user_id)

    # ── 2. RAG retrieval (reuse existing S3/Chroma logic) ─────────
    retrieval_started_at = time.time()
    with traced_span(main_trace, "agent-rag-retrieval", input={"query": query}) as rag_span:
        context_str, sources = _retrieve_rag_context(query)
    retrieval_elapsed = time.time() - retrieval_started_at

    # ── 3. Build state + classify intent ─────────────────────────
    from backend.agents.state import AgentState
    from backend.agents.router import classify_query

    initial_state: AgentState = {
        "input": query,
        "user_id": user_id,
        "session_id": session_id or "",
        "model_id": model_id,
        # Profile fields
        "student_name": profile.get("display_name", user_id),
        "student_level": profile.get("performance_level", config.AGENT_DEFAULT_LEVEL),
        "top_topics": profile.get("top_topics", []),
        "weak_topics": profile.get("weak_topics", []),
        "struggled_concepts": profile.get("struggled_concepts", []),
        "recently_studied": profile.get("recently_studied", []),
        # RAG context
        "context_str": context_str,
        "retrieved_sources": sources,
        # Metadata
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "response": "",
        "agent": "",
    }

    # Run router synchronously — it's cheap (regex + optional embed) and
    # gives us the route before we start streaming.
    agent_name, route_reason = classify_query(query)
    # The router also logs to Neo4j as a side effect, but that's the LangGraph
    # node's responsibility; replicate it here since we're bypassing the graph.
    from backend.agents import graph_ops as _graph_ops
    _query_type_map = {
        "tutor_agent": "general_tutoring",
        "doubts_agent": "doubt_resolution",
        "personalised_agent": "personalised_explanation",
        "quiz_helper_agent": "quiz_help",
        "feedback_agent": "feedback",
    }
    query_type = _query_type_map.get(agent_name, "general_tutoring")
    _graph_ops.log_query(user_id, query, query_type)

    generation_started_at = time.time()

    # ── 4. Stream the chosen specialist's LLM tokens ─────────────
    from backend.agents.streaming import stream_agent_response, stream_agent_tokens
    from backend.agents.llm_utils import stream_complete_with_model_fallback

    # Mapping of agent -> (prepare_fn, finalize_fn). Feedback handled separately
    # because it doesn't call an LLM.
    if agent_name == "tutor_agent":
        from backend.agents.tutor_agent import prepare_tutor, finalize_tutor
        prep = prepare_tutor(initial_state)
        finalize = lambda txt: finalize_tutor(initial_state, txt)
    elif agent_name == "doubts_agent":
        from backend.agents.doubts_agent import prepare_doubts, finalize_doubts
        prep = prepare_doubts(initial_state)
        _concept = prep.pop("_concept")
        finalize = lambda txt: finalize_doubts(initial_state, txt, concept=_concept)
    elif agent_name == "personalised_agent":
        from backend.agents.personalised_agent import prepare_personalised, finalize_personalised
        prep = prepare_personalised(initial_state)
        finalize = lambda txt: finalize_personalised(initial_state, txt)
    elif agent_name == "quiz_helper_agent":
        from backend.agents.quiz_helper_agent import prepare_quiz_helper, finalize_quiz_helper
        prep = prepare_quiz_helper(initial_state)
        finalize = lambda txt: finalize_quiz_helper(initial_state, txt)
    else:
        prep = None
        finalize = None

    # ── 4a. Feedback agent: no LLM stream — use canned-text chunking ─
    if agent_name == "feedback_agent":
        from backend.agents.feedback_agent import feedback_agent as _feedback_node
        result = _feedback_node(initial_state)
        response_text = result.get("response", "")
        sentiment = result.get("sentiment")
        generation_elapsed = time.time() - generation_started_at
        elapsed_ms = int((time.time() - start_time) * 1000)

        _log_post_stream(
            main_trace=main_trace,
            user_id=user_id,
            session_id=session_id,
            query=query,
            response_text=response_text,
            agent_name=agent_name,
            route_reason=route_reason,
            query_type=query_type,
            sentiment=sentiment,
            model_id=model_id,
            elapsed_ms=elapsed_ms,
            retrieval_elapsed=retrieval_elapsed,
            generation_elapsed=generation_elapsed,
            sources=sources,
        )

        generator = stream_agent_response(
            response_text=response_text,
            agent_name=agent_name,
            route_reason=route_reason,
            extra_meta={"response_time_ms": elapsed_ms},
        )
        return generator, sources

    # ── 4b. LLM-backed agents: true token streaming ───────────────
    token_gen = stream_complete_with_model_fallback(
        prompt=prep["prompt"],
        logger=logger,
        model_id=prep["model_id"],
    )

    def _on_complete(full_response: str) -> None:
        if finalize is not None:
            try:
                finalize(full_response)
            except Exception as exc:
                logger.warning("Agent finalize hook failed: %s", exc)
        generation_elapsed_local = time.time() - generation_started_at
        elapsed_ms_local = int((time.time() - start_time) * 1000)
        _log_post_stream(
            main_trace=main_trace,
            user_id=user_id,
            session_id=session_id,
            query=query,
            response_text=full_response,
            agent_name=agent_name,
            route_reason=route_reason,
            query_type=query_type,
            sentiment=None,
            model_id=model_id,
            elapsed_ms=elapsed_ms_local,
            retrieval_elapsed=retrieval_elapsed,
            generation_elapsed=generation_elapsed_local,
            sources=sources,
        )

    def _on_error(exc: Exception) -> str:
        logger.error("LLM stream failed for %s: %s", agent_name, exc)
        return (
            "I'm sorry, I encountered an issue generating a response. "
            "Could you try rephrasing your question?"
        )

    generator = stream_agent_tokens(
        token_iter=token_gen,
        agent_name=agent_name,
        route_reason=route_reason,
        extra_meta={"streaming": True},
        on_complete=_on_complete,
        on_error=_on_error,
    )

    return generator, sources


def _log_post_stream(
    *,
    main_trace,
    user_id: str,
    session_id: Optional[str],
    query: str,
    response_text: str,
    agent_name: str,
    route_reason: str,
    query_type: str,
    sentiment: Optional[str],
    model_id: Optional[str],
    elapsed_ms: int,
    retrieval_elapsed: float,
    generation_elapsed: float,
    sources: List[Dict[str, Any]],
) -> None:
    """Run all the post-stream logging that used to live inline."""
    from backend.agents.interaction_log import log_agent_interaction

    with traced_span(main_trace, "log-interaction", input={"agent": agent_name}):
        log_agent_interaction(
            username=user_id,
            session_id=session_id or "",
            query=query,
            response=response_text[:2000],
            agent=agent_name,
            route_reason=route_reason,
            query_type=query_type,
            sentiment=sentiment,
            response_time_ms=elapsed_ms,
            model_id=model_id,
        )

    try:
        from backend.rag_evaluation import get_evaluator

        get_evaluator().log_runtime_metrics(
            query=query,
            response=response_text,
            retrieval_time=retrieval_elapsed,
            generation_time=generation_elapsed,
            metadata={
                "mode": "agent_chat",
                "user_id": user_id,
                "session_id": session_id,
                "agent": agent_name,
                "route_reason": route_reason,
                "query_type": query_type,
                "sentiment": sentiment,
                "model_id": model_id,
                "web_search_used": False,
            },
            num_retrieved=len(sources),
            context_passages=[
                s.get("chunk_text", "")[:500]
                for s in sources[:5]
                if isinstance(s, dict) and s.get("chunk_text")
            ],
        )
    except Exception as exc:
        logger.warning("Failed to log agent runtime metrics: %s", exc)

    update_trace(
        main_trace,
        output={"response_length": len(response_text), "agent": agent_name},
        metadata={
            "agent": agent_name,
            "route_reason": route_reason,
            "elapsed_ms": elapsed_ms,
            "num_sources": len(sources),
        },
    )


# ── RAG context helper ───────────────────────────────────────────

def _retrieve_rag_context(query: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Run the existing S3/Chroma retrieval pipeline and return (context_str, sources)."""
    import os
    from urllib.parse import quote
    from backend.retrieval_tuning import determine_retrieval_limit, select_diverse_items

    try:
        retrieval_limit = determine_retrieval_limit(
            query,
            base_top_k=3,
            max_top_k=max(5, config.SIMILARITY_TOP_K + 1),
        )
        if config.USE_S3_VECTORS:
            from backend.s3_retriever import create_s3_retriever
            retriever = create_s3_retriever(similarity_top_k=retrieval_limit)
        else:
            from llama_index.core import StorageContext, load_index_from_storage
            from utils import get_storage_context
            sc = get_storage_context()
            if sc is None:
                return "No context available.", []
            idx = load_index_from_storage(sc)
            retriever = idx.as_retriever(similarity_top_k=retrieval_limit)

        nodes = select_diverse_items(
            retriever.retrieve(query),
            query=query,
            limit=retrieval_limit,
            max_per_source=2,
        )
        sources: List[Dict[str, Any]] = []
        context_parts: List[str] = []

        for i, n_ws in enumerate(nodes, 1):
            node = n_ws.node
            text = (
                node.get_text() if hasattr(node, "get_text")
                else (node.text if hasattr(node, "text") else "")
            )
            fp = node.metadata.get("file_path") or node.metadata.get("source_file")
            file_name = os.path.basename(fp) if fp else "Unknown Source"
            source_url = (
                f"/api/backend/files/s3-document?source_file={quote(file_name)}"
                if fp else None
            )

            sources.append({
                "file_name": file_name,
                "file_path": fp,
                "source_url": source_url,
                "page": node.metadata.get("page_number"),
                "slide": node.metadata.get("slide_number"),
                "chunk_text": text[:300] + "..." if len(text) > 300 else text,
            })
            context_parts.append(f"[Source {i}: {file_name}]\n{text}")

        context_str = "\n\n".join(context_parts) if context_parts else "No relevant context found."
        return context_str, sources

    except Exception as exc:
        logger.warning("RAG retrieval failed: %s", exc)
        return "Context retrieval failed.", []
