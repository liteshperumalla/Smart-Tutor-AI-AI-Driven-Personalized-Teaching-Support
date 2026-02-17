"""
LLM Complexity-Based Routing

Classifies query complexity using lightweight heuristics (no LLM call needed)
and selects the appropriate model tier. Simple queries route to a smaller/cheaper
model; complex queries route to the full-power model.

Heuristic signals (scored 0-1, threshold configurable):
- Query length: short queries lean simple, long queries lean complex
- Question type: definitional ("what is") vs analytical ("compare/analyze")
- Multi-part detection: conjunctions, multiple question marks
- Code/technical content: code blocks, math notation
- Greetings: short-circuit to simple with high confidence
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Patterns that signal simple/definitional queries
SIMPLE_PATTERNS = re.compile(
    r"^(what\s+is|what\s+are|define|list|name|who\s+is|when\s+was|where\s+is)",
    re.IGNORECASE,
)

# Patterns that signal complex/analytical queries
COMPLEX_PATTERNS = re.compile(
    r"\b(compare|contrast|analyze|analyse|evaluate|design|explain\s+how|"
    r"how\s+would|what\s+are\s+the\s+(?:advantages|disadvantages|differences|trade-?offs)|"
    r"discuss|justify|critique|implement|describe\s+the\s+process)",
    re.IGNORECASE,
)

# Multi-part indicators
MULTIPART_PATTERNS = re.compile(
    r"\b(and\s+also|additionally|furthermore|moreover|in\s+addition)\b",
    re.IGNORECASE,
)

# Greeting / trivial patterns (short-circuit)
GREETING_PATTERNS = re.compile(
    r"^(hi|hello|hey|good\s+morning|good\s+evening|greetings|thanks|thank\s+you|bye|goodbye|ok|okay)\b",
    re.IGNORECASE,
)

# Code/technical indicators
CODE_INDICATORS = re.compile(
    r"(```|`[^`]+`|def\s+\w+|class\s+\w+|import\s+\w+|function\s+\w+|\$\$|\\frac|\\sum)",
)


def classify_query_complexity(query: str) -> Tuple[str, float]:
    """
    Classify a user query as 'simple' or 'complex' using heuristic scoring.

    Returns:
        Tuple of (tier, confidence) where tier is 'simple' or 'complex'
        and confidence is a float between 0.0 and 1.0.
    """
    query = query.strip()

    # Short-circuit: greetings / trivial messages
    if GREETING_PATTERNS.match(query) and len(query.split()) <= 5:
        return ("simple", 1.0)

    score = 0.0  # Higher = more complex

    # Signal 1: Query length
    word_count = len(query.split())
    if word_count > 40:
        score += 0.2
    elif word_count < 15:
        score += 0.0  # Neutral for short queries

    # Signal 2: Question type patterns
    if SIMPLE_PATTERNS.match(query):
        score -= 0.3  # Push toward simple
    if COMPLEX_PATTERNS.search(query):
        score += 0.3  # Push toward complex

    # Signal 3: Multi-part detection
    if MULTIPART_PATTERNS.search(query):
        score += 0.2
    question_marks = query.count("?")
    if question_marks >= 2:
        score += 0.2

    # Signal 4: Code/technical content
    if CODE_INDICATORS.search(query):
        score += 0.2

    # Clamp score to [0, 1]
    score = max(0.0, min(1.0, score))

    # Import threshold from config
    from backend.config import config
    threshold = config.LLM_ROUTING_COMPLEXITY_THRESHOLD

    if score >= threshold:
        confidence = min(1.0, 0.5 + score)
        return ("complex", confidence)
    else:
        confidence = min(1.0, 0.5 + (threshold - score))
        return ("simple", confidence)


def select_model_for_complexity(tier: str) -> str:
    """
    Select the appropriate Bedrock model ID for the given complexity tier.

    Returns:
        A model ID string. Falls back to the default BEDROCK_MODEL_ID
        if no tier-specific model is configured.
    """
    from backend.config import config

    if tier == "simple" and config.LLM_ROUTING_SIMPLE_MODEL:
        return config.LLM_ROUTING_SIMPLE_MODEL
    elif tier == "complex" and config.LLM_ROUTING_COMPLEX_MODEL:
        return config.LLM_ROUTING_COMPLEX_MODEL

    # Fallback to default model
    return config.BEDROCK_MODEL_ID
