"""
RAG Quality Evaluator — LLM-as-Judge

Uses a single Bedrock LLM call to score three quality dimensions:
  1. Faithfulness  — Is the answer grounded in the provided context?
  2. Answer Relevance — Does the answer actually address the question?
  3. Context Recall — Did the retrieved context cover the question's needs?

Also provides a pure-computation `compute_context_precision` function
that needs no LLM call and can be run on every chat query cheaply.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from backend.bedrock_llm import BedrockLLM
from backend.config import config

logger = logging.getLogger(__name__)

# ── Single-prompt LLM-as-Judge template ──────────────────────────────
JUDGE_PROMPT = """\
You are a strict RAG quality evaluator. Given a user question, the retrieved \
context passages, and the generated answer, score THREE dimensions on a scale \
from 0.0 to 1.0. Be critical — only give high scores when truly deserved.

### Scoring rubric
1. **Faithfulness** (0-1): Every claim in the answer must be directly \
supported by the context. Deduct for any hallucinated facts, unsupported \
claims, or information not present in the context. Score 0 if the answer \
fabricates information.
2. **Answer Relevance** (0-1): The answer must directly address the \
question. Deduct for off-topic information, missing key aspects of the \
question, or overly vague responses. Score 0 if the answer doesn't address \
the question at all.
3. **Context Recall** (0-1): The retrieved context must contain the \
information needed to answer the question comprehensively. Deduct if \
important aspects are missing from the context. Score 0 if the context \
is completely irrelevant.

### Input
**Question:** {question}

**Retrieved Context:**
{context}

**Generated Answer:**
{answer}

### Output
Respond with ONLY a JSON object (no markdown, no extra text):
{{"faithfulness": <float>, "answer_relevance": <float>, "context_recall": <float>, "reasoning": "<brief 1-2 sentence justification>"}}
"""


def compute_context_precision(
    retrieval_scores: List[float],
    relevance_threshold: float = 0.5,
) -> float:
    """Compute context precision from retrieval similarity scores.

    This is a cheap, pure-computation metric that can run on every query.
    It measures what fraction of retrieved documents exceed the relevance
    threshold — i.e., how precise the retrieval was.

    Args:
        retrieval_scores: Similarity scores from the retriever (0-1).
        relevance_threshold: Minimum score to consider a document relevant.

    Returns:
        Precision score between 0.0 and 1.0.
    """
    if not retrieval_scores:
        return 0.0
    relevant = sum(1 for s in retrieval_scores if s >= relevance_threshold)
    return round(relevant / len(retrieval_scores), 4)


def evaluate_quality(
    question: str,
    context_passages: List[str],
    answer: str,
    model_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run LLM-as-judge evaluation on a single query.

    Args:
        question: The user's original question.
        context_passages: The text of each retrieved context passage.
        answer: The generated answer text.
        model_id: Optional Bedrock model ID to use for judging.

    Returns:
        Dict with keys: faithfulness, answer_relevance, context_recall,
        reasoning, and correctness (geometric mean of the three).
    """
    # Build context string with numbered passages
    if context_passages:
        context_str = "\n\n".join(
            f"[Passage {i+1}]\n{text}" for i, text in enumerate(context_passages)
        )
    else:
        context_str = "(No context was retrieved)"

    prompt = JUDGE_PROMPT.format(
        question=question,
        context=context_str,
        answer=answer,
    )

    try:
        llm = BedrockLLM(model_id=model_id or config.BEDROCK_MODEL_ID)
        raw_response = llm.generate(
            prompt=prompt,
            max_tokens=300,
            temperature=0.0,  # deterministic for evaluation
        )

        # Parse the JSON response
        # Strip markdown code fences if the LLM wraps output
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        scores = json.loads(cleaned)

        faithfulness = _clamp(float(scores.get("faithfulness", 0)))
        answer_relevance = _clamp(float(scores.get("answer_relevance", 0)))
        context_recall = _clamp(float(scores.get("context_recall", 0)))
        reasoning = str(scores.get("reasoning", ""))

        # Correctness = geometric mean of the three dimensions
        correctness = round(
            (faithfulness * answer_relevance * context_recall) ** (1 / 3), 4
        )

        return {
            "faithfulness": round(faithfulness, 4),
            "answer_relevance": round(answer_relevance, 4),
            "context_recall": round(context_recall, 4),
            "correctness": correctness,
            "reasoning": reasoning,
        }

    except json.JSONDecodeError as e:
        logger.error(f"LLM judge returned invalid JSON: {e}")
        return _empty_scores(f"JSON parse error: {e}")
    except Exception as e:
        logger.error(f"LLM judge evaluation failed: {e}")
        return _empty_scores(str(e))


def evaluate_batch(
    queries: List[Dict[str, Any]],
    model_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run LLM-as-judge on a batch of logged queries.

    Args:
        queries: List of dicts, each with keys: query, context_passages, answer.
        model_id: Optional Bedrock model ID.

    Returns:
        Dict with total_evaluated, quality_summary (averages), and
        individual_results (list of per-query scores).
    """
    individual_results = []
    faithfulness_sum = 0.0
    answer_relevance_sum = 0.0
    context_recall_sum = 0.0
    context_precision_sum = 0.0
    correctness_sum = 0.0
    evaluated_count = 0

    for entry in queries:
        q = entry.get("query", "")
        ctx = entry.get("context_passages", [])
        ans = entry.get("answer", "")
        scores_list = entry.get("retrieval_scores", [])

        if not q or not ans:
            continue

        scores = evaluate_quality(q, ctx, ans, model_id=model_id)
        ctx_precision = compute_context_precision(scores_list)
        scores["context_precision"] = ctx_precision

        individual_results.append({
            "query": q[:100],
            **scores,
        })

        faithfulness_sum += scores["faithfulness"]
        answer_relevance_sum += scores["answer_relevance"]
        context_recall_sum += scores["context_recall"]
        context_precision_sum += ctx_precision
        correctness_sum += scores["correctness"]
        evaluated_count += 1

    if evaluated_count == 0:
        return {
            "total_evaluated": 0,
            "quality_summary": None,
            "individual_results": [],
        }

    return {
        "total_evaluated": evaluated_count,
        "quality_summary": {
            "avg_faithfulness": round(faithfulness_sum / evaluated_count, 4),
            "avg_answer_relevance": round(answer_relevance_sum / evaluated_count, 4),
            "avg_context_recall": round(context_recall_sum / evaluated_count, 4),
            "avg_context_precision": round(context_precision_sum / evaluated_count, 4),
            "avg_correctness": round(correctness_sum / evaluated_count, 4),
        },
        "individual_results": individual_results,
    }


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _empty_scores(error: str = "") -> Dict[str, Any]:
    return {
        "faithfulness": 0.0,
        "answer_relevance": 0.0,
        "context_recall": 0.0,
        "correctness": 0.0,
        "reasoning": f"Evaluation failed: {error}" if error else "",
    }
