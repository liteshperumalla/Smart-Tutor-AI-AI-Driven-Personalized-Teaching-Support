"""AWS Bedrock Embeddings Adapter

Provides embedding generation using AWS Bedrock Titan models.
"""

import boto3
import json
from typing import List, Optional
import numpy as np
from llama_index.core.embeddings import BaseEmbedding
from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)


class BedrockEmbeddings:
    """AWS Bedrock Titan Embeddings wrapper"""

    MAX_INPUT_LENGTH = 8000
    EMBEDDING_DIMENSION = 1024

    def __init__(
        self,
        model_id: str = "amazon.titan-embed-text-v2:0",
        region: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        normalize: bool = True,
        cache_size: int = 1000,
    ):
        self.model_id = model_id
        self.region = region
        self.normalize = normalize
        self.dimension = self.EMBEDDING_DIMENSION
        self.cache_size = cache_size

        client_kwargs = {"region_name": region}
        access_key = aws_access_key_id or config.AWS_ACCESS_KEY_ID
        secret_key = aws_secret_access_key or config.AWS_SECRET_ACCESS_KEY
        session_token = aws_session_token or config.AWS_SESSION_TOKEN
        if access_key and secret_key:
            client_kwargs.update(
                {
                    "aws_access_key_id": access_key,
                    "aws_secret_access_key": secret_key,
                }
            )
            if session_token:
                client_kwargs["aws_session_token"] = session_token

        try:
            self.client = boto3.client("bedrock-runtime", **client_kwargs)
            logger.info(f"✓ Bedrock Embeddings initialized: {model_id} in {region}")
        except Exception as e:
            logger.error(f"✗ Failed to initialize Bedrock embeddings client: {e}")
            raise

        self.total_requests = 0
        self.total_tokens = 0

        from collections import OrderedDict

        self._embedding_cache = OrderedDict()
        self._text_hash_cache = {}

    def _get_text_hash(self, text: str) -> str:
        """Generate a hash for the text for caching purposes"""
        import hashlib

        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def _get_cached_embedding(self, text_hash: str) -> Optional[List[float]]:
        """Get embedding from cache"""
        if text_hash in self._embedding_cache:
            embedding = self._embedding_cache[text_hash]
            self._embedding_cache.move_to_end(text_hash)
            return embedding
        return None

    def _cache_embedding(self, text_hash: str, embedding: List[float]):
        """Cache embedding with LRU eviction"""
        self._embedding_cache[text_hash] = embedding
        if len(self._embedding_cache) > self.cache_size:
            self._embedding_cache.popitem(last=False)

    def encode(
        self,
        texts: List[str],
        batch_size: int = 1,
        show_progress_bar: bool = False,
        **kwargs,
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings for list of texts with caching

        Args:
            texts: List of text strings to embed
            batch_size: Not used (Bedrock processes one at a time)
            show_progress_bar: Not used
            **kwargs: Additional parameters

        Returns:
            List of embedding vectors (each is list of floats)
        """
        embeddings = []
        cache_hits = 0
        cache_misses = 0

        for i, text in enumerate(texts):
            text_hash = self._get_text_hash(text)
            cached = self._get_cached_embedding(text_hash)

            if cached is not None:
                embeddings.append(cached)
                cache_hits += 1
                continue

            cache_misses += 1
            try:
                embedding = self._encode_single(text)
                self._cache_embedding(text_hash, embedding)
                embeddings.append(embedding)

                if (i + 1) % 10 == 0:
                    logger.debug(f"Encoded {i + 1}/{len(texts)} texts")

            except Exception as e:
                logger.error(f"Error encoding text {i}: {e}")
                embeddings.append(None)

        if cache_hits + cache_misses > 0:
            hit_rate = cache_hits / (cache_hits + cache_misses) * 100
            logger.info(
                f"Encoded {len(texts)} texts with Bedrock Titan (cache hit rate: {hit_rate:.1f}%)"
            )
        return embeddings

    def _encode_single(self, text: str) -> List[float]:
        """
        Encode a single text string

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Truncate if too long
        if len(text) > self.MAX_INPUT_LENGTH:
            logger.warning(
                f"Text truncated from {len(text)} to {self.MAX_INPUT_LENGTH} chars"
            )
            text = text[: self.MAX_INPUT_LENGTH]

        request_body = {
            "inputText": text,
            "dimensions": self.dimension,
            "normalize": self.normalize,
        }

        try:
            response = self.client.invoke_model(
                modelId=self.model_id, body=json.dumps(request_body)
            )

            response_body = json.loads(response["body"].read())
            embedding = response_body.get("embedding", [])

            # Update stats
            self.total_requests += 1
            self.total_tokens += len(text.split())  # Rough estimate

            return embedding

        except Exception as e:
            logger.error(f"Bedrock embedding error: {e}")
            raise

    def encode_queries(self, queries: List[str]) -> List[List[float]]:
        """
        Encode queries (alias for encode)

        Args:
            queries: List of query strings

        Returns:
            List of embedding vectors
        """
        return self.encode(queries)

    def encode_corpus(self, corpus: List[str]) -> List[List[float]]:
        """
        Encode corpus documents (alias for encode)

        Args:
            corpus: List of document strings

        Returns:
            List of embedding vectors
        """
        return self.encode(corpus)

    def get_sentence_embedding_dimension(self) -> int:
        """
        Get embedding dimension

        Returns:
            Dimension of embedding vectors
        """
        return self.dimension

    def get_stats(self) -> dict:
        """Get usage statistics"""
        return {
            "model": self.model_id,
            "total_requests": self.total_requests,
            "total_tokens_estimated": self.total_tokens,
            "dimension": self.dimension,
        }


class BedrockEmbeddingsLlamaIndex(BaseEmbedding):
    """
    Wrapper to make BedrockEmbeddings compatible with LlamaIndex

    LlamaIndex expects specific methods and signatures.
    """

    _embeddings: BedrockEmbeddings = None
    _model_id: str = ""
    _region: str = ""

    def __init__(
        self,
        model_id: str = "amazon.titan-embed-text-v2:0",
        region: str = "us-east-1",
        **kwargs,
    ):
        super().__init__(**kwargs)
        object.__setattr__(
            self, "_embeddings", BedrockEmbeddings(model_id=model_id, region=region)
        )
        object.__setattr__(self, "_model_id", model_id)
        object.__setattr__(self, "_region", region)

    def _get_query_embedding(self, query: str) -> List[float]:
        """Get embedding for a query (LlamaIndex compatible)"""
        return self._embeddings.encode([query])[0]

    def _get_text_embedding(self, text: str) -> List[float]:
        """Get embedding for text (LlamaIndex compatible)"""
        return self._embeddings.encode([text])[0]

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for batch of texts (LlamaIndex compatible)"""
        return self._embeddings.encode(texts)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        """Async version of get_query_embedding"""
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        """Async version of get_text_embedding"""
        return self._get_text_embedding(text)


# Convenience function
def create_bedrock_embeddings(
    model_id: Optional[str] = None, for_llamaindex: bool = False
):
    """
    Create Bedrock embeddings instance

    Args:
        model_id: Optional model ID override
        for_llamaindex: If True, return LlamaIndex-compatible wrapper

    Returns:
        BedrockEmbeddings or BedrockEmbeddingsLlamaIndex instance
    """
    model_id = model_id or config.BEDROCK_EMBEDDING_MODEL_ID

    if for_llamaindex:
        return BedrockEmbeddingsLlamaIndex(model_id=model_id, region=config.AWS_REGION)
    else:
        return BedrockEmbeddings(model_id=model_id, region=config.AWS_REGION)
