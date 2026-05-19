"""
RAG Quality Evaluator — LLM-as-Judge

Scores four quality dimensions:
  1. Faithfulness  — Is the answer grounded in the provided context?
  2. Answer Relevance — Does the answer actually address the question?
  3. Context Recall — Did the retrieved context cover the question's needs?
  4. Correctness — Is the answer correct, preferably against a reference answer?

Two judge modes:
  * `combined` (default) — one LLM call scores all four metrics. Cheap, but
    the LLM can anchor later scores on its first score (halo bias).
  * `split` — four LLM calls, each scoring exactly one metric with no
    knowledge of the others. ~4x more expensive but resistant to anchoring;
    use for high-stakes evaluations (release gates, weekly audits).

Also provides a pure-computation `compute_context_precision` that runs
without an LLM call and is cheap enough for every chat query.

The relevance threshold for `compute_context_precision` is calibrated
per subject — educational subjects with terse content (e.g. math) tend
to produce lower absolute cosine scores than narrative subjects (e.g.
literature). See `CONTEXT_PRECISION_THRESHOLDS` in `backend.config`.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from backend.bedrock_llm import BedrockLLM
from backend.config import config

logger = logging.getLogger(__name__)


# Per-subject thresholds for context_precision. Educational content shows
# meaningfully different cosine-score distributions by domain — calibrate
# at the subject level instead of using one global cutoff. Keys are
# lowercase subject slugs; values are the minimum cosine score to count a
# retrieved chunk as "relevant".  Override via config.CONTEXT_PRECISION_THRESHOLDS
# (json env var) without code changes.
_DEFAULT_CONTEXT_PRECISION_THRESHOLDS: Dict[str, float] = {
    # Numeric / formula-heavy subjects: terser embeddings, lower absolute scores
    "math":            0.25,
    "physics":         0.27,
    "chemistry":       0.27,
    "statistics":      0.27,
    # Code & technical
    "programming":     0.30,
    "computer-science": 0.30,
    # Narrative / language-rich subjects: longer overlapping vocab, higher scores
    "history":         0.40,
    "literature":      0.42,
    "language":        0.40,
    # Mixed / general default
    "general":         0.30,
}


def _resolve_threshold(subject: Optional[str]) -> float:
    """Resolve the context-precision threshold for a subject.

    Lookup order: config override → builtin per-subject map → global default.
    """
    overrides = getattr(config, "CONTEXT_PRECISION_THRESHOLDS", None) or {}
    if subject:
        key = subject.strip().lower()
        if key in overrides:
            try:
                return float(overrides[key])
            except (TypeError, ValueError):
                pass
        if key in _DEFAULT_CONTEXT_PRECISION_THRESHOLDS:
            return _DEFAULT_CONTEXT_PRECISION_THRESHOLDS[key]
    if "default" in overrides:
        try:
            return float(overrides["default"])
        except (TypeError, ValueError):
            pass
    return 0.3

# ── Single-prompt LLM-as-Judge template ──────────────────────────────
JUDGE_PROMPT = """\
You are a strict RAG quality evaluator. Given a user question, the retrieved \
context passages, the generated answer, and an optional reference answer, \
score FOUR dimensions on a scale from 0.0 to 1.0. Be critical — only give \
high scores when truly deserved.

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
4. **Correctness** (0-1): If a reference answer is provided, compare the \
generated answer to that reference and score factual correctness and \
completeness. If no reference answer is provided, estimate correctness from \
the question, context, and generated answer. Score 0 for materially incorrect \
answers and near 1 only for answers that are substantially correct.

### Input
**Question:** {question}

**Retrieved Context:**
{context}

**Generated Answer:**
{answer}

**Reference Answer:**
{reference_answer}

### Output
Respond with ONLY a JSON object (no markdown, no extra text):
{{"faithfulness": <float>, "answer_relevance": <float>, "context_recall": <float>, "correctness": <float>, "reasoning": "<brief 1-2 sentence justification>"}}
"""


def compute_context_precision(
    retrieval_scores: List[float],
    relevance_threshold: Optional[float] = None,
    subject: Optional[str] = None,
) -> float:
    """Compute context precision from retrieval similarity scores.

    Args:
        retrieval_scores: Cosine-similarity scores from the retriever (0-1).
        relevance_threshold: Explicit threshold. If None, look up by
            `subject` in CONTEXT_PRECISION_THRESHOLDS / the builtin map /
            the 0.3 global default.
        subject: Optional subject slug (e.g. "math", "history") used to
            pick a subject-calibrated threshold when one isn't provided
            explicitly. Educational subjects show very different cosine
            distributions — math averages lower than literature — so a
            single global cutoff overestimates math precision and
            underestimates literature precision.

    Returns:
        Precision score between 0.0 and 1.0.
    """
    if not retrieval_scores:
        return 0.0
    threshold = relevance_threshold if relevance_threshold is not None else _resolve_threshold(subject)
    relevant = sum(1 for s in retrieval_scores if s >= threshold)
    return round(relevant / len(retrieval_scores), 4)


# ── Single-metric prompt templates used by `judge_mode="split"` ────────
# Each focuses the LLM on exactly one rubric so it can't anchor its score
# on neighbouring metrics. Trades 4x cost for reduced position/halo bias.

_SPLIT_PROMPT_TEMPLATES: Dict[str, str] = {
    "faithfulness": (
        "You are a strict RAG quality evaluator scoring ONE dimension: faithfulness.\n"
        "Faithfulness: every claim in the answer must be directly supported by the\n"
        "context. Deduct for any hallucinated facts, unsupported claims, or\n"
        "information not present in the context. Score 0 if the answer fabricates\n"
        "material information.\n\n"
        "**Question:** {question}\n\n"
        "**Retrieved Context:**\n{context}\n\n"
        "**Generated Answer:**\n{answer}\n\n"
        "Respond with ONLY a JSON object (no markdown):\n"
        '{{"faithfulness": <float 0-1>, "reasoning": "<brief justification>"}}'
    ),
    "answer_relevance": (
        "You are a strict RAG quality evaluator scoring ONE dimension: answer relevance.\n"
        "Answer Relevance: the answer must directly address the question. Deduct for\n"
        "off-topic information, missing key aspects, or overly vague responses.\n"
        "Score 0 if the answer doesn't address the question at all.\n\n"
        "**Question:** {question}\n\n"
        "**Generated Answer:**\n{answer}\n\n"
        "Respond with ONLY a JSON object (no markdown):\n"
        '{{"answer_relevance": <float 0-1>, "reasoning": "<brief justification>"}}'
    ),
    "context_recall": (
        "You are a strict RAG quality evaluator scoring ONE dimension: context recall.\n"
        "Context Recall: the retrieved context must contain the information needed\n"
        "to answer the question comprehensively. Deduct if important aspects are\n"
        "missing from the context. Score 0 if the context is completely irrelevant.\n\n"
        "**Question:** {question}\n\n"
        "**Retrieved Context:**\n{context}\n\n"
        "**Reference Answer:** {reference_answer}\n\n"
        "Respond with ONLY a JSON object (no markdown):\n"
        '{{"context_recall": <float 0-1>, "reasoning": "<brief justification>"}}'
    ),
    "correctness": (
        "You are a strict RAG quality evaluator scoring ONE dimension: correctness.\n"
        "Correctness: when a reference answer is provided, compare the generated\n"
        "answer to that reference and score factual correctness and completeness.\n"
        "Without a reference, estimate correctness from the question, context, and\n"
        "answer. Score 0 for materially incorrect answers; near 1 only when\n"
        "substantially correct.\n\n"
        "**Question:** {question}\n\n"
        "**Reference Answer:** {reference_answer}\n\n"
        "**Generated Answer:**\n{answer}\n\n"
        "Respond with ONLY a JSON object (no markdown):\n"
        '{{"correctness": <float 0-1>, "reasoning": "<brief justification>"}}'
    ),
}


def _parse_json_block(raw_response: str) -> Dict[str, Any]:
    """Strip optional markdown fences and parse the JSON the LLM returned."""
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    return json.loads(cleaned.strip())


def _build_context_str(context_passages: List[str]) -> str:
    if context_passages:
        return "\n\n".join(
            f"[Passage {i+1}]\n{text}" for i, text in enumerate(context_passages)
        )
    return "(No context was retrieved)"


def _evaluate_split(
    question: str,
    context_str: str,
    answer: str,
    reference_answer: str,
    model_id: Optional[str],
) -> Dict[str, Any]:
    """Score the 4 metrics with 4 separate LLM calls (anti-halo)."""
    llm = BedrockLLM(model_id=model_id or config.BEDROCK_MODEL_ID)
    results: Dict[str, float] = {}
    reasonings: List[str] = []
    inputs = {
        "question": question,
        "context": context_str,
        "answer": answer,
        "reference_answer": reference_answer,
    }
    for metric, template in _SPLIT_PROMPT_TEMPLATES.items():
        try:
            raw = llm.generate(prompt=template.format(**inputs), max_tokens=200, temperature=0.0)
            parsed = _parse_json_block(raw)
            results[metric] = _clamp(float(parsed.get(metric, 0)))
            if parsed.get("reasoning"):
                reasonings.append(f"{metric}: {parsed['reasoning']}")
        except Exception as exc:
            logger.error("Split judge failed on %s: %s", metric, exc)
            results[metric] = 0.0
            reasonings.append(f"{metric}: evaluation failed ({exc})")
    return {
        "faithfulness": round(results.get("faithfulness", 0.0), 4),
        "answer_relevance": round(results.get("answer_relevance", 0.0), 4),
        "context_recall": round(results.get("context_recall", 0.0), 4),
        "correctness": round(results.get("correctness", 0.0), 4),
        "reasoning": " | ".join(reasonings),
    }


def evaluate_quality(
    question: str,
    context_passages: List[str],
    answer: str,
    reference_answer: Optional[str] = None,
    model_id: Optional[str] = None,
    judge_mode: str = "combined",
) -> Dict[str, Any]:
    """Run LLM-as-judge evaluation on a single query.

    Args:
        question: The user's original question.
        context_passages: The text of each retrieved context passage.
        answer: The generated answer text.
        reference_answer: Optional reference answer from the evaluation dataset.
        model_id: Optional Bedrock model ID to use for judging.
        judge_mode: `combined` (default, 1 LLM call) or `split` (4 calls,
            one per metric, to reduce position/halo bias).

    Returns:
        Dict with keys: faithfulness, answer_relevance, context_recall,
        correctness, and reasoning.
    """
    context_str = _build_context_str(context_passages)
    ref = reference_answer.strip() if reference_answer else "(No reference answer provided)"

    if judge_mode == "split":
        return _evaluate_split(question, context_str, answer, ref, model_id)

    # Combined-prompt path (legacy default)
    prompt = JUDGE_PROMPT.format(
        question=question,
        context=context_str,
        answer=answer,
        reference_answer=ref,
    )

    try:
        llm = BedrockLLM(model_id=model_id or config.BEDROCK_MODEL_ID)
        raw_response = llm.generate(
            prompt=prompt,
            max_tokens=300,
            temperature=0.0,  # deterministic for evaluation
        )
        scores = _parse_json_block(raw_response)

        faithfulness = _clamp(float(scores.get("faithfulness", 0)))
        answer_relevance = _clamp(float(scores.get("answer_relevance", 0)))
        context_recall = _clamp(float(scores.get("context_recall", 0)))
        fallback_correctness = round(
            (faithfulness * answer_relevance * context_recall) ** (1 / 3), 4
        )
        correctness = _clamp(float(scores.get("correctness", fallback_correctness)))
        reasoning = str(scores.get("reasoning", ""))

        return {
            "faithfulness": round(faithfulness, 4),
            "answer_relevance": round(answer_relevance, 4),
            "context_recall": round(context_recall, 4),
            "correctness": round(correctness, 4),
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
    judge_mode: str = "combined",
) -> Dict[str, Any]:
    """Run LLM-as-judge on a batch of logged queries.

    Args:
        queries: List of dicts, each with keys: query, context_passages, answer,
            and optional reference_answer.
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
        reference_answer = entry.get("reference_answer")
        scores_list = entry.get("retrieval_scores", [])
        subject = entry.get("subject")  # optional per-entry subject for threshold

        if not q or not ans:
            continue

        scores = evaluate_quality(
            q,
            ctx,
            ans,
            reference_answer=reference_answer,
            model_id=model_id,
            judge_mode=judge_mode,
        )
        ctx_precision = compute_context_precision(scores_list, subject=subject)
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
