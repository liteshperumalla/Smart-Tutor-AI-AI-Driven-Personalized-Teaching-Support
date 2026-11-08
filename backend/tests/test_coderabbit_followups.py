"""Regression tests for review findings on PR #91."""

import json
import threading

import pytest

from backend.config import config


def _summary(path, **scores):
    payload = {"quality_summary": {f"avg_{k}": v for k, v in scores.items()} | {"evaluated_count": 10}}
    path.write_text(json.dumps(payload) + "\n")
    return str(path)


GOOD = dict(faithfulness=0.8, answer_relevance=0.8, context_recall=0.7, context_precision=0.6, correctness=0.7)


class TestQualityGate:
    def test_missing_metric_fails_the_gate(self, tmp_path):
        from backend.scripts.compare_evaluations import main

        partial = {k: v for k, v in GOOD.items() if k != "correctness"}
        assert main([_summary(tmp_path / "b", **GOOD), _summary(tmp_path / "c", **partial)]) == 1

    def test_all_zero_baseline_means_the_judge_failed(self, tmp_path, capsys):
        from backend.scripts.compare_evaluations import main

        zeros = {k: 0.0 for k in GOOD}
        assert main([_summary(tmp_path / "b", **zeros), _summary(tmp_path / "c", **GOOD)]) == 2
        assert "judge most likely failed" in capsys.readouterr().err


class TestIndexUploadFailure:
    def _store(self, tmp_path, monkeypatch):
        from backend.local_embeddings import LocalEmbeddings
        from backend.s3_vector_store import S3VectorStore
        from backend.tests.test_local_embeddings_index import FakeModel, FakeS3

        fake = FakeS3()
        fake.put_object("b", "chunks/a/chunk_0000.json", json.dumps({"chunk_id": "c0", "text": "aaaa"}))

        def failing_put(Bucket, Key, Body, ContentType=None, Metadata=None):
            if Key.startswith("vector_index/"):
                raise RuntimeError("AccessDenied")
            FakeS3.put_object(fake, Bucket, Key, Body, ContentType, Metadata)

        fake.put_object = failing_put
        import backend.cloud.aws_helpers as helpers

        monkeypatch.setattr(helpers, "get_s3_client", lambda **kwargs: fake)
        monkeypatch.setattr(config, "EMBEDDING_PROVIDER", "huggingface")
        monkeypatch.setattr(config, "EMBEDDING_MODEL_ID", "m")
        return S3VectorStore(bucket_name="b", index_cache_path=str(tmp_path / "i"), s3_index_key="vector_index/m.idx",
                             embedder=LocalEmbeddings(model=FakeModel()), embedding_model="m")

    def test_rebuild_raises_when_the_upload_fails(self, tmp_path, monkeypatch):
        vs = self._store(tmp_path, monkeypatch)
        with pytest.raises(RuntimeError, match="failed to upload"):
            vs.rebuild()

    def test_add_records_still_counts_but_warns(self, tmp_path, monkeypatch, caplog):
        vs = self._store(tmp_path, monkeypatch)
        assert vs.add_records([("x", "eeee", {"source_file": "x", "chunk_index": 0, "s3_key": "k"})]) == 1
        assert "was not uploaded" in caplog.text


class TestEmbeddingCacheThreads:
    def test_concurrent_encode_with_evictions_never_raises(self):
        from backend.local_embeddings import LocalEmbeddings
        from backend.tests.test_local_embeddings_index import FakeModel

        emb = LocalEmbeddings(model=FakeModel(), cache_size=5)
        errors = []

        def worker(seed):
            try:
                for i in range(300):
                    emb.encode([f"text {(seed * 7 + i) % 12}"])
            except Exception as exc:  # pragma: no cover - the failure we guard against
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert len(emb._cache) <= 5


class TestProviderModelSelection:
    @pytest.fixture(autouse=True)
    def cfg(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_PROVIDER", "openrouter")
        monkeypatch.setattr(config, "LLM_MODEL_ID", "openrouter/free")
        monkeypatch.setattr(config, "GEMINI_MODEL_ID", "gemini-2.5-flash")
        monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
        monkeypatch.setattr(config, "OPENROUTER_API_KEY", "k")
        monkeypatch.setattr(config, "LLM_FALLBACK_PROVIDERS", [])

    def test_other_provider_gets_its_own_default_not_the_primarys(self):
        from backend.llm_provider import LLMFactory

        assert LLMFactory._create_openai_compat_llm("gemini").model_id == "gemini-2.5-flash"
        assert LLMFactory._create_openai_compat_llm("openrouter").model_id == "openrouter/free"

    def test_ollama_llamaindex_path_honours_model_id(self, monkeypatch):
        import sys
        import types

        from backend.llm_provider import LLMFactory

        captured = {}
        fake = types.ModuleType("llama_index.llms.ollama")
        fake.Ollama = lambda **kwargs: captured.update(kwargs) or "ollama-llm"
        monkeypatch.setitem(sys.modules, "llama_index.llms.ollama", fake)
        LLMFactory._create_ollama_llm(model_id="qwen3:8b")
        assert captured["model"] == "qwen3:8b"

    def test_non_streaming_request_omits_top_p(self):
        from backend.openai_compat_llm import OpenAICompatLLM
        from backend.tests.test_openai_compat_llm import FakeClient

        log = []
        llm = OpenAICompatLLM(client_factory=lambda e: FakeClient(e.provider, log), fallback_providers=[])
        llm.generate("q", top_p=0.5)
        assert "top_p" not in log[-1][1]


class TestAddRecordsMergesExistingIndex:
    def _setup(self, tmp_path, monkeypatch):
        from backend.local_embeddings import LocalEmbeddings
        from backend.s3_vector_store import S3VectorStore
        from backend.tests.test_local_embeddings_index import FakeModel, FakeS3

        fake = FakeS3()
        for i, text in enumerate(["aaaa", "eeee", "iiii"]):
            fake.put_object("b", f"chunks/x/chunk_{i:04d}.json", json.dumps({"chunk_id": f"c{i}", "text": text}))
        import backend.cloud.aws_helpers as helpers

        monkeypatch.setattr(helpers, "get_s3_client", lambda **kwargs: fake)
        monkeypatch.setattr(config, "EMBEDDING_PROVIDER", "huggingface")

        def store(cache):
            return S3VectorStore(bucket_name="b", index_cache_path=str(tmp_path / cache), s3_index_key="vector_index/m.idx",
                                 embedder=LocalEmbeddings(model=FakeModel()), embedding_model="m")

        store("first").rebuild()  # shared index: c0, c1, c2
        return fake, store

    def test_unloaded_store_merges_instead_of_overwriting(self, tmp_path, monkeypatch):
        from backend.s3_vector_store import S3VectorStore

        fake, store = self._setup(tmp_path, monkeypatch)
        fresh = store("second")  # never loaded
        fresh.add_records([("new", "oooo", {"source_file": "n", "chunk_index": 0, "s3_key": "k"})])
        uploaded = S3VectorStore._safe_deserialize(fake.objects["vector_index/m.idx"][0])
        assert sorted(m["chunk_id"] for m in uploaded["metadata"]) == ["c0", "c1", "c2", "new"]

    def test_in_memory_records_survive_the_load(self, tmp_path, monkeypatch):
        from backend.s3_vector_store import S3VectorStore

        fake, store = self._setup(tmp_path, monkeypatch)
        fresh = store("third")
        fresh.add_records([("mem", "eeii", {"source_file": "m", "chunk_index": 0, "s3_key": "k"})], persist=False)
        fresh.add_records([("new", "oooo", {"source_file": "n", "chunk_index": 0, "s3_key": "k"})])
        uploaded = S3VectorStore._safe_deserialize(fake.objects["vector_index/m.idx"][0])
        assert sorted(m["chunk_id"] for m in uploaded["metadata"]) == ["c0", "c1", "c2", "mem", "new"]
