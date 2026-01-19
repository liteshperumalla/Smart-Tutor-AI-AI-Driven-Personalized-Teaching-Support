"""
S3 Vector Store for RAG
Implements vector similarity search using S3 + local index
"""

import boto3
import json
import numpy as np
from typing import List, Dict, Tuple
from pathlib import Path
import pickle
from botocore.exceptions import ClientError
from botocore.config import Config
import time

from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)


class S3VectorStore:
    """Vector store that uses S3 for storage with local index for fast search"""

    def __init__(
        self,
        bucket_name: str = None,
        region: str = None,
        index_cache_path: str = "./s3_vector_index.pkl",
        s3_index_key: str = "vector_index/s3_vector_index.pkl",
    ):
        self.bucket_name = bucket_name or config.S3_DOCUMENTS_BUCKET
        self.region = region or config.AWS_REGION

        boto_config = Config(
            connect_timeout=120, read_timeout=180, retries={"max_attempts": 3}
        )

        client_kwargs = {"region_name": self.region, "config": boto_config}
        if config.AWS_ACCESS_KEY_ID and config.AWS_SECRET_ACCESS_KEY:
            client_kwargs["aws_access_key_id"] = config.AWS_ACCESS_KEY_ID
            client_kwargs["aws_secret_access_key"] = config.AWS_SECRET_ACCESS_KEY
            if config.AWS_SESSION_TOKEN:
                client_kwargs["aws_session_token"] = config.AWS_SESSION_TOKEN
        self.s3 = boto3.client("s3", **client_kwargs)
        self.index_cache_path = index_cache_path
        self.s3_index_key = s3_index_key

        self.vectors = []
        self.metadata = {}
        self._numpy_cache = None
        self._chunk_ids_cache = None

        logger.info(f"S3VectorStore initialized: {self.bucket_name}")

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

    def load_index(self, force_rebuild: bool = False):
        """
        Load vector index with priority: S3 -> Local cache -> Rebuild

        Args:
            force_rebuild: If True, rebuild index from individual S3 chunks
        """
        cache_path = Path(self.index_cache_path)

        if force_rebuild:
            self._invalidate_cache()

        if not force_rebuild:
            if self._download_index_from_s3():
                logger.info(f"✓ Loaded {len(self.vectors)} vectors from S3")
                self._build_numpy_cache()
                return

        if not force_rebuild and cache_path.exists():
            logger.info("S3 index not found, loading from local cache...")
            if self._load_from_local_cache():
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
        """Load index from local pickle file. Returns True if successful."""
        try:
            cache_path = Path(self.index_cache_path)
            with open(cache_path, "rb") as f:
                data = pickle.load(f)

                # Handle format from rebuild_vector_index.py
                if isinstance(data["vectors"], np.ndarray):
                    # Convert from NumPy array format to list of tuples
                    vectors_array = data["vectors"]
                    metadata_list = data["metadata"]

                    self.vectors = []
                    self.metadata = {}

                    for i, (vec, meta) in enumerate(zip(vectors_array, metadata_list)):
                        chunk_id = meta["chunk_id"]
                        self.vectors.append((chunk_id, vec))
                        # Use s3_key from metadata if available, otherwise construct default
                        s3_key = meta.get(
                            "s3_key",
                            f"chunks/{meta.get('source_file', '')}/chunk_{meta.get('chunk_index', 0):03d}.txt",
                        )
                        self.metadata[chunk_id] = {
                            "source_file": meta.get("source_file", ""),
                            "chunk_index": meta.get("chunk_index", 0),
                            "s3_key": s3_key,
                        }
                else:
                    # Old format (list of tuples)
                    self.vectors = data["vectors"]
                    self.metadata = data["metadata"]

            return True
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

            # Download from S3
            response = self.s3.get_object(
                Bucket=self.bucket_name, Key=self.s3_index_key
            )
            index_data = response["Body"].read()

            # Load pickle data
            data = pickle.loads(index_data)

            # Handle different formats
            if isinstance(data["vectors"], np.ndarray):
                # Convert from NumPy array format
                vectors_array = data["vectors"]
                metadata_list = data["metadata"]

                self.vectors = []
                self.metadata = {}

                for i, (vec, meta) in enumerate(zip(vectors_array, metadata_list)):
                    chunk_id = meta["chunk_id"]
                    self.vectors.append((chunk_id, vec))
                    # Use s3_key from metadata if available, otherwise construct default
                    s3_key = meta.get(
                        "s3_key",
                        f"chunks/{meta.get('source_file', '')}/chunk_{meta.get('chunk_index', 0):03d}.txt",
                    )
                    self.metadata[chunk_id] = {
                        "source_file": meta.get("source_file", ""),
                        "chunk_index": meta.get("chunk_index", 0),
                        "s3_key": s3_key,
                    }
            else:
                # Old format (list of tuples)
                self.vectors = data["vectors"]
                self.metadata = data["metadata"]

            # Save to local cache for faster subsequent loads
            cache_path = Path(self.index_cache_path)
            with open(cache_path, "wb") as f:
                pickle.dump(data, f)

            logger.info(f"✓ Downloaded index from S3 and cached locally")
            return True

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

    def _upload_index_to_s3(self):
        """Upload the current index to S3 for sharing across instances"""
        try:
            logger.info(f"Uploading vector index to S3: {self.s3_index_key}")

            # Prepare data in NumPy format (more compact)
            vectors_array = np.array([vec for _, vec in self.vectors])
            metadata_list = [
                {
                    "chunk_id": chunk_id,
                    "source_file": self.metadata[chunk_id].get("source_file", ""),
                    "chunk_index": self.metadata[chunk_id].get("chunk_index", 0),
                }
                for chunk_id, _ in self.vectors
            ]

            data = {
                "vectors": vectors_array,
                "metadata": metadata_list,
                "count": len(self.vectors),
                "dimension": len(vectors_array[0]) if len(vectors_array) > 0 else 0,
            }

            # Serialize to pickle
            index_bytes = pickle.dumps(data)

            # Upload to S3
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
                    "created_at": str(Path(self.index_cache_path).stat().st_mtime),
                },
            )

            size_mb = len(index_bytes) / (1024 * 1024)
            logger.info(f"✓ Uploaded index to S3 ({size_mb:.1f} MB)")

        except Exception as e:
            logger.error(f"Failed to upload index to S3: {e}")
            # Don't fail the whole operation if upload fails

    def _build_index_from_s3(self):
        """Build index by downloading all vectors from S3"""
        self.vectors = []
        self.metadata = {}

        # List all vector files in S3
        paginator = self.s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=self.bucket_name, Prefix="chunks/")

        vector_count = 0
        for page in pages:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                key = obj["Key"]

                # Only process .vector.json files
                if not key.endswith(".vector.json"):
                    continue

                try:
                    # Download vector file
                    response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
                    vector_data = json.loads(response["Body"].read())

                    chunk_id = vector_data["chunk_id"]
                    embedding = vector_data["embedding"]

                    self.vectors.append((chunk_id, np.array(embedding)))
                    self.metadata[chunk_id] = {
                        "source_file": vector_data.get("source_file", ""),
                        "chunk_index": vector_data.get("chunk_index", 0),
                        "s3_key": key.replace(".vector.json", ".txt"),
                    }

                    vector_count += 1
                    if vector_count % 100 == 0:
                        logger.info(f"  Loaded {vector_count} vectors...")

                except Exception as e:
                    logger.warning(f"Error loading vector {key}: {e}")

        logger.info(f"✓ Built index with {len(self.vectors)} vectors")

    def _save_index_cache(self) -> bool:
        """Save index to cache for faster loading"""
        cache_path = Path(self.index_cache_path)
        try:
            # Prepare data in NumPy format (more compact)
            vectors_array = np.array([vec for _, vec in self.vectors])
            metadata_list = [
                {
                    "chunk_id": chunk_id,
                    "source_file": self.metadata[chunk_id].get("source_file", ""),
                    "chunk_index": self.metadata[chunk_id].get("chunk_index", 0),
                }
                for chunk_id, _ in self.vectors
            ]

            data = {
                "vectors": vectors_array,
                "metadata": metadata_list,
                "count": len(self.vectors),
                "dimension": len(vectors_array[0]) if len(vectors_array) > 0 else 0,
            }

            with open(cache_path, "wb") as f:
                pickle.dump(data, f)
            logger.info(f"✓ Saved index cache to {cache_path}")
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
