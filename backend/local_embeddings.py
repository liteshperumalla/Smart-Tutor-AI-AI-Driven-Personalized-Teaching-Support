"""Local embeddings with sentence-transformers (no API, no cost).

Replaces Bedrock Titan when ``EMBEDDING_PROVIDER`` is ``huggingface`` or
``local``. Same interface as ``BedrockEmbeddings`` (``encode``,
``encode_queries``, ``encode_corpus``, ``get_sentence_embedding_dimension``,
``get_stats``, ``model_id``, ``dimension``), so the retriever, the indexing
service and the rebuild script work with either.

The default model, ``BAAI/bge-small-en-v1.5`` (384 dimensions), runs on CPU.
Vectors are L2-normalised, so cosine similarity in ``S3VectorStore`` is a
plain dot product, as with Titan's normalised output.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from typing import Any, List, Optional

from backend.logger import get_logger

logger = get_logger(__name__)

# Rough characters-per-token, only for the token metric (the model's own
# tokenizer truncates inputs to its max sequence length).
_CHARS_PER_TOKEN = 4


def _record_metrics(model_id: str, duration: float, tokens: int, error_type: Optional[str] = None) -> None:
    try:
        from backend import metrics

        metrics.track_embedding_request(model_id, duration, status="error" if error_type else "success")
        if error_type:
            metrics.track_embedding_error(model_id, error_type)
            return
        metrics.track_tokens("local_embedding", input_tokens=tokens)
    except Exception:
        pass


def _cpu_threads() -> int:
    """Threads for torch: EMBEDDING_NUM_THREADS, else the container's CPU quota.

    torch defaults to one thread per host core, but a container capped with
    ``--cpus 1`` gets throttled when it runs more threads than its quota,
    which slows encoding down.
    """
    import os

    configured = os.getenv("EMBEDDING_NUM_THREADS", "").strip()
    if configured.isdigit() and int(configured) > 0:
        return int(configured)
    cores = os.cpu_count() or 1
    try:
        quota, period = open("/sys/fs/cgroup/cpu.max").read().split()[:2]  # cgroup v2
        if quota != "max":
            return max(1, min(cores, round(int(quota) / int(period))))
    except (OSError, ValueError):
        pass
    try:
        quota = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read())  # cgroup v1
        period = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read())
        if quota > 0:
            return max(1, min(cores, round(quota / period)))
    except (OSError, ValueError):
        pass
    return cores


def _record_cache(hit: bool) -> None:
    try:
        from backend import metrics

        (metrics.track_cache_hit if hit else metrics.track_cache_miss)("embedding")
    except Exception:
        pass


class LocalEmbeddings:
    """sentence-transformers model with an LRU cache, Titan-compatible API."""

    def __init__(
        self,
        model_id: Optional[str] = None,
        cache_size: int = 1000,
        batch_size: Optional[int] = None,
        model: Any = None,
    ):
        from backend.config import config

        self.model_id = model_id or config.EMBEDDING_MODEL
        self.batch_size = batch_size or config.EMBEDDING_BATCH_SIZE
        self.cache_size = cache_size
        if model is None:
            from sentence_transformers import SentenceTransformer

            try:
                import torch

                threads = _cpu_threads()
                torch.set_num_threads(threads)
                logger.info(f"Local embeddings: {threads} CPU thread(s)")
            except Exception as exc:  # torch missing or already initialised
                logger.debug(f"Could not set torch threads: {exc}")
            model = SentenceTransformer(self.model_id, device="cpu")
        self._model = model
        self.dimension = int(self._model.get_sentence_embedding_dimension())
        self._cache: "OrderedDict[str, List[float]]" = OrderedDict()
        # The model isn't documented as thread-safe; API threads share one.
        self._lock = threading.Lock()
        # Separate lock for the LRU cache and counters, so lookups don't wait
        # behind a long encode batch (e.g. an upload) and an eviction can't
        # race another thread's move_to_end.
        self._cache_lock = threading.Lock()
        self.total_requests = 0
        self.total_tokens = 0
        logger.info(f"✓ Local embeddings initialized: {self.model_id} ({self.dimension} dims)")

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()

    def encode(self, texts: List[str], batch_size: Optional[int] = None, show_progress_bar: bool = False, **kwargs) -> List[List[float]]:
        """Embed ``texts``; cached texts skip the model. Order is preserved."""
        results: List[Optional[List[float]]] = [None] * len(texts)
        missing: List[int] = []
        with self._cache_lock:
            for i, text in enumerate(texts):
                key = self._key(text)
                cached = self._cache.get(key)
                if cached is not None:
                    self._cache.move_to_end(key)
                    results[i] = cached
                else:
                    missing.append(i)
        hits = len(texts) - len(missing)
        for _ in range(hits):
            _record_cache(hit=True)
        for _ in missing:
            _record_cache(hit=False)

        if missing:
            batch = [texts[i] for i in missing]
            started = time.monotonic()
            try:
                with self._lock:
                    vectors = self._model.encode(
                        batch,
                        batch_size=batch_size or self.batch_size,
                        normalize_embeddings=True,
                        show_progress_bar=show_progress_bar,
                        convert_to_numpy=True,
                    )
            except Exception as exc:
                _record_metrics(self.model_id, time.monotonic() - started, 0, error_type=type(exc).__name__)
                raise
            tokens = sum(len(t) for t in batch) // _CHARS_PER_TOKEN
            _record_metrics(self.model_id, time.monotonic() - started, tokens)
            new = [(i, [float(x) for x in vector]) for i, vector in zip(missing, vectors)]
            with self._cache_lock:
                self.total_requests += len(batch)
                self.total_tokens += tokens
                for i, as_list in new:
                    results[i] = as_list
                    self._cache[self._key(texts[i])] = as_list
                    if len(self._cache) > self.cache_size:
                        self._cache.popitem(last=False)
        return results  # type: ignore[return-value]

    def encode_queries(self, queries: List[str]) -> List[List[float]]:
        return self.encode(queries)

    def encode_corpus(self, corpus: List[str]) -> List[List[float]]:
        return self.encode(corpus)

    def get_sentence_embedding_dimension(self) -> int:
        return self.dimension

    def get_stats(self) -> dict:
        return {
            "model": self.model_id,
            "provider": "local",
            "total_requests": self.total_requests,
            "total_tokens_estimated": self.total_tokens,
            "dimension": self.dimension,
        }
