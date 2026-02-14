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
    with traced_span(main_trace, "agent-rag-retrieval", input={"query": query}) as rag_span:
        context_str, sources = _retrieve_rag_context(query)

    # ── 3. Build state + invoke graph ─────────────────────────────
    from backend.agents.graph import get_compiled_graph
    from backend.agents.state import AgentState

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

    with traced_span(main_trace, "langgraph-invoke", input={"query": query}) as graph_span:
        compiled_graph = get_compiled_graph()
        result = compiled_graph.invoke(
            initial_state,
            {"recursion_limit": config.AGENT_GRAPH_RECURSION_LIMIT},
        )

    response_text = result.get("response", "I couldn't generate a response.")
    agent_name = result.get("agent", "tutor_agent")
    route_reason = result.get("route_reason", "")
    sentiment = result.get("sentiment")

    elapsed_ms = int((time.time() - start_time) * 1000)

    # ── 4. Log to PostgreSQL ──────────────────────────────────────
    from backend.agents.interaction_log import log_agent_interaction

    with traced_span(main_trace, "log-interaction", input={"agent": agent_name}) as log_span:
        log_agent_interaction(
            username=user_id,
            session_id=session_id or "",
            query=query,
            response=response_text[:2000],
            agent=agent_name,
            route_reason=route_reason,
            query_type=result.get("next", "general_tutoring"),
            sentiment=sentiment,
            response_time_ms=elapsed_ms,
            model_id=model_id,
        )

    # Update root trace with final output
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

    # ── 5. Stream with metadata prefix ────────────────────────────
    from backend.agents.streaming import stream_agent_response

    generator = stream_agent_response(
        response_text=response_text,
        agent_name=agent_name,
        route_reason=route_reason,
        extra_meta={"response_time_ms": elapsed_ms},
    )

    return generator, sources


# ── RAG context helper ───────────────────────────────────────────

def _retrieve_rag_context(query: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Run the existing S3/Chroma retrieval pipeline and return (context_str, sources)."""
    import os
    from urllib.parse import quote

    try:
        if config.USE_S3_VECTORS:
            from backend.s3_retriever import create_s3_retriever
            retriever = create_s3_retriever(similarity_top_k=3)
        else:
            from llama_index.core import StorageContext, load_index_from_storage
            from utils import get_storage_context
            sc = get_storage_context()
            if sc is None:
                return "No context available.", []
            idx = load_index_from_storage(sc)
            retriever = idx.as_retriever(similarity_top_k=3)

        nodes = retriever.retrieve(query)
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
