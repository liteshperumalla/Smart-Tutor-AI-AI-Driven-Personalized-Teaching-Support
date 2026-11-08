"""
S3 Vector Store for RAG
Implements vector similarity search using S3 + local index

Each embedding model has its own index file (``config.VECTOR_INDEX_KEY``),
tagged with the model that made it. Loading an index made by a different
model fails loudly instead of searching mismatched vectors.

Chunks live under ``chunks/`` in the bucket. Their inline ``embedding``
fields are Titan vectors, so a Titan index is built from them directly;
for any other model the chunk text is re-embedded (see ``rebuild``).
"""

import io
import json
import numpy as np
import struct
import threading
from typing import Any, Dict, Iterable, List, Optional, Tuple
from pathlib import Path
from botocore.exceptions import ClientError
from botocore.config import Config
import time

from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)

# Titan indexes predate the model tag, so an untagged index means Titan.
LEGACY_INDEX_MODEL = "amazon.titan-embed-text-v2:0"


class IndexModelMismatchError(RuntimeError):
    """The stored index was made by a different embedding model."""


class S3VectorStore:
    """Vector store that uses S3 for storage with local index for fast search"""

    def __init__(
        self,
        bucket_name: str = None,
        region: str = None,
        index_cache_path: Optional[str] = None,
        s3_index_key: Optional[str] = None,
        embedder: Any = None,
        embedding_model: Optional[str] = None,
    ):
        self.bucket_name = bucket_name or config.S3_DOCUMENTS_BUCKET
        s3_index_key = s3_index_key or config.VECTOR_INDEX_KEY
        # One local cache file per index key, so models never share a cache.
        index_cache_path = index_cache_path or "./" + Path(s3_index_key).name
        self.embedding_model = embedding_model or config.EMBEDDING_MODEL_ID
        # Titan: build from the chunks' inline vectors. Others: re-embed text.
        self.uses_inline_vectors = self.embedding_model == config.BEDROCK_EMBEDDING_MODEL_ID and (
            config.EMBEDDING_PROVIDER == "bedrock"
        )
        self._embedder = embedder
        self.region = region or config.AWS_REGION

        boto_config = Config(
            connect_timeout=120, read_timeout=180, retries={"max_attempts": 3}
        )

        from backend.cloud.aws_helpers import get_s3_client

        # Shared factory: AWS S3, or an S3-compatible store via S3_ENDPOINT_URL.
        client_kwargs = {"config": boto_config}
        if region:
            client_kwargs["region_name"] = region
        self.s3 = get_s3_client(**client_kwargs)
        self.index_cache_path = index_cache_path
        self.s3_index_key = s3_index_key

        self.vectors = []
        self.metadata = {}
        self._numpy_cache = None
        self._chunk_ids_cache = None
        self._loaded = False
        self._load_lock = threading.Lock()

        logger.info(f"S3VectorStore initialized: {self.bucket_name}")

    @staticmethod
    def _default_chunk_s3_key(source_file: str, chunk_index: int) -> str:
        return f"chunks/{source_file}/chunk_{int(chunk_index):04d}.txt"

    @staticmethod
    def _safe_serialize(data: dict) -> bytes:
        """Serialize vectors + metadata without pickle.
        Format: [8-byte meta JSON length][meta JSON bytes][numpy .npy bytes]
        """
        meta = {
            "metadata": [
                {k: v for k, v in m.items() if not isinstance(v, np.generic)}
                for m in data["metadata"]
            ],
            "count": int(data["count"]),
            "dimension": int(data["dimension"]),
        }
        if data.get("embedding_model"):
            meta["embedding_model"] = data["embedding_model"]
        meta_bytes = json.dumps(meta).encode("utf-8")

        vectors_buf = io.BytesIO()
        np.save(vectors_buf, data["vectors"])
        vectors_bytes = vectors_buf.getvalue()

        return struct.pack("<Q", len(meta_bytes)) + meta_bytes + vectors_bytes

    @staticmethod
    def _safe_deserialize(raw: bytes) -> dict:
        """Deserialize vectors + metadata without pickle."""
        meta_len = struct.unpack("<Q", raw[:8])[0]
        meta = json.loads(raw[8 : 8 + meta_len].decode("utf-8"))
        vectors_buf = io.BytesIO(raw[8 + meta_len :])
        vectors = np.load(vectors_buf, allow_pickle=False)
        return {
            "vectors": vectors,
            "metadata": meta["metadata"],
            "count": meta["count"],
            "dimension": meta["dimension"],
            "embedding_model": meta.get("embedding_model"),
        }

    def _check_model(self, data: dict) -> None:
        stored = data.get("embedding_model") or LEGACY_INDEX_MODEL
        if stored != self.embedding_model:
            raise IndexModelMismatchError(
                f"Vector index {self.s3_index_key} was built with {stored}, but the active "
                f"embedding model is {self.embedding_model}. Rebuild it with "
                f"`python -m backend.scripts.rebuild_index` or set VECTOR_INDEX_KEY to that model's index."
            )

    @property
    def embedder(self) -> Any:
        if self._embedder is None:
            from backend.llm_provider import get_shared_embedding_client

            self._embedder = get_shared_embedding_client()
        return self._embedder

    def _populate_from_data(self, data: dict):
        """Populate vectors and metadata from a deserialized data dict."""
        self._check_model(data)
        vectors_array = data["vectors"]
        metadata_list = data["metadata"]

        self.vectors = []
        self.metadata = {}

        for vec, meta in zip(vectors_array, metadata_list):
            chunk_id = meta["chunk_id"]
            self.vectors.append((chunk_id, vec))
            s3_key = meta.get(
                "s3_key",
                self._default_chunk_s3_key(
                    meta.get("source_file", ""),
                    meta.get("chunk_index", 0),
                ),
            )
            self.metadata[chunk_id] = {
                "source_file": meta.get("source_file", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "s3_key": s3_key,
            }

    def _invalidate_cache(self):
        """Invalidate cached numpy arrays"""
        self._numpy_cache = None
        self._chunk_ids_cache = None

    def _build_numpy_cache(self):
        """Build numpy arrays for efficient search"""
        if not self.vectors:
            return
        self._chunk_ids_cache = [item[0] for item in self.vectors]
        self._numpy_cache = np.array([item[1] for item in self.vectors])

    def ensure_loaded(self, force_rebuild: bool = False):
        """Load the index exactly once per process (thread-safe).

        Subsequent calls are no-ops unless force_rebuild is set, so a shared
        store can back many retrievers without re-downloading from S3.
        """
        if self._loaded and not force_rebuild:
            return
        with self._load_lock:
            if self._loaded and not force_rebuild:
                return
            self.load_index(force_rebuild=force_rebuild)
            self._loaded = True

    def load_index(self, force_rebuild: bool = False):
        """
        Load vector index with priority: S3 -> Local cache -> Rebuild

        Args:
            force_rebuild: If True, rebuild index from individual S3 chunks
        """
        cache_path = Path(self.index_cache_path)

        if force_rebuild:
            self._invalidate_cache()

        # A present-but-empty S3 index (0 vectors) must not be treated as a
        # successful load — otherwise retrieval silently returns no sources and
        # the tutor answers without citations. Fall through to rebuild instead.
        if not force_rebuild:
            if self._download_index_from_s3() and self.vectors:
                logger.info(f"✓ Loaded {len(self.vectors)} vectors from S3")
                self._build_numpy_cache()
                return

        if not force_rebuild and cache_path.exists():
            logger.info("S3 index not found, loading from local cache...")
            if self._load_from_local_cache() and self.vectors:
                logger.info(f"✓ Loaded {len(self.vectors)} vectors from local cache")
                self._build_numpy_cache()
                self._upload_index_to_s3()
                return

        logger.info("No cached index found. Building from S3 chunks...")
        self._build_index_from_s3()
        self._save_index_cache()
        self._upload_index_to_s3()
        self._build_numpy_cache()

    def _load_from_local_cache(self) -> bool:
        """Load index from local cache file. Returns True if successful."""
        try:
            cache_path = Path(self.index_cache_path)
            raw = cache_path.read_bytes()
            data = self._safe_deserialize(raw)
            self._populate_from_data(data)
            return True
        except IndexModelMismatchError as e:
            # A stale cache from another model: ignore it, never search it.
            logger.warning(f"Ignoring local index cache: {e}")
            return False
        except Exception as e:
            logger.warning(f"Failed to load from local cache: {e}")
            return False

    def _download_index_from_s3(self) -> bool:
        """
        Download prebuilt vector index from S3
        Returns True if successful, False otherwise
        """
        try:
            logger.info(f"Checking for vector index in S3: {self.s3_index_key}")

            response = self.s3.get_object(
                Bucket=self.bucket_name, Key=self.s3_index_key
            )
            raw = response["Body"].read()

            data = self._safe_deserialize(raw)
            self._populate_from_data(data)

            # Save to local cache for faster subsequent loads
            cache_path = Path(self.index_cache_path)
            cache_path.write_bytes(raw)

            logger.info("Downloaded index from S3 and cached locally")
            return True

        except IndexModelMismatchError:
            # Never rebuild over (and upload on top of) another model's index.
            raise
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.info("Vector index not found in S3")
                return False
            else:
                logger.warning(f"Failed to download index from S3: {e}")
                return False
        except Exception as e:
            logger.warning(f"Failed to download index from S3: {e}")
            return False

    def _index_payload(self) -> dict:
        vectors_array = np.array([vec for _, vec in self.vectors])
        metadata_list = [
            {
                "chunk_id": chunk_id,
                "source_file": self.metadata[chunk_id].get("source_file", ""),
                "chunk_index": self.metadata[chunk_id].get("chunk_index", 0),
                "s3_key": self.metadata[chunk_id].get(
                    "s3_key",
                    self._default_chunk_s3_key(
                        self.metadata[chunk_id].get("source_file", ""),
                        self.metadata[chunk_id].get("chunk_index", 0),
                    ),
                ),
            }
            for chunk_id, _ in self.vectors
        ]
        return {
            "vectors": vectors_array,
            "metadata": metadata_list,
            "count": len(self.vectors),
            "dimension": len(vectors_array[0]) if len(vectors_array) > 0 else 0,
            "embedding_model": self.embedding_model,
        }

    def _upload_index_to_s3(self):
        """Upload the current index to S3 for sharing across instances"""
        try:
            logger.info(f"Uploading vector index to S3: {self.s3_index_key}")

            data = self._index_payload()
            vectors_array = data["vectors"]

            index_bytes = self._safe_serialize(data)

            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=self.s3_index_key,
                Body=index_bytes,
                ContentType="application/octet-stream",
                Metadata={
                    "vector_count": str(len(self.vectors)),
                    "dimension": str(
                        len(vectors_array[0]) if len(vectors_array) > 0 else 0
                    ),
                    "embedding-model": self.embedding_model,
                },
            )

            size_mb = len(index_bytes) / (1024 * 1024)
            logger.info(f"Uploaded index to S3 ({size_mb:.1f} MB)")

        except Exception as e:
            logger.error(f"Failed to upload index to S3: {e}")

    def _build_index_from_s3(self):
        """Build the index from the chunks in S3, for the active model."""
        if self.uses_inline_vectors:
            self._build_index_from_inline_vectors()
        else:
            self._build_index_by_embedding()

    def rebuild(self) -> int:
        """Rebuild the index from the chunks, save it locally and upload it.

        Returns the number of vectors. For a non-Titan model this embeds
        every chunk, which takes minutes on CPU, so run it ahead of time
        (python -m backend.scripts.rebuild_index) rather than on a user's first query.
        """
        with self._load_lock:
            self._invalidate_cache()
            self._build_index_from_s3()
            if not self.vectors:
                raise RuntimeError(f"No chunks found under chunks/ in {self.bucket_name}")
            self._save_index_cache()
            self._upload_index_to_s3()
            self._build_numpy_cache()
            self._loaded = True
        return len(self.vectors)

    def list_chunk_records(self) -> List[str]:
        """Keys of the chunks to index: one per chunk, whatever its layout.

        ``<name>.json`` (text + Titan vector inline), ``<name>.vector.json``
        (Titan vector; text in a sibling ``.txt``) and a bare ``<name>.txt``
        (text only, written by uploads when the model isn't Titan).
        """
        paginator = self.s3.get_paginator("list_objects_v2")
        keys = [
            obj["Key"]
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix="chunks/")
            for obj in page.get("Contents", [])
        ]
        key_set = set(keys)
        records = []
        for key in keys:
            if key.endswith(".json"):
                records.append(key)
            elif key.endswith(".txt") and key[: -len(".txt")] + ".vector.json" not in key_set:
                records.append(key)
        return records

    def _read_chunk_record(self, key: str) -> Optional[Tuple[str, str, Dict]]:
        """(chunk_id, text, metadata) for one chunk record, or None to skip."""
        response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
        raw = response["Body"].read()
        if key.endswith(".txt"):
            meta = response.get("Metadata", {}) or {}
            text = raw.decode("utf-8")
            chunk_id = meta.get("chunk-id") or key
            return chunk_id, text, {
                "source_file": meta.get("source-file", ""),
                "chunk_index": int(meta.get("chunk-index", 0) or 0),
                "s3_key": key,
            }
        data = json.loads(raw)
        chunk_id = data.get("chunk_id") or key
        if key.endswith(".vector.json"):
            text_key = key.replace(".vector.json", ".txt")
            text = self.s3.get_object(Bucket=self.bucket_name, Key=text_key)["Body"].read().decode("utf-8")
        else:
            text_key = key
            text = data.get("text", "")
        if not text.strip():
            return None
        return chunk_id, text, {
            "source_file": data.get("source_file", ""),
            "chunk_index": data.get("chunk_index", 0),
            "s3_key": text_key,
        }

    def _build_index_by_embedding(self) -> None:
        """Embed every chunk's text with the active model."""
        from concurrent.futures import ThreadPoolExecutor

        logger.info(f"Building {self.embedding_model} index by re-embedding chunk text...")
        keys = self.list_chunk_records()

        def _read(key):
            try:
                return self._read_chunk_record(key)
            except Exception as e:
                logger.warning(f"Error reading chunk {key}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=32) as executor:
            records = [r for r in executor.map(_read, keys) if r is not None]

        self.vectors = []
        self.metadata = {}
        self.add_records(records, persist=False)
        logger.info(f"✓ Built index with {len(self.vectors)} vectors ({self.embedding_model})")

    def add_records(self, records: Iterable[Tuple[str, str, Dict]], persist: bool = True) -> int:
        """Embed and add (chunk_id, text, metadata) records to the index.

        Re-adding a chunk_id replaces its vector. With ``persist`` the index
        is saved and uploaded afterwards (used by uploads, so new documents
        are searchable without a full rebuild).
        """
        records = list(records)
        batch_size = max(1, int(getattr(config, "EMBEDDING_BATCH_SIZE", 32)) * 8)
        positions = {chunk_id: i for i, (chunk_id, _) in enumerate(self.vectors)}
        added = 0
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            vectors = self.embedder.encode([text for _, text, _ in batch])
            for (chunk_id, _, meta), vector in zip(batch, vectors):
                if vector is None:
                    continue
                vec = np.asarray(vector, dtype=np.float32)
                if chunk_id in positions:
                    self.vectors[positions[chunk_id]] = (chunk_id, vec)
                else:
                    positions[chunk_id] = len(self.vectors)
                    self.vectors.append((chunk_id, vec))
                self.metadata[chunk_id] = meta
                added += 1
            logger.info(f"  Embedded {min(start + batch_size, len(records))}/{len(records)} chunks")
        self._invalidate_cache()
        if persist and added:
            self._save_index_cache()
            self._upload_index_to_s3()
            self._build_numpy_cache()
        return added

    def _build_index_from_inline_vectors(self):
        """Build index by downloading all chunk embeddings from S3.

        Supports two on-disk chunk layouts:
          * ``<name>.json`` — current format: embedding **and** text inline.
            The text is fetched at query time from this same key, so ``s3_key``
            points at the file itself.
          * ``<name>.vector.json`` — legacy format: embedding only, with the
            text in a sibling ``<name>.txt``.

        Chunks without an ``embedding`` field are skipped (e.g. raw text-only
        exports), so a partially-embedded corpus still yields a usable index.
        """
        self.vectors = []
        self.metadata = {}

        # Download + parse chunks in parallel — a full corpus is tens of
        # thousands of small objects, and sequential GETs make a cold rebuild
        # take minutes instead of seconds.
        from concurrent.futures import ThreadPoolExecutor, as_completed

        paginator = self.s3.get_paginator("list_objects_v2")
        keys = [
            obj["Key"]
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix="chunks/")
            for obj in page.get("Contents", [])
            if obj["Key"].endswith(".json")
        ]

        def _load(key):
            try:
                vector_data = json.loads(
                    self.s3.get_object(Bucket=self.bucket_name, Key=key)["Body"].read()
                )
                embedding = vector_data.get("embedding")
                if not embedding:
                    return None
                chunk_id = vector_data.get("chunk_id") or key
                # Legacy ".vector.json" stores text in a sibling ".txt"; the
                # current ".json" format keeps it inline, so reuse the key.
                text_key = (
                    key.replace(".vector.json", ".txt")
                    if key.endswith(".vector.json")
                    else key
                )
                return chunk_id, np.array(embedding, dtype=np.float32), {
                    "source_file": vector_data.get("source_file", ""),
                    "chunk_index": vector_data.get("chunk_index", 0),
                    "s3_key": text_key,
                }
            except Exception as e:
                logger.warning(f"Error loading vector {key}: {e}")
                return None

        vector_count = 0
        with ThreadPoolExecutor(max_workers=32) as executor:
            for future in as_completed(
                {executor.submit(_load, key): key for key in keys}
            ):
                result = future.result()
                if result is None:
                    continue
                chunk_id, vec, meta = result
                self.vectors.append((chunk_id, vec))
                self.metadata[chunk_id] = meta
                vector_count += 1
                if vector_count % 1000 == 0:
                    logger.info(f"  Loaded {vector_count} vectors...")

        logger.info(f"✓ Built index with {len(self.vectors)} vectors")

    def _save_index_cache(self) -> bool:
        """Save index to cache for faster loading"""
        cache_path = Path(self.index_cache_path)
        try:
            data = self._index_payload()
            cache_path.write_bytes(self._safe_serialize(data))
            logger.info(f"Saved index cache to {cache_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save index cache to {cache_path}: {e}")
            return False

    def search(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[Tuple[str, float, Dict]]:
        """
        Search for most similar vectors using cosine similarity

        Args:
            query_embedding: Query vector (1024-dim)
            top_k: Number of results to return

        Returns:
            List of (chunk_id, similarity_score, metadata) tuples
        """
        if not self.vectors:
            logger.warning("Index is empty. Call load_index() first.")
            return []

        query_vec = np.array(query_embedding)

        if self._numpy_cache is not None:
            vectors_array = self._numpy_cache
            chunk_ids = self._chunk_ids_cache
        else:
            chunk_ids = [item[0] for item in self.vectors]
            vectors_array = np.array([item[1] for item in self.vectors])

        query_norm = np.linalg.norm(query_vec)
        vectors_norm = np.linalg.norm(vectors_array, axis=1)

        dot_products = np.dot(vectors_array, query_vec)

        denominators = query_norm * vectors_norm
        denominators[denominators == 0] = 1e-12

        similarities_array = dot_products / denominators
        similarities_array[denominators == 1e-12] = 0.0

        similarities = [
            (chunk_ids[i], float(similarities_array[i])) for i in range(len(chunk_ids))
        ]
        similarities.sort(key=lambda x: x[1], reverse=True)

        results = []
        for chunk_id, score in similarities[:top_k]:
            metadata = self.metadata.get(chunk_id, {})
            results.append((chunk_id, score, metadata))

        return results

    def get_chunk_text(self, chunk_id: str) -> str:
        """Retrieve chunk text from S3 JSON file"""
        metadata = self.metadata.get(chunk_id)
        if not metadata:
            return ""

        s3_key = metadata.get("s3_key", "")
        if not s3_key:
            return ""

        try:
            response = self.s3.get_object(Bucket=self.bucket_name, Key=s3_key)
            content = response["Body"].read().decode("utf-8")

            # Parse JSON if it's a JSON file
            if s3_key.endswith(".json"):
                import json

                chunk_data = json.loads(content)
                # Try to get text from various possible fields
                text = chunk_data.get("text", "")
                if not text:
                    # Fallback: use source_file info as context
                    source = chunk_data.get("source_file", "")
                    if source:
                        text = f"[Content from {source}]"
                return text
            else:
                return content
        except Exception as e:
            logger.error(f"Error retrieving chunk {chunk_id}: {e}")
            return ""

    def get_chunk_texts(self, chunk_ids: List[str]) -> Dict[str, str]:
        """Retrieve multiple chunk texts from S3 in parallel"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        texts = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_chunk_id = {
                executor.submit(self.get_chunk_text, chunk_id): chunk_id
                for chunk_id in chunk_ids
            }
            for future in as_completed(future_to_chunk_id):
                chunk_id = future_to_chunk_id[future]
                try:
                    text = future.result()
                    if text:
                        texts[chunk_id] = text
                except Exception as exc:
                    logger.error(f"Error retrieving chunk {chunk_id} in batch: {exc}")
        return texts

    def get_stats(self) -> Dict:
        """Get statistics about the vector store"""
        return {
            "total_vectors": len(self.vectors),
            "bucket": self.bucket_name,
            "index_cached": Path(self.index_cache_path).exists(),
        }
