"""LLM Provider Abstraction Layer

Provides a unified interface for switching between different LLM and embedding providers:

LLM Providers:
- AWS Bedrock (Claude, Llama, etc.)
- OpenRouter, Groq, Gemini, any OpenAI-compatible API (backend/openai_compat_llm.py)
- Ollama (local models)

Embedding Providers:
- AWS Bedrock (Titan Embeddings)
- HuggingFace/Local (SentenceTransformer models)

This allows easy switching via configuration without code changes.
"""

from enum import Enum
from typing import Optional, Any
from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers"""
    BEDROCK = "bedrock"
    OPENROUTER = "openrouter"
    GROQ = "groq"
    GEMINI = "gemini"
    OPENAI_COMPAT = "openai_compat"
    OLLAMA = "ollama"
    HUGGINGFACE = "huggingface"  # Local embeddings using SentenceTransformer
    LOCAL = "local"  # Alias for HUGGINGFACE


class LLMFactory:
    """Factory for creating LLM and embedding instances"""

    @staticmethod
    def create_llm(provider: Optional[str] = None, **kwargs) -> Any:
        """
        Create LLM instance based on provider

        Args:
            provider: LLM provider name (bedrock, openrouter, groq, gemini, openai_compat, ollama).
                Uses config if not specified.
            **kwargs: Additional parameters for the LLM

        Returns:
            LLM instance

        Raises:
            ValueError: If unknown provider
        """
        provider = provider or config.LLM_PROVIDER

        logger.info(f"Creating LLM with provider: {provider}")

        if provider == LLMProvider.BEDROCK.value:
            return LLMFactory._create_bedrock_llm(**kwargs)

        elif provider in _OPENAI_COMPAT_LLMS:
            return LLMFactory._create_openai_compat_llm(provider, **kwargs)

        elif provider == LLMProvider.OLLAMA.value:
            return LLMFactory._create_ollama_llm(**kwargs)

        else:
            raise ValueError(
                f"Unknown LLM provider: {provider}. "
                f"Supported: {[p.value for p in LLMProvider]}"
            )

    @staticmethod
    def _create_bedrock_llm(**kwargs) -> Any:
        """Create AWS Bedrock LLM instance (LlamaIndex-compatible)"""
        try:
            from backend.bedrock_llamaindex import BedrockLLM

            model_id = kwargs.get('model_id', config.BEDROCK_MODEL_ID)
            region = kwargs.get('region', config.AWS_REGION)

            logger.info(f"✓ Using AWS Bedrock for LLM: {model_id}")

            return BedrockLLM(
                model_id=model_id,
                region=region
            )

        except ImportError as e:
            logger.error(f"Failed to import BedrockLLM: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to create Bedrock LLM: {e}", exc_info=True)
            raise

    @staticmethod
    def _create_openai_compat_llm(provider: str, **kwargs) -> Any:
        """Create a LlamaIndex LLM for Groq / Gemini / an OpenAI-compatible API."""
        from backend.llamaindex_compat import OpenAICompatLlamaIndexLLM

        model_id = kwargs.get("model_id")
        if not model_id and provider == config.LLM_PROVIDER:
            model_id = config.LLM_MODEL_ID or None
        # model_id None = that provider's own default model.
        logger.info(f"✓ Using {provider} for LLM: {model_id}")
        return OpenAICompatLlamaIndexLLM(model_id=model_id, provider=provider)

    @staticmethod
    def _create_ollama_llm(**kwargs) -> Any:
        """Create Ollama local LLM instance"""
        try:
            from llama_index.llms.ollama import Ollama

            model = kwargs.get('model') or kwargs.get('model_id') or config.LLM_MODEL
            base_url = kwargs.get('base_url', config.OLLAMA_BASE_URL)
            timeout = kwargs.get('request_timeout', config.LLM_REQUEST_TIMEOUT)

            logger.info(f"✓ Using Ollama for LLM (local): {model}")

            return Ollama(
                model=model,
                base_url=base_url,
                request_timeout=timeout
            )

        except ImportError as e:
            logger.error(f"Failed to import Ollama: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to create Ollama LLM: {e}", exc_info=True)
            raise

    @staticmethod
    def create_embeddings(provider: Optional[str] = None, **kwargs) -> Any:
        """
        Create embeddings instance based on provider

        Args:
            provider: Embedding provider (bedrock, ollama). Uses config if not specified.
            **kwargs: Additional parameters

        Returns:
            Embeddings instance

        Raises:
            ValueError: If unknown provider
        """
        provider = provider or config.EMBEDDING_PROVIDER

        logger.info(f"Creating embeddings with provider: {provider}")

        if provider == LLMProvider.BEDROCK.value:
            return LLMFactory._create_bedrock_embeddings(**kwargs)

        elif provider in (LLMProvider.HUGGINGFACE.value, LLMProvider.LOCAL.value):
            return LLMFactory._create_huggingface_embeddings(**kwargs)

        elif provider == LLMProvider.OLLAMA.value:
            # Backwards compatibility: OLLAMA maps to HuggingFace for embeddings
            logger.warning(
                f"Provider 'ollama' for embeddings is deprecated. "
                f"Use 'huggingface' or 'local' instead."
            )
            return LLMFactory._create_huggingface_embeddings(**kwargs)

        else:
            raise ValueError(
                f"Unknown embedding provider: {provider}. "
                f"Supported: {[p.value for p in LLMProvider]}"
            )

    @staticmethod
    def _create_bedrock_embeddings(**kwargs) -> Any:
        """Create AWS Bedrock Titan embeddings instance"""
        try:
            from backend.bedrock_embeddings import create_bedrock_embeddings

            model_id = kwargs.get('model_id', config.BEDROCK_EMBEDDING_MODEL_ID)
            # Default to True for LlamaIndex compatibility
            for_llamaindex = kwargs.get('for_llamaindex', True)

            logger.info(f"✓ Using AWS Bedrock for embeddings: {model_id}")

            return create_bedrock_embeddings(
                model_id=model_id,
                for_llamaindex=for_llamaindex
            )

        except ImportError as e:
            logger.error(f"Failed to import Bedrock embeddings: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to create Bedrock embeddings: {e}", exc_info=True)
            raise

    @staticmethod
    def _create_huggingface_embeddings(**kwargs) -> Any:
        """Create HuggingFace (local) embeddings instance"""
        try:
            from sentence_transformers import SentenceTransformer

            model_name = kwargs.get('model_name', config.EMBEDDING_MODEL)

            logger.info(f"✓ Using HuggingFace for embeddings (local): {model_name}")

            return SentenceTransformer(model_name)

        except ImportError as e:
            logger.error(f"Failed to import SentenceTransformer: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to create HuggingFace embeddings: {e}", exc_info=True)
            raise

    @staticmethod
    def get_provider_info() -> dict:
        """Get information about current provider configuration"""
        return {
            "llm_provider": config.LLM_PROVIDER,
            "embedding_provider": config.EMBEDDING_PROVIDER,
            "bedrock": {
                "model_id": config.BEDROCK_MODEL_ID,
                "embedding_model_id": config.BEDROCK_EMBEDDING_MODEL_ID,
                "region": config.AWS_REGION,
                "enabled": config.LLM_PROVIDER == LLMProvider.BEDROCK.value
            },
            "openai_compat": {
                "model_id": config.LLM_MODEL_ID,
                "fallback_providers": config.LLM_FALLBACK_PROVIDERS,
                "enabled": config.LLM_PROVIDER in _OPENAI_COMPAT_LLMS,
            },
            "ollama": {
                "model": config.LLM_MODEL,
                "base_url": config.OLLAMA_BASE_URL,
                "embedding_model": config.EMBEDDING_MODEL,
                "enabled": config.LLM_PROVIDER == LLMProvider.OLLAMA.value
            }
        }


_OPENAI_COMPAT_LLMS = (
    LLMProvider.OPENROUTER.value,
    LLMProvider.GROQ.value,
    LLMProvider.GEMINI.value,
    LLMProvider.OPENAI_COMPAT.value,
)


def create_llm_client(model_id: Optional[str] = None, provider: Optional[str] = None) -> Any:
    """Direct (non-LlamaIndex) LLM client for the active provider.

    Returns an object with ``generate`` / ``stream_generate`` / ``get_stats``
    and a ``model_id`` attribute: ``BedrockLLM`` when LLM_PROVIDER=bedrock,
    otherwise ``OpenAICompatLLM`` (OpenRouter, Groq, Gemini, Ollama, any OpenAI-compatible
    endpoint). Use this instead of constructing ``BedrockLLM`` directly.
    """
    provider = (provider or config.LLM_PROVIDER).lower()
    if provider == LLMProvider.BEDROCK.value:
        from backend.bedrock_llm import BedrockLLM

        return BedrockLLM(model_id=model_id or config.BEDROCK_MODEL_ID, region=config.AWS_REGION)

    from backend.openai_compat_llm import OpenAICompatLLM

    return OpenAICompatLLM(model_id=model_id, provider=provider)


def is_local_embedding_provider(provider: Optional[str] = None) -> bool:
    return (provider or config.EMBEDDING_PROVIDER).lower() in (
        LLMProvider.HUGGINGFACE.value,
        LLMProvider.LOCAL.value,
        LLMProvider.OLLAMA.value,  # legacy alias, see create_embeddings
    )


def create_embedding_client(provider: Optional[str] = None) -> Any:
    """Direct embeddings client for the active provider.

    ``BedrockEmbeddings`` (Titan) when EMBEDDING_PROVIDER=bedrock, otherwise
    ``LocalEmbeddings`` (sentence-transformers, EMBEDDING_MODEL). Both offer
    ``encode`` / ``get_sentence_embedding_dimension`` / ``get_stats`` and
    ``model_id``. Prefer ``get_shared_embedding_client`` in request paths:
    a local model takes seconds and hundreds of MB to load.
    """
    provider = (provider or config.EMBEDDING_PROVIDER).lower()
    if is_local_embedding_provider(provider):
        from backend.local_embeddings import LocalEmbeddings

        return LocalEmbeddings(model_id=config.EMBEDDING_MODEL)
    if provider == LLMProvider.BEDROCK.value:
        from backend.bedrock_embeddings import BedrockEmbeddings

        return BedrockEmbeddings(model_id=config.BEDROCK_EMBEDDING_MODEL_ID, region=config.AWS_REGION)
    raise ValueError(f"Unknown embedding provider: {provider}")


_shared_embedding_client: Any = None
_shared_embedding_lock = __import__("threading").Lock()


def get_shared_embedding_client() -> Any:
    """Process-wide embeddings client (lazy, thread-safe)."""
    global _shared_embedding_client
    if _shared_embedding_client is None:
        with _shared_embedding_lock:
            if _shared_embedding_client is None:
                _shared_embedding_client = create_embedding_client()
    return _shared_embedding_client


# Convenience functions
def get_llm(provider: Optional[str] = None, **kwargs) -> Any:
    """Convenience function to create LLM"""
    return LLMFactory.create_llm(provider, **kwargs)


def get_embeddings(provider: Optional[str] = None, **kwargs) -> Any:
    """Convenience function to create embeddings"""
    return LLMFactory.create_embeddings(provider, **kwargs)


def get_provider_info() -> dict:
    """Convenience function to get provider info"""
    return LLMFactory.get_provider_info()
