"""Monte Carlo sampler for production chat queries.

Picks N random user queries from the chat-session store (across all users
in scope), filters by recency, and returns them in a shape that drops
straight into `evaluate_batch` / the existing eval pipeline. The goal is
continuous quality monitoring against real traffic instead of only the
static eval dataset.

Wired to the API in `backend/api/routes/evaluation.py` and to the
scheduled job in `.github/workflows/rag-evaluation-scheduled.yml` — both
are opt-in via the `EVAL_PRODUCTION_SAMPLE_*` config knobs.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from backend.config import config
from backend.services import get_storage_backend
from backend.services.models import ChatMessage, ChatSession

logger = logging.getLogger(__name__)


def _coerce_timestamp(value: Any) -> Optional[datetime]:
    """Return an aware UTC datetime for naive/aware/str timestamps; else None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _iter_user_query_pairs(
    storage,
    usernames: Iterable[str],
    cutoff: Optional[datetime],
) -> List[Dict[str, Any]]:
    """Walk every session for every user and yield (user_query, assistant_answer)
    pairs that match the recency cutoff.

    Each yielded dict carries enough context for `evaluate_batch` to score:
    `query`, `answer`, `context_passages`, `retrieval_scores`, `subject`,
    plus tracing fields (session_id, username, timestamp).
    """
    pairs: List[Dict[str, Any]] = []

    for username in usernames:
        try:
            sessions: List[ChatSession] = storage.list_chat_sessions(username) or []
        except Exception as exc:
            logger.debug("Skipping user %s (list_chat_sessions failed: %s)", username, exc)
            continue

        for session in sessions:
            session_updated = _coerce_timestamp(getattr(session, "updated_at", None))
            if cutoff and session_updated and session_updated < cutoff:
                continue

            messages = getattr(session, "messages", []) or []
            # Walk pairs in order so each assistant turn pairs with the
            # *preceding* user turn it actually answered.
            last_user: Optional[ChatMessage] = None
            for msg in messages:
                role = getattr(msg, "role", None)
                content = (getattr(msg, "content", "") or "").strip()
                if role == "user":
                    last_user = msg
                elif role == "assistant" and last_user is not None and content:
                    user_q = (getattr(last_user, "content", "") or "").strip()
                    if not user_q:
                        last_user = None
                        continue
                    ts = _coerce_timestamp(getattr(msg, "timestamp", None))
                    if cutoff and ts and ts < cutoff:
                        last_user = None
                        continue
                    sources = getattr(msg, "sources", None) or []
                    pairs.append(
                        {
                            "query": user_q,
                            "answer": content,
                            "context_passages": [
                                s.get("text") for s in sources if isinstance(s, dict) and s.get("text")
                            ],
                            "retrieval_scores": [
                                float(s.get("score"))
                                for s in sources
                                if isinstance(s, dict) and isinstance(s.get("score"), (int, float))
                            ],
                            "subject": (getattr(session, "title", "") or "").strip()[:64] or None,
                            "session_id": getattr(session, "id", ""),
                            "username": username,
                            "answered_at": ts.isoformat() if ts else None,
                        }
                    )
                    last_user = None
    return pairs


def sample_production_queries(
    n: Optional[int] = None,
    since_hours: Optional[int] = None,
    usernames: Optional[List[str]] = None,
    rng_seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return a random sample of N production query/answer pairs.

    Args:
        n: Number of pairs to return. Defaults to
            `config.EVAL_PRODUCTION_SAMPLE_SIZE`.
        since_hours: Only include sessions updated within this many hours.
            Defaults to `config.EVAL_PRODUCTION_SAMPLE_LOOKBACK_HOURS`.
        usernames: Explicit username list. When None, enumerates the
            storage backend (only filesystem/postgres expose this; falls
            back to an empty sample on dynamodb-only setups).
        rng_seed: Optional deterministic seed for repeatable samples
            (useful in tests and reproducible eval runs).

    Returns:
        List of dicts ready for `evaluate_batch`. Each item has `query`,
        `answer`, `context_passages`, `retrieval_scores`, `subject`,
        `session_id`, `username`, `answered_at`.
    """
    target_n = n if n is not None else getattr(config, "EVAL_PRODUCTION_SAMPLE_SIZE", 20)
    lookback = since_hours if since_hours is not None else getattr(
        config, "EVAL_PRODUCTION_SAMPLE_LOOKBACK_HOURS", 168
    )
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback) if lookback else None

    storage = get_storage_backend()

    if usernames is None:
        # Best-effort enumeration. Storage backends without list_users still
        # work if callers pass `usernames` explicitly.
        if hasattr(storage, "list_users"):
            try:
                raw_users = storage.list_users() or []
                usernames = [
                    (u.get("username") if isinstance(u, dict) else getattr(u, "username", None))
                    for u in raw_users
                ]
                usernames = [u for u in usernames if u]
            except Exception as exc:
                logger.warning("production_sampler: list_users failed (%s); returning empty sample", exc)
                usernames = []
        else:
            # Hard fail so the scheduled workflow surfaces this via its Slack
            # failure path instead of ticking with an empty sample forever.
            raise RuntimeError(
                f"production_sampler: storage backend {type(storage).__name__} "
                "does not implement list_users(); either add it to the backend "
                "or call /evaluation/sample-production with an explicit "
                "usernames= list."
            )

    pool = _iter_user_query_pairs(storage, usernames, cutoff)
    if not pool:
        logger.info("production_sampler: empty pool (no recent assistant answers in window)")
        return []

    rng = random.Random(rng_seed)
    if target_n >= len(pool):
        rng.shuffle(pool)
        return pool
    return rng.sample(pool, target_n)


def run_production_sample_evaluation(
    n: Optional[int] = None,
    since_hours: Optional[int] = None,
    judge_mode: Optional[str] = None,
    model_id: Optional[str] = None,
    rng_seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Sample production traffic and run the LLM-judge over it.

    Thin orchestrator: pulls a Monte Carlo sample, runs `evaluate_batch`
    with the configured judge mode, and returns the same shape the
    existing scheduled-eval endpoint uses so callers can diff against it.
    """
    from backend.services.rag_quality_evaluator import evaluate_batch

    mode = judge_mode or getattr(config, "EVAL_JUDGE_MODE", "combined")
    samples = sample_production_queries(n=n, since_hours=since_hours, rng_seed=rng_seed)
    if not samples:
        return {
            "total_evaluated": 0,
            "quality_summary": None,
            "individual_results": [],
            "sampled_pairs": 0,
            "lookback_hours": since_hours or config.EVAL_PRODUCTION_SAMPLE_LOOKBACK_HOURS,
            "judge_mode": mode,
        }

    result = evaluate_batch(samples, model_id=model_id, judge_mode=mode)
    result["sampled_pairs"] = len(samples)
    result["lookback_hours"] = since_hours or config.EVAL_PRODUCTION_SAMPLE_LOOKBACK_HOURS
    result["judge_mode"] = mode
    return result
