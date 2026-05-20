"""
Semantic Intent Router (embedding-based)

A lightweight companion to ``router.py``'s keyword rules.  Keyword regex
remains the fast path (~5µs) and handles obvious queries.  When keywords
return the default ``tutor_agent`` (i.e. no rule matched), we fall back to
embedding-based classification so phrases like
"I have a doubt about my quiz score" still route correctly.

Design choices:
* Uses ``sentence-transformers`` with a small model (default ``all-MiniLM-L6-v2``,
  ~22M params, ~14ms per encode on CPU). The model is loaded lazily.
* Each agent intent owns a handful of canonical "prototype" phrases; we
  pre-compute their normalised embeddings once.
* Classification is a single matmul (BLAS-accelerated).
* A per-query LRU cache avoids re-embedding repeated queries (chats often
  retry the same prompt after edits).
"""

from __future__ import annotations

import logging
import os
import threading
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ── Intent prototypes ────────────────────────────────────────────
# Order doesn't matter; ``argmax`` over centroid similarity picks the winner.

_INTENT_PROTOTYPES: Dict[str, List[str]] = {
    "feedback_agent": [
        "I love this platform, it has been very helpful",
        "Your app crashed and I'm frustrated",
        "I have a suggestion to improve the interface",
        "Thanks for the great learning experience",
        "I am disappointed with the platform's slow performance",
    ],
    "quiz_helper_agent": [
        "How did I do on my last quiz?",
        "What should I study next based on my scores?",
        "Tell me about my weakest topics from the assessment",
        "Review my quiz performance and suggest a study plan",
        "I want to improve my exam results, what should I focus on?",
    ],
    "doubts_agent": [
        "I don't understand this concept, please clarify",
        "I am confused about how this works",
        "Can you explain the difference between these two ideas?",
        "I'm lost on this topic, it makes no sense",
        "Help me understand why this happens",
    ],
    "personalised_agent": [
        "Explain this to me like I'm a beginner",
        "Walk me through this step by step in simple terms",
        "Break this down using an analogy I can relate to",
        "Teach me this concept tailored to my level",
        "Give me an ELI5 explanation",
    ],
    "tutor_agent": [
        "What is photosynthesis?",
        "How does machine learning work?",
        "Tell me about the French Revolution",
        "What are the key principles of object-oriented programming?",
        "Summarise the second law of thermodynamics",
    ],
}


# Cosine threshold the winner must clear to *override* the keyword default.
# Tuned conservatively: below this we stay with tutor_agent rather than
# misroute a generic question. Configurable via env for ops tuning.
_SIM_THRESHOLD = float(os.environ.get("SEMANTIC_ROUTER_THRESHOLD", "0.45"))
_MODEL_NAME = os.environ.get("SEMANTIC_ROUTER_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


# ── Lazy singletons ──────────────────────────────────────────────

_lock = threading.Lock()
_model = None  # type: ignore[var-annotated]
_centroids: Optional[np.ndarray] = None  # shape (n_intents, dim)
_intent_order: List[str] = []
_disabled = False  # set if model load fails


# ── Tiny LRU for query embeddings (cheap, in-process) ────────────

class _EmbeddingLRU:
    def __init__(self, max_size: int = 512):
        self._items: "OrderedDict[str, np.ndarray]" = OrderedDict()
        self._max = max_size

    def get(self, key: str) -> Optional[np.ndarray]:
        vec = self._items.get(key)
        if vec is not None:
            self._items.move_to_end(key)
        return vec

    def put(self, key: str, vec: np.ndarray) -> None:
        if key in self._items:
            self._items.move_to_end(key)
            self._items[key] = vec
            return
        if len(self._items) >= self._max:
            self._items.popitem(last=False)
        self._items[key] = vec


_embedding_cache = _EmbeddingLRU(max_size=512)


def _normalise(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    norm = np.where(norm == 0, 1.0, norm)
    return v / norm


def _load_model_and_centroids() -> bool:
    """Load the embedding model and build intent centroids. Idempotent."""
    global _model, _centroids, _intent_order, _disabled
    if _disabled:
        return False
    if _model is not None and _centroids is not None:
        return True

    with _lock:
        if _disabled:
            return False
        if _model is not None and _centroids is not None:
            return True
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading semantic router model: %s", _MODEL_NAME)
            _model = SentenceTransformer(_MODEL_NAME)

            _intent_order = list(_INTENT_PROTOTYPES.keys())
            centroids: List[np.ndarray] = []
            for intent in _intent_order:
                proto_texts = _INTENT_PROTOTYPES[intent]
                proto_vecs = np.asarray(
                    _model.encode(proto_texts, normalize_embeddings=True),
                    dtype=np.float32,
                )
                centroid = proto_vecs.mean(axis=0)
                centroids.append(_normalise(centroid))
            _centroids = np.vstack(centroids).astype(np.float32)
            logger.info(
                "Semantic router ready: %d intents, dim=%d",
                len(_intent_order),
                _centroids.shape[1],
            )
            return True
        except Exception as exc:
            logger.warning("Semantic router disabled — failed to load model: %s", exc)
            _disabled = True
            return False


def _embed_query(text: str) -> Optional[np.ndarray]:
    cached = _embedding_cache.get(text)
    if cached is not None:
        return cached
    try:
        vec = np.asarray(
            _model.encode([text], normalize_embeddings=True)[0],
            dtype=np.float32,
        )
        _embedding_cache.put(text, vec)
        return vec
    except Exception as exc:
        logger.warning("Semantic router embed failed: %s", exc)
        return None


def classify(text: str) -> Optional[Tuple[str, float, str]]:
    """Return ``(agent, similarity, reason)`` if the semantic match clears the
    threshold, otherwise ``None`` (caller should keep the keyword default).
    """
    if not text or not text.strip():
        return None
    if not _load_model_and_centroids():
        return None

    vec = _embed_query(text.strip())
    if vec is None or _centroids is None:
        return None

    sims = _centroids @ vec  # (n_intents,)
    best_idx = int(np.argmax(sims))
    best_sim = float(sims[best_idx])
    best_intent = _intent_order[best_idx]

    if best_sim < _SIM_THRESHOLD:
        return None

    reason = (
        f"Semantic match: closest to '{best_intent}' prototypes "
        f"(cosine={best_sim:.2f})"
    )
    return best_intent, best_sim, reason
