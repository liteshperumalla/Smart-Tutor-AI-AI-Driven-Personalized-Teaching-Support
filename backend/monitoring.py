"""
Enhanced Monitoring and Observability
Provides cache statistics, observability integration status, and system health checks
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .config import config
from .logger import get_logger

logger = get_logger(__name__)


class MonitoringService:
    """Service for monitoring application health and performance"""

    def __init__(self):
        self._start_time = datetime.now()

    def get_system_health(self) -> Dict[str, Any]:
        """
        Get comprehensive system health status

        Returns:
            Dictionary with system health information
        """
        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
            "components": {}
        }

        # Check cache status
        health["components"]["cache"] = self._check_cache_health()

        # Check Langfuse status
        health["components"]["langfuse"] = self._check_langfuse_health()

        # Check PostHog status
        health["components"]["posthog"] = self._check_posthog_health()

        # Check evaluation framework
        health["components"]["evaluation"] = self._check_evaluation_health()

        # Check Phase 3 features
        health["components"]["phase3_features"] = self._check_phase3_status()

        # Determine overall status
        component_statuses = [comp.get("status", "unknown") for comp in health["components"].values()]
        if any(status == "error" for status in component_statuses):
            health["status"] = "degraded"
        elif all(status == "healthy" for status in component_statuses):
            health["status"] = "healthy"
        else:
            health["status"] = "warning"

        return health

    def _check_cache_health(self) -> Dict[str, Any]:
        """Check cache system health"""
        try:
            from .cache import get_cache_manager

            cache_manager = get_cache_manager()
            stats = cache_manager.get_all_stats()

            backend_type = "in-memory"
            if config.REDIS_ENABLED:
                # Check if any cache is actually using Redis
                for cache_stats in stats.values():
                    if cache_stats.get("backend") == "redis":
                        backend_type = "redis"
                        break

            return {
                "status": "healthy",
                "enabled": config.CACHE_ENABLED,
                "backend": backend_type,
                "statistics": stats,
                "ttl": config.CACHE_TTL,
                "max_size": config.CACHE_MAX_SIZE
            }
        except Exception as e:
            logger.error(f"Failed to check cache health: {e}")
            return {
                "status": "error",
                "enabled": False,
                "error": str(e)
            }

    def _check_langfuse_health(self) -> Dict[str, Any]:
        """Check Langfuse monitoring health"""
        try:
            if not config.LANGFUSE_ENABLED:
                return {
                    "status": "disabled",
                    "enabled": False,
                    "message": "Langfuse monitoring is not enabled. Set LANGFUSE_ENABLED=true to enable."
                }

            if not config.LANGFUSE_PUBLIC_KEY or not config.LANGFUSE_SECRET_KEY:
                return {
                    "status": "warning",
                    "enabled": True,
                    "configured": False,
                    "message": "Langfuse is enabled but API keys are missing"
                }

            # Try to import and check Langfuse
            try:
                from langfuse import Langfuse
                # Note: We don't test the connection here to avoid API calls
                return {
                    "status": "healthy",
                    "enabled": True,
                    "configured": True,
                    "host": config.LANGFUSE_HOST
                }
            except ImportError:
                return {
                    "status": "error",
                    "enabled": True,
                    "configured": True,
                    "error": "Langfuse SDK not installed. Install with: pip install langfuse"
                }

        except Exception as e:
            logger.error(f"Failed to check Langfuse health: {e}")
            return {
                "status": "error",
                "enabled": config.LANGFUSE_ENABLED,
                "error": str(e)
            }

    def _check_evaluation_health(self) -> Dict[str, Any]:
        """Check RAG evaluation framework health"""
        try:
            import os

            if not config.EVALUATION_ENABLED:
                return {
                    "status": "disabled",
                    "enabled": False,
                    "message": "Evaluation framework is not enabled"
                }

            # Check if log file exists and is writable
            log_dir = os.path.dirname(config.EVALUATION_LOG_FILE)
            if log_dir and not os.path.exists(log_dir):
                return {
                    "status": "warning",
                    "enabled": True,
                    "message": f"Log directory does not exist: {log_dir}"
                }

            # Try to import evaluation module
            try:
                from .rag_evaluation import get_evaluator
                evaluator = get_evaluator()

                # Get evaluation statistics if available
                try:
                    stats = evaluator.get_summary_stats()
                    return {
                        "status": "healthy",
                        "enabled": True,
                        "log_file": config.EVALUATION_LOG_FILE,
                        "statistics": stats
                    }
                except:
                    return {
                        "status": "healthy",
                        "enabled": True,
                        "log_file": config.EVALUATION_LOG_FILE
                    }
            except ImportError:
                return {
                    "status": "warning",
                    "enabled": True,
                    "message": "Evaluation framework module not found"
                }

        except Exception as e:
            logger.error(f"Failed to check evaluation health: {e}")
            return {
                "status": "error",
                "enabled": config.EVALUATION_ENABLED,
                "error": str(e)
            }

    def _check_posthog_health(self) -> Dict[str, Any]:
        """Check PostHog analytics health"""
        try:
            from .posthog_tracker import get_posthog_health

            return get_posthog_health()
        except Exception as e:
            logger.error(f"Failed to check PostHog health: {e}")
            return {
                "status": "error",
                "enabled": config.POSTHOG_ENABLED,
                "error": str(e)
            }

    def _check_phase3_status(self) -> Dict[str, Any]:
        """Check Phase 3 features status"""
        return {
            "status": "healthy",
            "features": {
                "recursive_chunking": {
                    "enabled": config.RECURSIVE_CHUNKING_ENABLED,
                    "parent_chunk_size": config.PARENT_CHUNK_SIZE,
                    "child_chunk_size": config.CHILD_CHUNK_SIZE
                },
                "contextual_enrichment": {
                    "enabled": config.CONTEXTUAL_ENRICHMENT_ENABLED,
                    "include_doc_title": config.INCLUDE_DOC_TITLE,
                    "include_section_headers": config.INCLUDE_SECTION_HEADERS,
                    "include_page_numbers": config.INCLUDE_PAGE_NUMBERS
                },
                "mmr_diversity": {
                    "enabled": config.MMR_ENABLED,
                    "diversity_lambda": config.MMR_DIVERSITY_LAMBDA,
                    "fetch_k": config.MMR_FETCH_K
                },
                "agentic_chunking": {
                    "enabled": config.AGENTIC_CHUNKING_ENABLED,
                    "min_size": config.AGENTIC_CHUNK_MIN_SIZE,
                    "max_size": config.AGENTIC_CHUNK_MAX_SIZE
                }
            }
        }

    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get detailed cache statistics"""
        try:
            from .cache import get_cache_manager

            cache_manager = get_cache_manager()
            return cache_manager.get_all_stats()
        except Exception as e:
            logger.error(f"Failed to get cache statistics: {e}")
            return {"error": str(e)}

    def get_feature_status(self) -> Dict[str, Any]:
        """Get status of all features"""
        return {
            "phase1": {
                "chunk_optimization": {
                    "chunk_size": config.CHUNK_SIZE,
                    "chunk_overlap": config.CHUNK_OVERLAP
                },
                "embedding_model": config.EMBEDDING_MODEL,
                "query_expansion": {
                    "enabled": config.QUERY_EXPANSION_ENABLED,
                    "num_variations": config.QUERY_EXPANSION_NUM
                },
                "evaluation": {
                    "enabled": config.EVALUATION_ENABLED,
                    "log_file": config.EVALUATION_LOG_FILE
                }
            },
            "phase2": {
                "query_rewriting": {
                    "enabled": config.QUERY_REWRITING_ENABLED
                },
                "self_rag": {
                    "enabled": config.SELF_RAG_ENABLED
                },
                "crag": {
                    "quality_threshold": config.CRAG_QUALITY_THRESHOLD
                }
            },
            "phase3": self._check_phase3_status()["features"],
            "caching": {
                "enabled": config.CACHE_ENABLED,
                "backend": "redis" if config.REDIS_ENABLED else "in-memory",
                "ttl": config.CACHE_TTL
            },
            "monitoring": {
                "langfuse_enabled": config.LANGFUSE_ENABLED,
                "evaluation_enabled": config.EVALUATION_ENABLED
            }
        }


# Singleton instance
_monitoring_service = None


def get_monitoring_service() -> MonitoringService:
    """Get singleton monitoring service instance"""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService()
    return _monitoring_service
