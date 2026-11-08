"""Local embeddings and the per-model vector index (Phase 2 of the AWS exit)."""

import io
import json

import numpy as np
import pytest
from botocore.exceptions import ClientError

from backend.config import config
from backend.local_embeddings import LocalEmbeddings
from backend.s3_vector_store import LEGACY_INDEX_MODEL, IndexModelMismatchError, S3VectorStore

MODEL = "BAAI/bge-small-en-v1.5"


class FakeModel:
    """Deterministic 4-dim 'embeddings': letter counts of a, e, i, o."""

    def __init__(self):
        self.calls = []

    def get_sentence_embedding_dimension(self):
        return 4

    def encode(self, texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True):
        self.calls.append(list(texts))
        out = []
        for text in texts:
            vec = np.array([text.count(c) + 0.01 for c in "aeio"], dtype=np.float32)
            out.append(vec / np.linalg.norm(vec) if normalize_embeddings else vec)
        return np.array(out)


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, ContentType=None, Metadata=None):
        self.objects[Key] = (Body if isinstance(Body, bytes) else Body.encode(), Metadata or {})

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "missing"}}, "GetObject")
        body, meta = self.objects[Key]
        return {"Body": io.BytesIO(body), "Metadata": meta}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    def get_paginator(self, name):
        objects = self.objects

        class Paginator:
            def paginate(self, Bucket, Prefix=""):
                yield {"Contents": [{"Key": k} for k in sorted(objects) if k.startswith(Prefix)]}

        return Paginator()


@pytest.fixture
def local_config(monkeypatch):
    monkeypatch.setattr(config, "EMBEDDING_PROVIDER", "huggingface")
    monkeypatch.setattr(config, "EMBEDDING_MODEL", MODEL)
    monkeypatch.setattr(config, "EMBEDDING_MODEL_ID", MODEL)
    monkeypatch.setattr(config, "VECTOR_INDEX_KEY", "vector_index/BAAI_bge-small-en-v1.5.idx")
    monkeypatch.setattr(config, "EMBEDDING_BATCH_SIZE", 2)


@pytest.fixture
def s3(monkeypatch):
    fake = FakeS3()
    import backend.cloud.aws_helpers as helpers

    monkeypatch.setattr(helpers, "get_s3_client", lambda **kwargs: fake)
    # Three chunk layouts: inline JSON, legacy .vector.json + .txt, bare .txt.
    fake.put_object("b", "chunks/a/chunk_0000.json", json.dumps(
        {"chunk_id": "inline-0", "text": "aaaa banana", "embedding": [0.1] * 1024, "source_file": "a.pdf", "chunk_index": 0}
    ))
    fake.put_object("b", "chunks/b/chunk_0000.vector.json", json.dumps(
        {"chunk_id": "legacy-0", "embedding": [0.2] * 1024, "source_file": "b.pdf", "chunk_index": 0}
    ))
    fake.put_object("b", "chunks/b/chunk_0000.txt", b"eeee cheese")
    fake.put_object("b", "chunks/c/chunk_0000.txt", b"oooo zoo",
                    Metadata={"chunk-id": "upload-0", "source-file": "c.pdf", "chunk-index": "0"})
    return fake


def store(tmp_path, **kwargs):
    return S3VectorStore(bucket_name="b", index_cache_path=str(tmp_path / "idx"), embedder=LocalEmbeddings(model=FakeModel()), **kwargs)


class TestLocalEmbeddings:
    def test_encode_normalises_and_caches(self, local_config):
        model = FakeModel()
        emb = LocalEmbeddings(model=model)
        first = emb.encode(["aaa", "eee"])
        again = emb.encode(["eee", "ooo"])
        assert emb.dimension == emb.get_sentence_embedding_dimension() == 4
        assert np.isclose(np.linalg.norm(first[0]), 1.0)
        assert again[0] == first[1]
        assert model.calls == [["aaa", "eee"], ["ooo"]]  # "eee" came from the cache
        assert emb.get_stats()["model"] == MODEL
        assert emb.total_requests == 3

    def test_factory_picks_local_off_bedrock(self, local_config, monkeypatch):
        import backend.local_embeddings as le
        from backend.llm_provider import create_embedding_client

        monkeypatch.setattr(le, "LocalEmbeddings", lambda model_id=None: ("local", model_id))
        assert create_embedding_client() == ("local", MODEL)


class TestConfigKeys:
    def test_each_model_has_its_own_index_key(self):
        from backend.config import vector_index_key_for

        assert vector_index_key_for("huggingface", "BAAI/bge-base-en-v1.5") == "vector_index/BAAI_bge-base-en-v1.5.idx"
        assert vector_index_key_for("local", MODEL) == "vector_index/BAAI_bge-small-en-v1.5.idx"
        # Titan's key is unchanged, so production's index keeps working.
        assert vector_index_key_for("bedrock", "amazon.titan-embed-text-v2:0") == "vector_index/s3_vector_index.pkl"


class TestIndexBuild:
    def test_lists_one_record_per_chunk_whatever_the_layout(self, local_config, s3, tmp_path):
        assert sorted(store(tmp_path).list_chunk_records()) == [
            "chunks/a/chunk_0000.json",
            "chunks/b/chunk_0000.vector.json",
            "chunks/c/chunk_0000.txt",
        ]

    def test_rebuild_re_embeds_text_and_uploads_a_tagged_index(self, local_config, s3, tmp_path):
        vs = store(tmp_path)
        assert vs.rebuild() == 3
        assert {cid for cid, _ in vs.vectors} == {"inline-0", "legacy-0", "upload-0"}
        assert all(len(vec) == 4 for _, vec in vs.vectors)  # not the 1024-dim Titan vectors
        assert vs.metadata["legacy-0"]["s3_key"] == "chunks/b/chunk_0000.txt"
        assert vs.metadata["upload-0"]["source_file"] == "c.pdf"
        raw, meta = s3.objects[config.VECTOR_INDEX_KEY]
        assert meta["embedding-model"] == MODEL
        assert S3VectorStore._safe_deserialize(raw)["embedding_model"] == MODEL
        assert "vector_index/s3_vector_index.pkl" not in s3.objects  # Titan index untouched

    def test_search_finds_the_matching_chunk(self, local_config, s3, tmp_path):
        vs = store(tmp_path)
        vs.rebuild()
        query = vs.embedder.encode(["oooooo"])[0]
        assert vs.search(query, top_k=1)[0][0] == "upload-0"

    def test_fresh_store_loads_the_uploaded_index(self, local_config, s3, tmp_path):
        store(tmp_path).rebuild()
        vs = store(tmp_path / "other")
        (tmp_path / "other").mkdir()
        vs.ensure_loaded()
        assert len(vs.vectors) == 3

    def test_index_from_another_model_is_refused_not_overwritten(self, local_config, s3, tmp_path):
        titan = {"vectors": np.zeros((1, 3), dtype=np.float32), "metadata": [{"chunk_id": "x"}], "count": 1, "dimension": 3}
        s3.put_object("b", config.VECTOR_INDEX_KEY, S3VectorStore._safe_serialize(titan))  # untagged = Titan
        vs = store(tmp_path)
        with pytest.raises(IndexModelMismatchError, match=LEGACY_INDEX_MODEL):
            vs.load_index()
        # Still the Titan bytes: nothing was rebuilt on top of it.
        assert S3VectorStore._safe_deserialize(s3.objects[config.VECTOR_INDEX_KEY][0])["dimension"] == 3

    def test_stale_local_cache_from_another_model_is_ignored(self, local_config, s3, tmp_path):
        cache = tmp_path / "idx"
        other = {"vectors": np.zeros((1, 3), dtype=np.float32), "metadata": [{"chunk_id": "x"}],
                 "count": 1, "dimension": 3, "embedding_model": "some/other-model"}
        cache.write_bytes(S3VectorStore._safe_serialize(other))
        vs = store(tmp_path)
        vs.load_index()  # no S3 index yet -> ignores the cache, builds from chunks
        assert len(vs.vectors) == 3

    def test_titan_store_still_uses_inline_vectors(self, s3, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "EMBEDDING_PROVIDER", "bedrock")
        monkeypatch.setattr(config, "EMBEDDING_MODEL_ID", config.BEDROCK_EMBEDDING_MODEL_ID)

        class NoEmbedder:
            def encode(self, texts):
                raise AssertionError("Titan builds must not re-embed")

        vs = S3VectorStore(bucket_name="b", index_cache_path=str(tmp_path / "t"), s3_index_key="vector_index/t.pkl",
                           embedder=NoEmbedder())
        assert vs.uses_inline_vectors
        vs._build_index_from_s3()
        assert {cid for cid, _ in vs.vectors} == {"inline-0", "legacy-0"}  # bare .txt has no Titan vector
        assert all(len(vec) == 1024 for _, vec in vs.vectors)


class TestAddRecords:
    def test_add_and_replace(self, local_config, s3, tmp_path):
        vs = store(tmp_path)
        vs.rebuild()
        added = vs.add_records([
            ("new-0", "iiii", {"source_file": "n.pdf", "chunk_index": 0, "s3_key": "chunks/n/chunk_0000.txt"}),
            ("upload-0", "aaaa", {"source_file": "c.pdf", "chunk_index": 0, "s3_key": "chunks/c/chunk_0000.txt"}),
        ])
        assert added == 2
        assert len(vs.vectors) == 4
        query = vs.embedder.encode(["iiiiii"])[0]
        assert vs.search(query, top_k=1)[0][0] == "new-0"
        reloaded = S3VectorStore._safe_deserialize(s3.objects[config.VECTOR_INDEX_KEY][0])
        assert reloaded["count"] == 4

    def test_upload_indexing_writes_text_only_and_appends(self, local_config, s3, tmp_path, monkeypatch):
        from backend import s3_retriever
        from backend.services.indexing_service import IndexingService

        vs = store(tmp_path)
        vs.rebuild()
        monkeypatch.setattr(s3_retriever, "_shared_vector_store", vs)
        service = IndexingService.__new__(IndexingService)
        service.s3, service.bucket, service.redis = s3, "b", None
        progress = []
        created = service._embed_and_upload(
            "r1", "notes.pdf", [("iiii one", {}), ("iiii two", {})], lambda *a, **k: progress.append(a)
        )
        assert created == 2
        new_keys = [k for k in s3.objects if k.startswith("chunks/resources/r1/")]
        assert sorted(new_keys) == ["chunks/resources/r1/notes/chunk_0000.txt", "chunks/resources/r1/notes/chunk_0001.txt"]
        assert not any(k.endswith(".json") for k in new_keys)  # no non-Titan vectors next to Titan ones
        assert len(vs.vectors) == 5
        assert vs.metadata[next(cid for cid, _ in vs.vectors if cid.startswith("notes_"))]["source_file"] == "notes.pdf"


class TestEvaluationTools:
    def test_compare_passes_within_margin_and_fails_beyond(self, tmp_path):
        from backend.scripts.compare_evaluations import main

        def run(path, **scores):
            summary = {f"avg_{k}": v for k, v in scores.items()} | {"evaluated_count": 20}
            log = json.dumps({"level": "INFO", "message": "flushing traces"})
            path.write_text(log + "\n" + json.dumps({"quality_summary": summary, "avg_latency": 2.0}) + "\n" + log + "\n")
            return str(path)

        metrics = dict(faithfulness=0.8, answer_relevance=0.8, context_recall=0.7, context_precision=0.6, correctness=0.7)
        base = run(tmp_path / "b.json", **metrics)
        close = run(tmp_path / "c.json", **(metrics | {"correctness": 0.67}))
        worse = run(tmp_path / "w.json", **(metrics | {"context_recall": 0.6}))
        assert main([base, close, "--max-drop", "0.05"]) == 0
        assert main([base, worse, "--max-drop", "0.05"]) == 1

    def test_fixed_judge_is_strict_and_ignores_answer_fallbacks(self, monkeypatch):
        from backend.openai_compat_llm import OpenAICompatLLM
        from backend.services import rag_quality_evaluator as evaluator

        monkeypatch.setattr(config, "EVAL_JUDGE_PROVIDER", "gemini")
        monkeypatch.setattr(config, "EVAL_JUDGE_MODEL_ID", "gemini-2.5-pro")
        monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
        monkeypatch.setattr(config, "LLM_FALLBACK_PROVIDERS", ["ollama"])
        judge = evaluator._judge_llm("whatever-the-answer-model-is")
        assert isinstance(judge, OpenAICompatLLM)
        assert (judge.provider, judge.model_id) == ("gemini", "gemini-2.5-pro")
        assert judge._attempts() == [(judge.endpoint, "gemini-2.5-pro")]

    def test_no_judge_setting_keeps_the_answer_model(self, monkeypatch):
        from backend.services import rag_quality_evaluator as evaluator

        monkeypatch.setattr(config, "EVAL_JUDGE_PROVIDER", "")
        monkeypatch.setattr(evaluator, "create_llm_client", lambda model_id=None: ("client", model_id))
        assert evaluator._judge_llm("m1") == ("client", "m1")
