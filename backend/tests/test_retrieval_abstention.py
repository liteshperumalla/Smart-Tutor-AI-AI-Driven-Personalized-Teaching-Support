"""Low-relevance retrieval must not reach the answer context.

When no candidate clears MIN_RETRIEVAL_SCORE the retriever returns nothing,
the chat path abstains with NO_RELEVANT_MATERIAL_RESPONSE, and the agents get
a marker their prompts tell them to treat as "not covered by the course".
"""

from llama_index.core.schema import QueryBundle

from backend.config import config
from backend.s3_retriever import S3Retriever


class _FakeEmbeddings:
    def encode(self, texts):
        return [[0.0] * 4 for _ in texts]


class _FakeStore:
    def __init__(self, results):
        self.results = results

    def ensure_loaded(self, force_rebuild=False):
        pass

    def search(self, query_embedding, top_k):
        return self.results[:top_k]

    def get_chunk_texts(self, chunk_ids):
        return {cid: f"text of {cid}" for cid in chunk_ids}


def _retriever(results, monkeypatch):
    monkeypatch.setattr(config, "RERANKING_ENABLED", False)
    monkeypatch.setattr(config, "MIN_RETRIEVAL_SCORE", 0.25)
    return S3Retriever(vector_store=_FakeStore(results), embeddings=_FakeEmbeddings(), similarity_top_k=3)


def test_all_results_below_threshold_returns_nothing(monkeypatch):
    retriever = _retriever([("a", 0.2, {}), ("b", 0.1, {})], monkeypatch)

    assert retriever._retrieve(QueryBundle("unrelated question")) == []
    assert retriever._stats["total_retrievals"] == 1


def test_only_results_above_threshold_are_kept(monkeypatch):
    retriever = _retriever([("a", 0.6, {}), ("b", 0.1, {})], monkeypatch)

    nodes = retriever._retrieve(QueryBundle("question"))

    assert [n.node.id_ for n in nodes] == ["a"]


def test_streaming_chat_abstains_without_relevant_material(monkeypatch):
    import utils

    class _EmptyRetriever:
        def retrieve(self, query):
            return []

    monkeypatch.setattr(config, "USE_S3_VECTORS", True)
    monkeypatch.setattr(config, "ANSWER_CACHE_ENABLED", False)
    monkeypatch.setattr(utils, "create_s3_retriever", lambda similarity_top_k=3: _EmptyRetriever())
    monkeypatch.setattr(utils, "_should_search_web", lambda *a, **k: False)

    def _no_synthesis(**kwargs):
        raise AssertionError("must not synthesize from zero nodes")

    monkeypatch.setattr(utils, "get_response_synthesizer", _no_synthesis)

    stream, sources = utils.generate_response_stream_and_sources(
        "What is the capital of Atlantis?", allow_web_search=False
    )

    assert "".join(stream) == utils.NO_RELEVANT_MATERIAL_RESPONSE
    assert sources == []


def test_agent_prompts_handle_missing_course_material():
    from backend.agents import NO_COURSE_MATERIAL
    from backend.agents.doubts_agent import _DOUBT_SYSTEM_PROMPT
    from backend.agents.personalised_agent import _PERSONALISED_SYSTEM_PROMPT
    from backend.agents.tutor_agent import _TUTOR_SYSTEM_PROMPT

    for prompt in (_TUTOR_SYSTEM_PROMPT, _DOUBT_SYSTEM_PROMPT, _PERSONALISED_SYSTEM_PROMPT):
        assert f'"{NO_COURSE_MATERIAL}"' in prompt
