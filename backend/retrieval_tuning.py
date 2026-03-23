from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "what",
    "when",
    "which",
    "why",
    "with",
}

_COMPLEXITY_HINTS = (
    "compare",
    "contrast",
    "difference",
    "advantages",
    "disadvantages",
    "tradeoff",
    "trade-off",
    "explain",
    "steps",
    "process",
    "workflow",
    "architecture",
    "pipeline",
)


def extract_query_terms(query: str) -> List[str]:
    terms = re.findall(r"[a-z0-9]{3,}", query.lower())
    return [term for term in terms if term not in _STOPWORDS]


def determine_retrieval_limit(
    query: str,
    base_top_k: int = 3,
    max_top_k: int = 6,
) -> int:
    """Choose a slightly larger retrieval budget for broader or multi-part questions."""
    limit = max(1, base_top_k)
    lowered = query.lower()
    terms = extract_query_terms(query)

    if len(terms) >= 7:
        limit += 1
    if any(hint in lowered for hint in _COMPLEXITY_HINTS):
        limit += 1
    if lowered.count(" and ") + lowered.count(" or ") + lowered.count(",") >= 2:
        limit += 1

    return min(limit, max_top_k)


def _item_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("text_excerpt") or item.get("text") or "")
    node = getattr(item, "node", item)
    if hasattr(node, "get_text"):
        return str(node.get_text() or "")
    return str(getattr(node, "text", "") or "")


def _item_metadata(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        return dict(item.get("metadata") or {})
    node = getattr(item, "node", item)
    return dict(getattr(node, "metadata", {}) or {})


def _item_score(item: Any) -> float:
    if isinstance(item, dict):
        metadata = _item_metadata(item)
        return float(
            metadata.get("rerank_score")
            or metadata.get("similarity_score")
            or item.get("score")
            or 0.0
        )
    metadata = _item_metadata(item)
    return float(
        metadata.get("rerank_score")
        or metadata.get("similarity_score")
        or getattr(item, "score", 0.0)
        or 0.0
    )


def _item_source(item: Any) -> str:
    metadata = _item_metadata(item)
    return str(
        metadata.get("source_file")
        or metadata.get("file_path")
        or metadata.get("source")
        or metadata.get("s3_key")
        or "unknown"
    )


def select_diverse_items(
    items: Iterable[Any],
    query: str,
    limit: int,
    max_per_source: int = 2,
) -> List[Any]:
    """Deduplicate and diversify retrieval results while keeping query-relevant passages."""
    query_terms = set(extract_query_terms(query))
    candidates = []

    for idx, item in enumerate(items):
        text = _item_text(item).strip()
        if not text:
            continue
        text_key = re.sub(r"\s+", " ", text.lower())[:400]
        source = _item_source(item)
        overlap = sum(1 for term in query_terms if term in text.lower())
        candidates.append(
            {
                "index": idx,
                "item": item,
                "text_key": text_key,
                "source": source,
                "overlap": overlap,
                "score": _item_score(item),
            }
        )

    ranked = sorted(
        candidates,
        key=lambda candidate: (
            candidate["overlap"],
            candidate["score"],
            -candidate["index"],
        ),
        reverse=True,
    )

    selected: List[Any] = []
    seen_text = set()
    source_counts = defaultdict(int)

    for source_cap in (1, max_per_source):
        for candidate in ranked:
            if len(selected) >= limit:
                break
            if candidate["text_key"] in seen_text:
                continue
            if source_counts[candidate["source"]] >= source_cap:
                continue
            selected.append(candidate["item"])
            seen_text.add(candidate["text_key"])
            source_counts[candidate["source"]] += 1

        if len(selected) >= limit:
            break

    return selected


def build_grounded_answer_prompt(query: str, context_passages: List[str]) -> str:
    context = "\n\n".join(
        f"[Passage {idx + 1}]\n{passage}" for idx, passage in enumerate(context_passages)
    )
    return (
        "You are a course-grounded tutor. Answer the question using only the provided "
        "context. Prioritize the most relevant evidence, synthesize overlapping passages, "
        "and be explicit when the context is insufficient. Do not invent facts.\n\n"
        f"Context:\n{context or '(No context retrieved)'}\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )


def build_rag_recommendations(
    *,
    avg_context_recall: float | None = None,
    avg_context_precision: float | None = None,
    avg_correctness: float | None = None,
    avg_topic_coverage: float | None = None,
    p95_response_time: float | None = None,
) -> List[str]:
    recommendations: List[str] = []

    if avg_context_recall is not None and avg_context_recall < 0.6:
        recommendations.append(
            "Increase retrieval breadth for multi-part questions and keep more diverse context passages."
        )
    if avg_context_precision is not None and avg_context_precision < 0.55:
        recommendations.append(
            "Tighten retrieval relevance by favoring query-term overlap and limiting duplicate chunks from the same source."
        )
    if avg_correctness is not None and avg_correctness < 0.6:
        recommendations.append(
            "Strengthen grounding prompts so answers explicitly defer when the retrieved evidence is incomplete."
        )
    if avg_topic_coverage is not None and avg_topic_coverage < 0.7:
        recommendations.append(
            "Expand retrieval coverage for broad conceptual questions before generation."
        )
    if p95_response_time is not None and p95_response_time > 20:
        recommendations.append(
            "Review retrieval and generation latency hotspots before increasing retrieval breadth further."
        )

    if not recommendations:
        recommendations.append(
            "Current evaluation metrics are healthy; continue monitoring regressions against the stored baseline."
        )

    return recommendations
