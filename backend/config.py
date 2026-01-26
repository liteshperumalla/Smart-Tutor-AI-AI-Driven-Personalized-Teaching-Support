"""
Configuration Management System
Handles environment variables, settings, and secrets management
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
import json
import boto3
from botocore.exceptions import ClientError
import logging

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_secret(secret_name: str, region: str = "us-east-1") -> Optional[Dict[str, Any]]:
    """
    Fetch secret from AWS Secrets Manager.
    Returns None if secret not found or if there's an error.
    """
    try:
        session = boto3.session.Session()
        client = session.client(service_name="secretsmanager", region_name=region)

        response = client.get_secret_value(SecretId=secret_name)

        if "SecretString" in response:
            return json.loads(response["SecretString"])
        else:
            logger.warning(f"Secret {secret_name} does not contain SecretString")
            return None
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            logger.warning(f"Secret {secret_name} not found in Secrets Manager")
        elif error_code == "AccessDeniedException":
            logger.warning(f"Access denied to secret {secret_name}")
        else:
            logger.error(f"Error fetching secret {secret_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching secret {secret_name}: {e}")
        return None


# Fetch secrets from AWS Secrets Manager (production only)
_rds_credentials = None
_app_secrets = None

# Always try to fetch secrets from AWS Secrets Manager if available
# This allows using AWS resources in development mode
if True:  # Changed from production-only to always attempt
    logger.info("Attempting to fetch secrets from AWS Secrets Manager...")
    _rds_credentials = get_secret("smart-tutor/rds/credentials")
    _app_secrets = get_secret("smart-tutor/app/secrets")

    if _rds_credentials:
        logger.info("✅ RDS credentials loaded from Secrets Manager")
    else:
        logger.warning(
            "⚠️ RDS credentials not found in Secrets Manager, falling back to .env"
        )

    if _app_secrets:
        logger.info("✅ Application secrets loaded from Secrets Manager")
    else:
        logger.warning(
            "⚠️ Application secrets not found in Secrets Manager, falling back to .env"
        )


class Config:
    """Central configuration management for the application"""

    # Application Settings
    APP_NAME = "Smart AI Tutor"
    APP_VERSION = "1.0.0"
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

    # Security Settings
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
    # SECURITY: Reduced from 3600 to 900 seconds (15 minutes)
    SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "900"))  # 15 minutes default
    MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
    LOCKOUT_DURATION = int(os.getenv("LOCKOUT_DURATION", "900"))  # 15 minutes
    # SECURITY: Increased minimum password length from 8 to 12
    PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "12"))
    PASSWORD_REQUIRE_UPPERCASE = (
        os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true"
    )
    PASSWORD_REQUIRE_LOWERCASE = (
        os.getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true"
    )
    PASSWORD_REQUIRE_DIGIT = (
        os.getenv("PASSWORD_REQUIRE_DIGIT", "true").lower() == "true"
    )
    PASSWORD_REQUIRE_SPECIAL = (
        os.getenv("PASSWORD_REQUIRE_SPECIAL", "true").lower() == "true"
    )
    PASSWORD_RESET_TOKEN_TTL_SECONDS = int(
        os.getenv("PASSWORD_RESET_TOKEN_TTL_SECONDS", "3600")
    )
    ALLOWED_REDIRECT_DOMAINS = os.getenv("ALLOWED_REDIRECT_DOMAINS", "").split(",")
    CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    CORS_ALLOW_LOCALHOST = os.getenv("CORS_ALLOW_LOCALHOST", "false").lower() == "true"

    # JWT Settings - with AWS Secrets Manager support
    JWT_SECRET_KEY = (
        _app_secrets.get("jwt_secret_key")
        if _app_secrets
        else os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    )  # Separate key for JWT signing
    JWT_ALGORITHM = os.getenv(
        "JWT_ALGORITHM", "HS256"
    )  # HS256 (symmetric) or RS256 (asymmetric)
    # SECURITY: Reduced from 30 to 15 minutes
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    )  # 15 minutes
    JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(
        os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")
    )  # 7 days
    JWT_ISSUER = os.getenv("JWT_ISSUER", "smart-ai-tutor")
    JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "smart-ai-tutor-api")

    # RSA Keys for RS256 (asymmetric signing)
    JWT_PRIVATE_KEY_PATH = os.getenv("JWT_PRIVATE_KEY_PATH", "keys/jwt_private.pem")
    JWT_PUBLIC_KEY_PATH = os.getenv("JWT_PUBLIC_KEY_PATH", "keys/jwt_public.pem")

    # Database Settings
    STORAGE_BACKEND = os.getenv(
        "STORAGE_BACKEND", "filesystem"
    )  # Options: filesystem, postgres, dynamodb
    USER_DATA_ROOT = os.getenv("USER_DATA_ROOT", "user_data")
    USERS_FILE = os.getenv("USERS_FILE", "users.json")
    PREV_CHAT_DIR = os.getenv("PREV_CHAT_DIR", "previous_chats")
    QUIZ_RESULTS_DIR = os.getenv("QUIZ_RESULTS_DIR", "quiz_results")

    # PostgreSQL Settings (Phase 2) - with AWS Secrets Manager support
    POSTGRES_HOST = (
        _rds_credentials.get("host")
        if _rds_credentials
        else os.getenv("POSTGRES_HOST", "localhost")
    )
    POSTGRES_PORT = (
        _rds_credentials.get("port")
        if _rds_credentials
        else int(os.getenv("POSTGRES_PORT", "5432"))
    )
    POSTGRES_DB = (
        _rds_credentials.get("database")
        if _rds_credentials
        else os.getenv("POSTGRES_DB", "smart_tutor")
    )
    POSTGRES_USER = (
        _rds_credentials.get("username")
        if _rds_credentials
        else os.getenv("POSTGRES_USER", "smart_tutor_user")
    )
    POSTGRES_PASSWORD = (
        _rds_credentials.get("password")
        if _rds_credentials
        else os.getenv("POSTGRES_PASSWORD", "dev_password_change_in_prod")
    )
    POSTGRES_MIN_CONNECTIONS = int(os.getenv("POSTGRES_MIN_CONNECTIONS", "2"))
    POSTGRES_MAX_CONNECTIONS = int(os.getenv("POSTGRES_MAX_CONNECTIONS", "10"))
    # SECURITY: PostgreSQL SSL settings
    POSTGRES_SSL_MODE = os.getenv(
        "POSTGRES_SSL_MODE", "require" if ENVIRONMENT == "production" else "prefer"
    )
    POSTGRES_SSL_ROOT_CERT = os.getenv(
        "POSTGRES_SSL_ROOT_CERT", ""
    )  # Path to CA certificate for RDS

    # DynamoDB Settings (Phase 2) - Updated for AWS production deployment
    DYNAMODB_ENDPOINT = os.getenv(
        "DYNAMODB_ENDPOINT", ""
    )  # Empty = AWS DynamoDB, set to http://localhost:8001 for local
    DYNAMODB_REGION = os.getenv("DYNAMODB_REGION", os.getenv("AWS_REGION", "us-east-1"))
    # Table names from Terraform outputs
    DYNAMODB_TABLE_CHAT_SESSIONS = os.getenv(
        "DYNAMODB_TABLE_CHAT_SESSIONS", f"smart-tutor-{ENVIRONMENT}-chat-sessions"
    )
    DYNAMODB_TABLE_USER_SESSIONS = os.getenv(
        "DYNAMODB_TABLE_USER_SESSIONS", f"smart-tutor-{ENVIRONMENT}-user-sessions"
    )
    # AWS credentials - use IAM roles in ECS (preferred) or environment variables
    AWS_ACCESS_KEY_ID = os.getenv(
        "AWS_ACCESS_KEY_ID", ""
    )  # Not needed when using IAM roles
    AWS_SECRET_ACCESS_KEY = os.getenv(
        "AWS_SECRET_ACCESS_KEY", ""
    )  # Not needed when using IAM roles
    AWS_SESSION_TOKEN = os.getenv(
        "AWS_SESSION_TOKEN", ""
    )  # Not needed when using IAM roles

    # Redis Settings (Phase 3) - Updated for ElastiCache
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(
        os.getenv("REDIS_PORT", "6379")
    )  # 6379 for production ElastiCache, 6380 for local dev
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    # Redis AUTH token from Secrets Manager or environment
    REDIS_PASSWORD = (
        _app_secrets.get("redis_auth_token")
        if _app_secrets
        else os.getenv("REDIS_PASSWORD", "")
    )
    # ElastiCache uses TLS in production
    REDIS_SSL = (
        os.getenv(
            "REDIS_SSL", "true" if ENVIRONMENT == "production" else "false"
        ).lower()
        == "true"
    )
    REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))
    # Enable Redis in production, optional in dev
    USE_REDIS_CACHE = (
        os.getenv(
            "USE_REDIS_CACHE", "true" if ENVIRONMENT == "production" else "false"
        ).lower()
        == "true"
    )

    # AWS Bedrock Settings (Phase 4)
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # bedrock or ollama
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama")  # bedrock or ollama

    # Bedrock Models
    BEDROCK_MODEL_ID = os.getenv(
        "BEDROCK_MODEL_ID", "us.meta.llama3-1-70b-instruct-v1:0"
    )
    BEDROCK_EMBEDDING_MODEL_ID = os.getenv(
        "BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
    )

    # S3 Buckets - Updated for Terraform module naming convention
    S3_UPLOADS_BUCKET = os.getenv(
        "S3_UPLOADS_BUCKET", f"smart-tutor-{ENVIRONMENT}-uploads"
    )
    S3_VECTORS_BUCKET = os.getenv(
        "S3_VECTORS_BUCKET", f"smart-tutor-{ENVIRONMENT}-vectors"
    )
    S3_BACKUPS_BUCKET = os.getenv(
        "S3_BACKUPS_BUCKET", f"smart-tutor-{ENVIRONMENT}-backups"
    )
    S3_DOCUMENTS_BUCKET = os.getenv(
        "S3_DOCUMENTS_BUCKET", "smart-ai-tutor-docs"
    )  # For course documents
    S3_VECTOR_INDEX_NAME = os.getenv(
        "S3_VECTOR_INDEX_NAME", ""
    )  # AWS S3 Vector Index name

    # Vector Store Selection
    USE_S3_VECTORS = (
        os.getenv("USE_S3_VECTORS", "false").lower() == "true"
    )  # Use S3 vectors instead of ChromaDB
    USE_S3_VECTOR_INDEX = (
        os.getenv("USE_S3_VECTOR_INDEX", "false").lower() == "true"
    )  # Use AWS S3 Vector Index

    # Bedrock Knowledge Base
    BEDROCK_KB_ID = os.getenv("BEDROCK_KB_ID", "")
    BEDROCK_KB_ENABLED = os.getenv("BEDROCK_KB_ENABLED", "false").lower() == "true"

    # Cost Tracking
    ENABLE_COST_TRACKING = os.getenv("ENABLE_COST_TRACKING", "true").lower() == "true"
    COST_LOG_FILE = os.getenv("COST_LOG_FILE", "logs/bedrock_costs.jsonl")

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
    QUERY_EXPANSION_ENABLED = (
        os.getenv("QUERY_EXPANSION_ENABLED", "true").lower() == "true"
    )
    QUERY_EXPANSION_NUM = int(
        os.getenv("QUERY_EXPANSION_NUM", "3")
    )  # Generate 3 query variations

    # Phase 2: Advanced RAG Settings
    # Query Rewriting - Optimize queries before retrieval (+22 NDCG@3)
    QUERY_REWRITING_ENABLED = (
        os.getenv("QUERY_REWRITING_ENABLED", "true").lower() == "true"
    )

    # Self-RAG - Reflection mechanism for quality assessment (-52% hallucinations)
    SELF_RAG_ENABLED = os.getenv("SELF_RAG_ENABLED", "true").lower() == "true"

    # Corrective RAG (CRAG) - Enhanced quality threshold for web search triggering
    CRAG_QUALITY_THRESHOLD = float(
        os.getenv("CRAG_QUALITY_THRESHOLD", "0.5")
    )  # 0.0-1.0 scale

    # Evaluation Settings
    EVALUATION_ENABLED = os.getenv("EVALUATION_ENABLED", "false").lower() == "true"
    EVALUATION_LOG_FILE = os.getenv("EVALUATION_LOG_FILE", "logs/rag_evaluation.jsonl")
    EVALUATION_DATASET_FILE = os.getenv(
        "EVALUATION_DATASET_FILE", "evaluation_dataset.json"
    )

    # Phase 3: Context & Quality Improvements (2025-11-05) - DISABLED
    # Recursive Chunking - Parent-child relationships for better context preservation
    RECURSIVE_CHUNKING_ENABLED = (
        os.getenv("RECURSIVE_CHUNKING_ENABLED", "false").lower() == "true"
    )
    PARENT_CHUNK_SIZE = int(
        os.getenv("PARENT_CHUNK_SIZE", "1024")
    )  # Larger parent chunks (500-2000 tokens)
    CHILD_CHUNK_SIZE = int(
        os.getenv("CHILD_CHUNK_SIZE", "256")
    )  # Smaller child chunks (100-500 tokens)
    PARENT_CHUNK_OVERLAP = int(
        os.getenv("PARENT_CHUNK_OVERLAP", "204")
    )  # 20% of parent size
    CHILD_CHUNK_OVERLAP = int(
        os.getenv("CHILD_CHUNK_OVERLAP", "51")
    )  # 20% of child size

    # Contextual Enrichment - Add document metadata to chunks
    CONTEXTUAL_ENRICHMENT_ENABLED = (
        os.getenv("CONTEXTUAL_ENRICHMENT_ENABLED", "false").lower() == "true"
    )
    INCLUDE_DOC_TITLE = os.getenv("INCLUDE_DOC_TITLE", "true").lower() == "true"
    INCLUDE_SECTION_HEADERS = (
        os.getenv("INCLUDE_SECTION_HEADERS", "true").lower() == "true"
    )
    INCLUDE_PAGE_NUMBERS = os.getenv("INCLUDE_PAGE_NUMBERS", "true").lower() == "true"

    # Response Diversity - MMR for reducing redundancy
    MMR_ENABLED = os.getenv("MMR_ENABLED", "false").lower() == "true"
    MMR_DIVERSITY_LAMBDA = float(
        os.getenv("MMR_DIVERSITY_LAMBDA", "0.5")
    )  # 0.0=max diversity, 1.0=max relevance
    MMR_FETCH_K = int(
        os.getenv("MMR_FETCH_K", "10")
    )  # Fetch more candidates for MMR reranking

    # Agentic Chunking - LLM-determined semantic boundaries (Experimental)
    AGENTIC_CHUNKING_ENABLED = (
        os.getenv("AGENTIC_CHUNKING_ENABLED", "false").lower() == "true"
    )
    AGENTIC_CHUNK_MIN_SIZE = int(os.getenv("AGENTIC_CHUNK_MIN_SIZE", "200"))
    AGENTIC_CHUNK_MAX_SIZE = int(os.getenv("AGENTIC_CHUNK_MAX_SIZE", "800"))

    # Web Search Settings - with AWS Secrets Manager support
    WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "true").lower() == "true"
    SERPAPI_API_KEY = (
        _app_secrets.get("serpapi_api_key")
        if _app_secrets
        else os.getenv("SERPAPI_API_KEY", "")
    )
    MAX_WEB_RESULTS = int(os.getenv("MAX_WEB_RESULTS", "3"))

    # Langfuse Settings (for monitoring) - with AWS Secrets Manager support
    LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
    LANGFUSE_PUBLIC_KEY = (
        _app_secrets.get("langfuse_public_key")
        if _app_secrets
        else os.getenv("LANGFUSE_PUBLIC_KEY", "")
    )
    LANGFUSE_SECRET_KEY = (
        _app_secrets.get("langfuse_secret_key")
        if _app_secrets
        else os.getenv("LANGFUSE_SECRET_KEY", "")
    )
    LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    # Google OAuth Settings - with AWS Secrets Manager support
    GOOGLE_OAUTH_CLIENT_ID = (
        _app_secrets.get("google_oauth_client_id")
        if _app_secrets
        else os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    )
    GOOGLE_OAUTH_CLIENT_SECRET = (
        _app_secrets.get("google_oauth_client_secret")
        if _app_secrets
        else os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    )
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

    # Rate Limiting
    RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_PERIOD = int(os.getenv("RATE_LIMIT_PERIOD", "60"))  # seconds

    # Per-User Rate Limiting (more restrictive, tracked by authenticated user)
    RATE_LIMIT_PER_USER_REQUESTS = int(os.getenv("RATE_LIMIT_PER_USER_REQUESTS", "60"))
    RATE_LIMIT_PER_USER_WINDOW = int(
        os.getenv("RATE_LIMIT_PER_USER_WINDOW", "60")
    )  # seconds

    # HTTPS Enforcement
    ENFORCE_HTTPS = (
        os.getenv("ENFORCE_HTTPS", "false").lower() == "true"
    )  # Enable in production

    # File Upload Settings
    MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))  # 10MB default
    ALLOWED_EXTENSIONS = os.getenv(
        "ALLOWED_EXTENSIONS", ".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg"
    ).split(",")

    # Logging Settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # json or text
    LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10MB
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    # CloudWatch Logging (for ECS)
    CLOUDWATCH_LOG_GROUP = os.getenv(
        "CLOUDWATCH_LOG_GROUP", f"/aws/ecs/smart-tutor/{ENVIRONMENT}/backend"
    )
    ENABLE_CLOUDWATCH_LOGS = (
        os.getenv(
            "ENABLE_CLOUDWATCH_LOGS", "true" if ENVIRONMENT == "production" else "false"
        ).lower()
        == "true"
    )

    # ECS Metadata (auto-populated in ECS environment)
    ECS_CONTAINER_METADATA_URI_V4 = os.getenv("ECS_CONTAINER_METADATA_URI_V4", "")
    AWS_EXECUTION_ENV = os.getenv("AWS_EXECUTION_ENV", "")

    @classmethod
    def validate(cls) -> Dict[str, Any]:
        """Validate configuration and return warnings/errors"""
        warnings = []
        errors = []

        # CRITICAL: Production security validation
        if cls.ENVIRONMENT == "production":
            # JWT Secret validation
            if (
                not cls.JWT_SECRET_KEY
                or cls.JWT_SECRET_KEY == "change-this-secret-key-in-production"
            ):
                errors.append(
                    "CRITICAL: JWT_SECRET_KEY not set in production. "
                    "Application cannot start without secure JWT secret. "
                    "Set it via AWS Secrets Manager or environment variable."
                )

            # CORS validation
            if not cls.CORS_ALLOWED_ORIGINS or cls.CORS_ALLOWED_ORIGINS == [""]:
                errors.append(
                    "CRITICAL: CORS_ALLOWED_ORIGINS must be set in production. "
                    "Example: CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com"
                )

            # Database password validation
            if cls.STORAGE_BACKEND in ["postgres", "hybrid"]:
                if not cls.POSTGRES_PASSWORD:
                    errors.append(
                        "CRITICAL: POSTGRES_PASSWORD not set in production. "
                        "Database password must be loaded from AWS Secrets Manager."
                    )

            # HTTPS enforcement validation
            if not cls.ENFORCE_HTTPS:
                warnings.append(
                    "SECURITY: ENFORCE_HTTPS is disabled in production. "
                    "This should be enabled for security."
                )

            # Warn about localhost in CORS
            if cls.CORS_ALLOW_LOCALHOST:
                warnings.append(
                    "SECURITY: CORS_ALLOW_LOCALHOST is enabled in production. "
                    "This should be disabled for security."
                )

            # Warn about weak secret key fallback
            if cls.SECRET_KEY == "change-this-secret-key-in-production":
                errors.append("SECRET_KEY must be changed in production environment")

        if cls.LANGFUSE_ENABLED and (
            not cls.LANGFUSE_PUBLIC_KEY or not cls.LANGFUSE_SECRET_KEY
        ):
            warnings.append("Langfuse is enabled but keys are missing")

        if not cls.GOOGLE_OAUTH_CLIENT_ID or not cls.GOOGLE_OAUTH_CLIENT_SECRET:
            warnings.append("Google OAuth credentials are not configured")

        if cls.WEB_SEARCH_ENABLED and not cls.SERPAPI_API_KEY:
            warnings.append("Web search is enabled but SERPAPI_API_KEY is missing")

        # Create required directories
        for directory in [
            cls.USER_DATA_ROOT,
            cls.PREV_CHAT_DIR,
            cls.QUIZ_RESULTS_DIR,
            cls.PERSIST_DIR,
            cls.CHROMA_DB_PATH,
        ]:
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

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    @classmethod
    def to_dict(cls, include_secrets: bool = False) -> Dict[str, Any]:
        """Export configuration as dictionary"""
        config_dict = {}
        for key, value in cls.__dict__.items():
            if not key.startswith("_") and not callable(value):
                # Mask secrets unless explicitly requested
                if not include_secrets and any(
                    secret in key.lower() for secret in ["key", "secret", "password"]
                ):
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
