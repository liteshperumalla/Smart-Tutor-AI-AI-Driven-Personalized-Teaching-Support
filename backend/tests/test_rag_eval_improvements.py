"""Tests for the audit-driven eval framework improvements:

* Per-subject context-precision threshold resolution
* Split-prompt LLM judge mode dispatch
* Monte Carlo production sampler

Tests exercise pure logic paths and stub out the Bedrock LLM/embedding
calls so they run in CI without AWS credentials.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import List

import pytest


# ─── Context-precision threshold ──────────────────────────────────────


def test_compute_context_precision_uses_subject_calibrated_threshold(monkeypatch):
    from backend.services import rag_quality_evaluator as ev

    # Math threshold is 0.25 by default — three scores 0.27, 0.31, 0.18 → 2/3
    monkeypatch.setattr(ev.config, "CONTEXT_PRECISION_THRESHOLDS", {}, raising=False)
    assert ev.compute_context_precision([0.27, 0.31, 0.18], subject="math") == pytest.approx(0.6667, abs=1e-3)
    # Same scores against the literature default (0.42) → 0/3
    assert ev.compute_context_precision([0.27, 0.31, 0.18], subject="literature") == 0.0


def test_compute_context_precision_honors_config_override(monkeypatch):
    from backend.services import rag_quality_evaluator as ev

    monkeypatch.setattr(
        ev.config,
        "CONTEXT_PRECISION_THRESHOLDS",
        {"math": 0.50, "default": 0.10},
        raising=False,
    )
    # Math override raises the bar — none of the scores pass
    assert ev.compute_context_precision([0.27, 0.31, 0.18], subject="math") == 0.0
    # Unknown subject falls back to the configured default (0.10) — all pass
    assert ev.compute_context_precision([0.27, 0.31, 0.18], subject="unknown") == 1.0


def test_compute_context_precision_explicit_threshold_wins(monkeypatch):
    from backend.services import rag_quality_evaluator as ev

    monkeypatch.setattr(ev.config, "CONTEXT_PRECISION_THRESHOLDS", {"math": 0.99}, raising=False)
    # Explicit threshold overrides everything — including config and builtin
    assert ev.compute_context_precision([0.4, 0.5], subject="math", relevance_threshold=0.45) == 0.5


# ─── Split-prompt judge dispatch ──────────────────────────────────────


class _FakeLLM:
    """Stand-in for BedrockLLM that returns canned JSON per call."""

    def __init__(self, responses: List[str]):
        self._responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str, **_) -> str:
        self.calls += 1
        return self._responses.pop(0)


def test_evaluate_quality_split_mode_makes_four_calls(monkeypatch):
    from backend.services import rag_quality_evaluator as ev

    fake = _FakeLLM(
        [
            '{"faithfulness": 0.9, "reasoning": "supported"}',
            '{"answer_relevance": 0.8, "reasoning": "on-topic"}',
            '{"context_recall": 0.7, "reasoning": "mostly there"}',
            '{"correctness": 0.85, "reasoning": "matches"}',
        ]
    )
    monkeypatch.setattr(ev, "BedrockLLM", lambda model_id=None: fake)

    result = ev.evaluate_quality(
        question="What is data leakage?",
        context_passages=["Data leakage occurs when..."],
        answer="Data leakage is when test info bleeds into training.",
        reference_answer="Information from outside the training data influences training.",
        judge_mode="split",
    )

    assert fake.calls == 4, "split mode must run exactly one LLM call per metric"
    assert result["faithfulness"] == 0.9
    assert result["answer_relevance"] == 0.8
    assert result["context_recall"] == 0.7
    assert result["correctness"] == 0.85
    # Reasoning is concatenated across metrics so a reader sees per-metric notes
    assert "faithfulness:" in result["reasoning"]
    assert "correctness:" in result["reasoning"]


def test_evaluate_quality_combined_mode_uses_single_call(monkeypatch):
    from backend.services import rag_quality_evaluator as ev

    fake = _FakeLLM(
        ['{"faithfulness": 0.5, "answer_relevance": 0.5, "context_recall": 0.5, "correctness": 0.5, "reasoning": "ok"}']
    )
    monkeypatch.setattr(ev, "BedrockLLM", lambda model_id=None: fake)

    result = ev.evaluate_quality(
        question="q",
        context_passages=["c"],
        answer="a",
        judge_mode="combined",
    )
    assert fake.calls == 1
    assert result["faithfulness"] == 0.5


# ─── Monte Carlo production sampler ───────────────────────────────────


class _FakeStorage:
    """Minimal storage backend stub with predictable session data."""

    def __init__(self, sessions_by_user: dict):
        self._sessions = sessions_by_user

    def list_users(self):
        return [{"username": u} for u in self._sessions]

    def list_chat_sessions(self, username: str):
        return self._sessions.get(username, [])


def _make_session(session_id: str, updated_at: datetime, turns: list):
    """Build a ChatSession-shaped object the sampler can walk."""
    msgs = []
    for role, content, ts in turns:
        msgs.append(SimpleNamespace(role=role, content=content, timestamp=ts, sources=[]))
    return SimpleNamespace(
        id=session_id,
        title="test-subject",
        messages=msgs,
        updated_at=updated_at,
    )


def test_sample_production_queries_pairs_user_then_assistant(monkeypatch):
    from backend.services import production_sampler as ps

    now = datetime.now(timezone.utc)
    fake_storage = _FakeStorage(
        {
            "alice": [
                _make_session(
                    "s1",
                    now - timedelta(hours=2),
                    [
                        ("user", "What is overfitting?", now - timedelta(hours=2, minutes=1)),
                        ("assistant", "Overfitting happens when...", now - timedelta(hours=2)),
                        ("user", "How to avoid it?", now - timedelta(hours=1, minutes=30)),
                        ("assistant", "Use regularization, cross-validation...", now - timedelta(hours=1)),
                    ],
                )
            ]
        }
    )
    monkeypatch.setattr(ps, "get_storage_backend", lambda: fake_storage)

    samples = ps.sample_production_queries(n=5, since_hours=24, rng_seed=42)
    assert len(samples) == 2
    queries = {s["query"] for s in samples}
    assert queries == {"What is overfitting?", "How to avoid it?"}
    # subject pulled from session title
    assert all(s["subject"] == "test-subject" for s in samples)
    # session tracing carries through
    assert all(s["session_id"] == "s1" for s in samples)


def test_sample_production_queries_respects_lookback(monkeypatch):
    from backend.services import production_sampler as ps

    now = datetime.now(timezone.utc)
    fake_storage = _FakeStorage(
        {
            "alice": [
                # Updated 10 days ago — should be excluded by a 24h lookback
                _make_session(
                    "old",
                    now - timedelta(days=10),
                    [
                        ("user", "ancient question", now - timedelta(days=10)),
                        ("assistant", "ancient answer", now - timedelta(days=10)),
                    ],
                ),
                # Updated 30 minutes ago — included
                _make_session(
                    "fresh",
                    now - timedelta(minutes=30),
                    [
                        ("user", "fresh question", now - timedelta(minutes=30)),
                        ("assistant", "fresh answer", now - timedelta(minutes=29)),
                    ],
                ),
            ]
        }
    )
    monkeypatch.setattr(ps, "get_storage_backend", lambda: fake_storage)

    samples = ps.sample_production_queries(n=10, since_hours=24)
    assert len(samples) == 1
    assert samples[0]["query"] == "fresh question"


def test_sample_production_queries_empty_storage_returns_empty(monkeypatch):
    from backend.services import production_sampler as ps

    monkeypatch.setattr(ps, "get_storage_backend", lambda: _FakeStorage({}))
    assert ps.sample_production_queries(n=5, since_hours=24) == []
