"""
Enhanced Health Check System
Provides detailed health checks for all application dependencies
"""

from datetime import datetime, timezone
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class HealthChecker:
    """Comprehensive health check for all application components"""

    @staticmethod
    def check_database() -> Dict[str, Any]:
        """Check database connectivity and health"""
        try:
            from backend.database import get_user_db
            from backend.config import config

            db = get_user_db()

            # Try a simple query
            try:
                # Attempt to get a non-existent user (shouldn't error)
                db.get_user("__health_check__")
                status = "healthy"
                message = f"Connected to {config.STORAGE_BACKEND}"
            except Exception as e:
                # If it's a connection error, mark unhealthy
                if "connection" in str(e).lower() or "timeout" in str(e).lower():
                    status = "unhealthy"
                    message = f"Database connection error: {e}"
                else:
                    # Other errors (like user not found) are expected
                    status = "healthy"
                    message = f"Connected to {config.STORAGE_BACKEND}"

            return {
                "status": status,
                "backend": config.STORAGE_BACKEND,
                "message": message
            }

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    @staticmethod
    def check_redis() -> Dict[str, Any]:
        """Check Redis connectivity"""
        try:
            from backend.config import config

            if not config.USE_REDIS_CACHE:
                return {
                    "status": "disabled",
                    "message": "Redis caching is disabled"
                }

            from backend.redis_cache import get_redis_cache

            redis = get_redis_cache()
            # Try to ping Redis
            redis.client.ping()

            return {
                "status": "healthy",
                "host": config.REDIS_HOST,
                "port": config.REDIS_PORT,
                "message": "Connected"
            }

        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    @staticmethod
    def check_bedrock() -> Dict[str, Any]:
        """Check AWS Bedrock connectivity"""
        try:
            from backend.config import config

            if config.LLM_PROVIDER != "bedrock":
                return {
                    "status": "not_configured",
                    "message": f"LLM provider is {config.LLM_PROVIDER}"
                }

            # Simple check - verify boto3 can be imported and region is set
            import boto3

            # Try to get STS caller identity (lightweight API call)
            sts = boto3.client('sts', region_name=config.AWS_REGION)
            identity = sts.get_caller_identity()

            return {
                "status": "healthy",
                "region": config.AWS_REGION,
                "model": config.BEDROCK_MODEL_ID,
                "account": identity.get("Account", "unknown"),
                "message": "AWS credentials valid"
            }

        except Exception as e:
            logger.error(f"Bedrock health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    @staticmethod
    def check_neo4j() -> Dict[str, Any]:
        """Check Neo4j connectivity (knowledge graph)"""
        try:
            from backend.config import config

            if not config.NEO4J_URI:
                return {
                    "status": "not_configured",
                    "message": "NEO4J_URI is not set"
                }

            from backend.agents.neo4j_client import get_neo4j_client

            get_neo4j_client().driver.verify_connectivity()

            return {
                "status": "healthy",
                "message": "Connected"
            }

        except Exception as e:
            # Includes a paused Aura instance -- reported as unhealthy here
            # rather than triggering an in-request resume, which can take
            # minutes; the scheduled resume-guard workflow owns that job.
            logger.error(f"Neo4j health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    @staticmethod
    def check_s3() -> Dict[str, Any]:
        """Check S3 connectivity (vector store / uploads)"""
        try:
            from backend.config import config

            # S3_DOCUMENTS_BUCKET is the bucket S3VectorStore and every other
            # S3-backed service (files, quiz, research) actually reads/writes.
            # S3_VECTORS_BUCKET is unused elsewhere and its default name was
            # never provisioned as a real bucket, so checking it always 404s.
            if not config.S3_DOCUMENTS_BUCKET:
                return {
                    "status": "not_configured",
                    "message": "S3_DOCUMENTS_BUCKET is not set"
                }

            from backend.cloud.aws_helpers import get_boto3_client

            s3 = get_boto3_client("s3")
            s3.head_bucket(Bucket=config.S3_DOCUMENTS_BUCKET)

            return {
                "status": "healthy",
                "bucket": config.S3_DOCUMENTS_BUCKET,
                "message": "Accessible"
            }

        except Exception as e:
            logger.error(f"S3 health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    @staticmethod
    def check_secrets_manager() -> Dict[str, Any]:
        """Check AWS Secrets Manager access"""
        try:
            from backend.config import config

            if config.ENVIRONMENT != "production":
                return {
                    "status": "not_applicable",
                    "message": "Secrets Manager only used in production"
                }

            import boto3

            client = boto3.client('secretsmanager', region_name=config.AWS_REGION)

            # Try to describe the app secrets (lightweight operation)
            try:
                client.describe_secret(SecretId='smart-tutor/app/secrets')
                return {
                    "status": "healthy",
                    "message": "Secrets Manager accessible"
                }
            except client.exceptions.ResourceNotFoundException:
                return {
                    "status": "unhealthy",
                    "error": "Secret 'smart-tutor/app/secrets' not found"
                }

        except Exception as e:
            logger.error(f"Secrets Manager health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    @staticmethod
    def check_langfuse() -> Dict[str, Any]:
        """Check Langfuse tracing connectivity"""
        try:
            from backend.langfuse_setup import get_langfuse_health
            return get_langfuse_health()
        except Exception as e:
            logger.error(f"Langfuse health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    @staticmethod
    def check_posthog() -> Dict[str, Any]:
        """Check PostHog analytics connectivity"""
        try:
            from backend.posthog_tracker import get_posthog_health
            return get_posthog_health()
        except Exception as e:
            logger.error(f"PostHog health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    @staticmethod
    def check_jwt_blacklist() -> Dict[str, Any]:
        """Check JWT blacklist functionality"""
        try:
            from backend.jwt_blacklist import get_jwt_blacklist

            blacklist = get_jwt_blacklist()

            if not blacklist:
                return {
                    "status": "not_initialized",
                    "message": "JWT blacklist not initialized"
                }

            stats = blacklist.get_stats()

            return {
                "status": "healthy",
                "redis_enabled": stats.get("redis_enabled", False),
                "in_memory_count": stats.get("in_memory_count", 0),
                "redis_count": stats.get("redis_count", -1)
            }

        except Exception as e:
            logger.error(f"JWT blacklist health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    # Components the app cannot meaningfully serve traffic without. A
    # failure here means "unhealthy" (gates deploys/rollbacks); a failure
    # in anything else means "degraded" (observability/secrets-cache blips
    # that shouldn't block a promotion on their own).
    CORE_COMPONENTS = {"database", "redis", "bedrock", "neo4j", "s3"}

    @classmethod
    def get_detailed_health(cls) -> Dict[str, Any]:
        """
        Get comprehensive health status for all components

        Returns:
            Dict with overall status and individual component health
        """
        checks = {
            "database": cls.check_database(),
            "redis": cls.check_redis(),
            "bedrock": cls.check_bedrock(),
            "neo4j": cls.check_neo4j(),
            "s3": cls.check_s3(),
            "secrets_manager": cls.check_secrets_manager(),
            "jwt_blacklist": cls.check_jwt_blacklist(),
            "langfuse": cls.check_langfuse(),
            "posthog": cls.check_posthog(),
        }

        # Determine overall health
        unhealthy_components = [
            name for name, check in checks.items()
            if check.get("status") == "unhealthy"
        ]
        unhealthy_core = [name for name in unhealthy_components if name in cls.CORE_COMPONENTS]

        if unhealthy_core:
            overall_status = "unhealthy"
        elif unhealthy_components:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        return {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
            "unhealthy_components": unhealthy_components if unhealthy_components else None
        }

    @classmethod
    def get_simple_health(cls) -> Dict[str, str]:
        """
        Get simple health status (just overall status)

        Returns:
            Dict with status and timestamp
        """
        detailed = cls.get_detailed_health()

        return {
            "status": detailed["status"],
            "timestamp": detailed["timestamp"]
        }

    @classmethod
    def get_liveness_core(cls) -> Dict[str, Any]:
        """
        Fast, cheap check of only the dependencies nearly every request
        needs. This backs /ready, which Docker's HEALTHCHECK polls every
        5s for the entire lifetime of the container -- deliberately
        excludes slower/external checks (Bedrock, Neo4j, S3, Secrets
        Manager, Langfuse, PostHog) that belong in /health instead.

        Returns:
            Dict with status ("ready" or "unhealthy") and component checks
        """
        checks = {
            "database": cls.check_database(),
            "redis": cls.check_redis(),
        }
        unhealthy = [
            name for name, check in checks.items()
            if check.get("status") == "unhealthy"
        ]
        return {
            "status": "unhealthy" if unhealthy else "ready",
            "checks": checks,
            "unhealthy_components": unhealthy if unhealthy else None
        }
