"""
Self-RAG Grounding Check

Lightweight heuristic to verify that an LLM-generated response is grounded
in the retrieved context.  Uses token-overlap analysis (no extra LLM call)
to produce a grounding score.

Score interpretation:
  >= 0.4  — response is well-grounded in context
  <  0.4  — response may contain information beyond the provided materials

When the score is below the threshold the streaming wrapper appends a
confidence disclaimer so the student knows to double-check.
"""

import re
from typing import Tuple, Set

from backend.logger import get_logger

logger = get_logger(__name__)

# Common English stop-words (kept small for speed)
_STOP_WORDS: Set[str] = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for",
    "from", "had", "has", "have", "he", "her", "his", "how", "i",
    "if", "in", "into", "is", "it", "its", "just", "my", "no",
    "not", "of", "on", "or", "our", "she", "so", "than", "that",
    "the", "their", "them", "then", "there", "these", "they",
    "this", "to", "too", "us", "very", "was", "we", "were",
    "what", "when", "where", "which", "who", "will", "with",
    "would", "you", "your",
}

GROUNDING_THRESHOLD = 0.4

DISCLAIMER = (
    "\n\n*Note: This response may include information beyond "
    "the provided course materials.*"
)


def _significant_tokens(text: str) -> Set[str]:
    """Extract significant lowercase tokens (length > 3, not stop-words)."""
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return {t for t in tokens if len(t) > 3 and t not in _STOP_WORDS}


def check_response_grounding(response: str, context: str) -> Tuple[float, bool]:
    """
    Check if *response* is grounded in *context* using token overlap.

    Returns:
        (grounding_score, is_grounded)
        grounding_score: float 0-1 — fraction of response key-terms found in context
        is_grounded: True when score >= GROUNDING_THRESHOLD
    """
    response_tokens = _significant_tokens(response)
    if not response_tokens:
        return 1.0, True  # trivial / empty response is "grounded"

    context_tokens = _significant_tokens(context)
    if not context_tokens:
        return 0.0, False  # no context means nothing to ground against

    overlap = response_tokens & context_tokens
    score = len(overlap) / len(response_tokens)

    is_grounded = score >= GROUNDING_THRESHOLD
    logger.debug(
        "Grounding check: score=%.2f (%d/%d tokens), grounded=%s",
        score, len(overlap), len(response_tokens), is_grounded,
    )
    return score, is_grounded
