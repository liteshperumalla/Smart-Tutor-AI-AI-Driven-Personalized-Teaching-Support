"""
Configuration Management System
Handles environment variables, settings, and secrets management
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
import json

# Load environment variables from .env file
load_dotenv()


class Config:
    """Central configuration management for the application"""

    # Application Settings
    APP_NAME = "Smart AI Tutor"
    APP_VERSION = "1.0.0"
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

    # Security Settings
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
    SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "3600"))  # 1 hour default
    MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
    LOCKOUT_DURATION = int(os.getenv("LOCKOUT_DURATION", "900"))  # 15 minutes
    PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
    PASSWORD_REQUIRE_UPPERCASE = os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true"
    PASSWORD_REQUIRE_LOWERCASE = os.getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true"
    PASSWORD_REQUIRE_DIGIT = os.getenv("PASSWORD_REQUIRE_DIGIT", "true").lower() == "true"
    PASSWORD_REQUIRE_SPECIAL = os.getenv("PASSWORD_REQUIRE_SPECIAL", "true").lower() == "true"

    # Database Settings
    USER_DATA_ROOT = os.getenv("USER_DATA_ROOT", "user_data")
    USERS_FILE = os.getenv("USERS_FILE", "users.json")
    PREV_CHAT_DIR = os.getenv("PREV_CHAT_DIR", "previous_chats")
    QUIZ_RESULTS_DIR = os.getenv("QUIZ_RESULTS_DIR", "quiz_results")

    # RAG & AI Settings
    PERSIST_DIR = os.getenv("PERSIST_DIR", "./persisted_index")
    CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    # Updated to BAAI/bge-small-en-v1.5 for better retrieval performance (Phase 1 improvement)
    # Previous: sentence-transformers/all-MiniLM-L6-v2
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:latest")
    LLM_REQUEST_TIMEOUT = float(os.getenv("LLM_REQUEST_TIMEOUT", "120.0"))
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Retrieval Settings
    SIMILARITY_TOP_K = int(os.getenv("SIMILARITY_TOP_K", "3"))
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.3"))
    # Optimized chunking: increased from 100 to 512 chars for better context (Phase 1 improvement)
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))
    # Optimized overlap: increased to 20% of chunk size (102/512) for better continuity
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "102"))

    # Advanced Retrieval Settings (Phase 1 additions)
    RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "5"))
    MIN_RERANK_SCORE = float(os.getenv("MIN_RERANK_SCORE", "0.20"))

    # Query Expansion Settings (Phase 1)
    QUERY_EXPANSION_ENABLED = os.getenv("QUERY_EXPANSION_ENABLED", "true").lower() == "true"
    QUERY_EXPANSION_NUM = int(os.getenv("QUERY_EXPANSION_NUM", "3"))  # Generate 3 query variations

    # Phase 2: Advanced RAG Settings
    # Query Rewriting - Optimize queries before retrieval (+22 NDCG@3)
    QUERY_REWRITING_ENABLED = os.getenv("QUERY_REWRITING_ENABLED", "true").lower() == "true"

    # Self-RAG - Reflection mechanism for quality assessment (-52% hallucinations)
    SELF_RAG_ENABLED = os.getenv("SELF_RAG_ENABLED", "true").lower() == "true"

    # Corrective RAG (CRAG) - Enhanced quality threshold for web search triggering
    CRAG_QUALITY_THRESHOLD = float(os.getenv("CRAG_QUALITY_THRESHOLD", "0.5"))  # 0.0-1.0 scale

    # Evaluation Settings (Enabled by default for monitoring)
    EVALUATION_ENABLED = os.getenv("EVALUATION_ENABLED", "true").lower() == "true"
    EVALUATION_LOG_FILE = os.getenv("EVALUATION_LOG_FILE", "logs/rag_evaluation.jsonl")

    # Phase 3: Context & Quality Improvements (2025-11-18) - ENABLED
    # Recursive Chunking - Parent-child relationships for better context preservation
    RECURSIVE_CHUNKING_ENABLED = os.getenv("RECURSIVE_CHUNKING_ENABLED", "true").lower() == "true"
    PARENT_CHUNK_SIZE = int(os.getenv("PARENT_CHUNK_SIZE", "1024"))  # Larger parent chunks (500-2000 tokens)
    CHILD_CHUNK_SIZE = int(os.getenv("CHILD_CHUNK_SIZE", "256"))     # Smaller child chunks (100-500 tokens)
    PARENT_CHUNK_OVERLAP = int(os.getenv("PARENT_CHUNK_OVERLAP", "204"))  # 20% of parent size
    CHILD_CHUNK_OVERLAP = int(os.getenv("CHILD_CHUNK_OVERLAP", "51"))     # 20% of child size

    # Contextual Enrichment - Add document metadata to chunks
    CONTEXTUAL_ENRICHMENT_ENABLED = os.getenv("CONTEXTUAL_ENRICHMENT_ENABLED", "true").lower() == "true"
    INCLUDE_DOC_TITLE = os.getenv("INCLUDE_DOC_TITLE", "true").lower() == "true"
    INCLUDE_SECTION_HEADERS = os.getenv("INCLUDE_SECTION_HEADERS", "true").lower() == "true"
    INCLUDE_PAGE_NUMBERS = os.getenv("INCLUDE_PAGE_NUMBERS", "true").lower() == "true"

    # Response Diversity - MMR for reducing redundancy
    MMR_ENABLED = os.getenv("MMR_ENABLED", "true").lower() == "true"
    MMR_DIVERSITY_LAMBDA = float(os.getenv("MMR_DIVERSITY_LAMBDA", "0.5"))  # 0.0=max diversity, 1.0=max relevance
    MMR_FETCH_K = int(os.getenv("MMR_FETCH_K", "10"))  # Fetch more candidates for MMR reranking

    # Agentic Chunking - LLM-determined semantic boundaries (Experimental)
    AGENTIC_CHUNKING_ENABLED = os.getenv("AGENTIC_CHUNKING_ENABLED", "true").lower() == "true"
    AGENTIC_CHUNK_MIN_SIZE = int(os.getenv("AGENTIC_CHUNK_MIN_SIZE", "200"))
    AGENTIC_CHUNK_MAX_SIZE = int(os.getenv("AGENTIC_CHUNK_MAX_SIZE", "800"))

    # Web Search Settings
    WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "true").lower() == "true"
    SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
    MAX_WEB_RESULTS = int(os.getenv("MAX_WEB_RESULTS", "3"))

    # Langfuse Settings (for monitoring)
    LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
    LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    # Google OAuth Settings
    GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    GOOGLE_OAUTH_REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "")

    # Email Settings
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM = os.getenv("EMAIL_FROM", "")

    # Cache Settings
    CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes default
    CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "1000"))

    # Redis Cache Settings (optional, falls back to in-memory if not available)
    REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
    REDIS_SSL = os.getenv("REDIS_SSL", "false").lower() == "true"
    REDIS_CONNECTION_TIMEOUT = int(os.getenv("REDIS_CONNECTION_TIMEOUT", "5"))  # seconds

    # Rate Limiting
    RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_PERIOD = int(os.getenv("RATE_LIMIT_PERIOD", "60"))  # seconds

    # File Upload Settings
    MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))  # 10MB default
    ALLOWED_EXTENSIONS = os.getenv("ALLOWED_EXTENSIONS", ".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg").split(",")

    # Logging Settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # json or text
    LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10MB
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    @classmethod
    def validate(cls) -> Dict[str, Any]:
        """Validate configuration and return warnings/errors"""
        warnings = []
        errors = []

        # Check critical settings
        if cls.SECRET_KEY == "change-this-secret-key-in-production" and cls.ENVIRONMENT == "production":
            errors.append("SECRET_KEY must be changed in production environment")

        if cls.LANGFUSE_ENABLED and (not cls.LANGFUSE_PUBLIC_KEY or not cls.LANGFUSE_SECRET_KEY):
            warnings.append("Langfuse is enabled but keys are missing")

        if not cls.GOOGLE_OAUTH_CLIENT_ID or not cls.GOOGLE_OAUTH_CLIENT_SECRET:
            warnings.append("Google OAuth credentials are not configured")

        if cls.WEB_SEARCH_ENABLED and not cls.SERPAPI_API_KEY:
            warnings.append("Web search is enabled but SERPAPI_API_KEY is missing")

        # Create required directories
        for directory in [cls.USER_DATA_ROOT, cls.PREV_CHAT_DIR, cls.QUIZ_RESULTS_DIR,
                         cls.PERSIST_DIR, cls.CHROMA_DB_PATH]:
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception as e:
                errors.append(f"Failed to create directory {directory}: {e}")

        # Create logs directory if needed
        log_dir = os.path.dirname(cls.LOG_FILE)
        if log_dir:
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception as e:
                warnings.append(f"Failed to create log directory {log_dir}: {e}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    @classmethod
    def to_dict(cls, include_secrets: bool = False) -> Dict[str, Any]:
        """Export configuration as dictionary"""
        config_dict = {}
        for key, value in cls.__dict__.items():
            if not key.startswith('_') and not callable(value):
                # Mask secrets unless explicitly requested
                if not include_secrets and any(secret in key.lower() for secret in ['key', 'secret', 'password']):
                    config_dict[key] = "***REDACTED***"
                else:
                    config_dict[key] = value
        return config_dict

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get configuration value by key"""
        return getattr(cls, key, default)


# Singleton instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance"""
    return config


def validate_config() -> Dict[str, Any]:
    """Validate the current configuration"""
    return config.validate()
