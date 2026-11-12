"""Resumable index rebuilds and the rebuild script's --check (staging re-index)."""

import numpy as np
import pytest

from backend.config import config
from backend.local_embeddings import LocalEmbeddings, _cpu_threads
from backend.s3_vector_store import IndexModelMismatchError, S3VectorStore
from backend.tests.test_local_embeddings_index import MODEL, FakeModel, local_config, s3  # noqa: F401


class Interrupt(Exception):
    pass


def make_store(tmp_path, model):
    return S3VectorStore(bucket_name="b", index_cache_path=str(tmp_path / "idx"), embedder=LocalEmbeddings(model=model))


class TestResumableRebuild:
    def test_an_interrupted_rebuild_resumes_from_its_checkpoint(self, local_config, s3, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "EMBEDDING_BATCH_SIZE", 1 / 8)  # one chunk per batch
        ckpt = str(tmp_path / "rebuild.ckpt")
        first_model = FakeModel()

        class Flaky(FakeModel):
            def encode(self, texts, **kwargs):
                if len(first_model.calls) == 2:
                    raise Interrupt("killed")
                return first_model.encode(texts, **kwargs)

        with pytest.raises(Interrupt):
            make_store(tmp_path, Flaky()).rebuild(checkpoint_path=ckpt, checkpoint_every=0)
        assert (tmp_path / "rebuild.ckpt").exists()

        second_model = FakeModel()
        vs = make_store(tmp_path, second_model)
        assert vs.rebuild(checkpoint_path=ckpt, checkpoint_every=0) == 3
        # Only the chunk that wasn't embedded before the kill is embedded again.
        assert sum(len(c) for c in second_model.calls) == 1
        assert {cid for cid, _ in vs.vectors} == {"inline-0", "legacy-0", "upload-0"}
        assert not (tmp_path / "rebuild.ckpt").exists()  # removed after the upload
        assert config.VECTOR_INDEX_KEY in s3.objects

    def test_changed_text_is_re_embedded(self, local_config, s3, tmp_path):
        ckpt = str(tmp_path / "rebuild.ckpt")
        # A finished embedding pass whose checkpoint was kept (upload never ran).
        make_store(tmp_path, FakeModel())._build_index_by_embedding(checkpoint_path=ckpt, checkpoint_every=0)
        s3.put_object("b", "chunks/c/chunk_0000.txt", b"iiii kiwi", Metadata={"chunk-id": "upload-0"})
        model = FakeModel()
        make_store(tmp_path, model).rebuild(checkpoint_path=ckpt)
        assert model.calls == [["iiii kiwi"]]

    def test_a_checkpoint_from_another_model_is_ignored(self, local_config, s3, tmp_path, monkeypatch):
        ckpt = str(tmp_path / "rebuild.ckpt")
        other = make_store(tmp_path, FakeModel())
        other.embedding_model = "some/other-model"
        other.vectors = [("inline-0", np.ones(4, dtype=np.float32))]
        other._save_checkpoint(ckpt, {"inline-0": other._text_hash("aaaa banana")})
        model = FakeModel()
        make_store(tmp_path, model).rebuild(checkpoint_path=ckpt)
        assert sum(len(c) for c in model.calls) == 3

    def test_a_corrupt_checkpoint_is_ignored(self, local_config, s3, tmp_path):
        ckpt = tmp_path / "rebuild.ckpt"
        ckpt.write_bytes(b"\x00garbage")
        assert make_store(tmp_path, FakeModel()).rebuild(checkpoint_path=str(ckpt)) == 3


class TestIndexCheck:
    def test_index_exists_once_built(self, local_config, s3, tmp_path):
        vs = make_store(tmp_path, FakeModel())
        assert vs.index_exists() is False
        vs.rebuild()
        assert make_store(tmp_path, FakeModel()).index_exists() is True

    def test_another_models_index_raises(self, local_config, s3, tmp_path):
        titan = {"vectors": np.zeros((1, 3), dtype=np.float32), "metadata": [{"chunk_id": "x"}], "count": 1, "dimension": 3}
        s3.put_object("b", config.VECTOR_INDEX_KEY, S3VectorStore._safe_serialize(titan))
        with pytest.raises(IndexModelMismatchError):
            make_store(tmp_path, FakeModel()).index_exists()

    def test_script_check_exit_codes(self, local_config, s3, tmp_path, monkeypatch):
        from backend.scripts import rebuild_index

        monkeypatch.setattr(config, "S3_DOCUMENTS_BUCKET", "b")
        import backend.llm_provider as lp

        monkeypatch.setattr(lp, "get_shared_embedding_client", lambda: LocalEmbeddings(model=FakeModel()))
        monkeypatch.chdir(tmp_path)
        assert rebuild_index.main(["--check"]) == 3
        assert rebuild_index.main(["--checkpoint", str(tmp_path / "c.ckpt")]) == 0
        assert rebuild_index.main(["--check"]) == 0


class TestThreads:
    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_NUM_THREADS", "3")
        assert _cpu_threads() == 3

    def test_defaults_to_a_positive_count(self, monkeypatch):
        monkeypatch.delenv("EMBEDDING_NUM_THREADS", raising=False)
        assert _cpu_threads() >= 1


def test_an_unwritable_checkpoint_does_not_stop_the_rebuild(local_config, s3, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    ckpt = str(blocker / "sub" / "rebuild.ckpt")  # parent is a file: can't be created
    assert make_store(tmp_path, FakeModel()).rebuild(checkpoint_path=ckpt, checkpoint_every=0) == 3
