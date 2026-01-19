"""LLM Provider Abstraction Layer

Provides a unified interface for switching between different LLM and embedding providers:

LLM Providers:
- AWS Bedrock (Claude, Llama, etc.)
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
            provider: LLM provider name (bedrock, ollama). Uses config if not specified.
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
    def _create_ollama_llm(**kwargs) -> Any:
        """Create Ollama local LLM instance"""
        try:
            from llama_index.llms.ollama import Ollama

            model = kwargs.get('model', config.LLM_MODEL)
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
            "ollama": {
                "model": config.LLM_MODEL,
                "base_url": config.OLLAMA_BASE_URL,
                "embedding_model": config.EMBEDDING_MODEL,
                "enabled": config.LLM_PROVIDER == LLMProvider.OLLAMA.value
            }
        }


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
