"""LLM usage reaches Prometheus and Langfuse with Bedrock's real token counts."""

import pytest

import backend.langfuse_setup as langfuse_setup
from backend import bedrock_llm
from backend.bedrock_llm import BedrockLLM
from backend.metrics import REGISTRY, record_llm_usage

MODEL = "us.meta.llama3-3-70b-instruct-v1:0"


def _sample(name, **labels):
    return REGISTRY.get_sample_value(name, labels) or 0.0


class FakeGeneration:
    def __init__(self, **kwargs):
        self.started_with = kwargs
        self.updates = {}
        self.ended = False

    def update(self, **kwargs):
        self.updates.update(kwargs)

    def end(self):
        self.ended = True


class FakeLangfuse:
    def __init__(self):
        self.generations = []

    def start_observation(self, **kwargs):
        generation = FakeGeneration(**kwargs)
        self.generations.append(generation)
        return generation


class FakeBedrock:
    def __init__(self, events):
        self.events = events

    def converse_stream(self, **kwargs):
        return {"stream": iter(self.events)}


def _llm(events):
    # Skip __init__: it builds a real boto3 client.
    llm = BedrockLLM.__new__(BedrockLLM)
    llm.model_id = MODEL
    llm.client = FakeBedrock(events)
    return llm


STREAM = [
    {"contentBlockDelta": {"delta": {"text": "Hello"}}},
    {"contentBlockDelta": {"delta": {"text": " there"}}},
    {"messageStop": {"stopReason": "end_turn"}},
    {"metadata": {"usage": {"inputTokens": 120, "outputTokens": 30}}},
]


def test_record_llm_usage_counts_requests_tokens_and_cost():
    model = "test-record-usage-model"
    before_cost = _sample("rag_total_cost_dollars_total", service="bedrock_llm")

    record_llm_usage(model, 1.5, input_tokens=100, output_tokens=40, cost_usd=0.002)

    assert _sample("llm_requests_total", model=model, status="success") == 1
    assert _sample("llm_tokens_total", model=model, token_type="input") == 100
    assert _sample("llm_tokens_total", model=model, token_type="output") == 40
    assert _sample("llm_latency_seconds_count", model=model) == 1
    assert _sample("rag_total_cost_dollars_total", service="bedrock_llm") - before_cost == pytest.approx(0.002)


def test_stream_records_bedrock_usage_and_langfuse_generation(monkeypatch):
    fake = FakeLangfuse()
    monkeypatch.setattr(langfuse_setup, "get_langfuse_client", lambda: fake)
    monkeypatch.setattr(bedrock_llm, "record_model_used", lambda model: None)
    before = _sample("llm_tokens_total", model=MODEL, token_type="input")

    text = "".join(_llm(STREAM)._stream_converse("Hi", 64, 0.2, None))

    assert text == "Hello there"
    assert _sample("llm_tokens_total", model=MODEL, token_type="input") - before == 120
    (generation,) = fake.generations
    assert generation.started_with["model"] == MODEL
    assert generation.started_with["as_type"] == "generation"
    assert generation.updates["usage_details"] == {"input": 120, "output": 30}
    assert generation.updates["cost_details"]["total"] > 0
    assert generation.updates["level"] == "DEFAULT"
    assert generation.ended


def test_stream_closed_early_is_recorded_as_cancelled(monkeypatch):
    fake = FakeLangfuse()
    monkeypatch.setattr(langfuse_setup, "get_langfuse_client", lambda: fake)
    monkeypatch.setattr(bedrock_llm, "record_model_used", lambda model: None)
    before = _sample("llm_requests_total", model=MODEL, status="cancelled")

    stream = _llm(STREAM)._stream_converse("Hi", 64, 0.2, None)
    next(stream)
    stream.close()  # the client disconnected

    assert _sample("llm_requests_total", model=MODEL, status="cancelled") - before == 1
    assert fake.generations[0].updates["status_message"] == "cancelled"
    assert fake.generations[0].ended


def test_langfuse_disabled_still_records_metrics(monkeypatch):
    monkeypatch.setattr(langfuse_setup, "get_langfuse_client", lambda: None)
    monkeypatch.setattr(bedrock_llm, "record_model_used", lambda model: None)
    before = _sample("llm_requests_total", model=MODEL, status="success")

    "".join(_llm(STREAM)._stream_converse("Hi", 64, 0.2, None))

    assert _sample("llm_requests_total", model=MODEL, status="success") - before == 1
