"""
Feature Flag Service
====================
Runtime-toggleable feature flags that resolve from PostHog (when available)
with a safe environment-variable fallback.

This means flags can be toggled without redeployment:
- In production:  toggle via PostHog dashboard  → takes effect immediately
- In dev/CI:      set FEATURE_FLAG_<NAME>=true/false in .env  → works offline

Usage
-----
    from backend.feature_flags import flags

    if flags.is_enabled("enhanced_rag", user_id="user-123"):
        # use enhanced RAG pipeline
    else:
        # use default pipeline

Adding a new flag
-----------------
1. Add an entry to FLAG_DEFAULTS below with its safe default value.
2. Use flags.is_enabled("my_flag") in the code path.
3. Optionally set FEATURE_FLAG_MY_FLAG=true in .env to override locally.
4. Create the flag in the PostHog dashboard for live runtime toggling.
"""

from __future__ import annotations

import os
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flag registry — add all flags here with their safe fallback default.
# Values here are used when PostHog is unavailable or the flag is not defined.
# ---------------------------------------------------------------------------
FLAG_DEFAULTS: Dict[str, bool] = {
    # RAG pipeline enhancements
    "enhanced_rag":              os.getenv("ENHANCED_RAG_ENABLED", "false").lower() == "true",
    "self_rag":                  os.getenv("SELF_RAG_ENABLED", "true").lower() == "true",
    "query_expansion":           os.getenv("QUERY_EXPANSION_ENABLED", "true").lower() == "true",
    "query_rewriting":           os.getenv("QUERY_REWRITING_ENABLED", "true").lower() == "true",
    "reranking":                 os.getenv("RERANKING_ENABLED", "false").lower() == "true",
    "recursive_chunking":        os.getenv("RECURSIVE_CHUNKING_ENABLED", "false").lower() == "true",
    "contextual_enrichment":     os.getenv("CONTEXTUAL_ENRICHMENT_ENABLED", "false").lower() == "true",
    "mmr_diversity":             os.getenv("MMR_ENABLED", "false").lower() == "true",
    "agentic_chunking":          os.getenv("AGENTIC_CHUNKING_ENABLED", "false").lower() == "true",

    # Infrastructure / backend features
    "redis_cache":               os.getenv("USE_REDIS_CACHE", "false").lower() == "true",
    "bedrock_kb":                os.getenv("BEDROCK_KB_ENABLED", "false").lower() == "true",
    "cost_tracking":             os.getenv("ENABLE_COST_TRACKING", "true").lower() == "true",
    "rag_evaluation":            os.getenv("EVALUATION_ENABLED", "false").lower() == "true",

    # UX / frontend-facing flags (toggled without code change)
    "new_chat_ui":               os.getenv("FEATURE_FLAG_NEW_CHAT_UI", "false").lower() == "true",
    "quiz_generation_v2":        os.getenv("FEATURE_FLAG_QUIZ_V2", "false").lower() == "true",
    "code_execution":            os.getenv("FEATURE_FLAG_CODE_EXECUTION", "true").lower() == "true",
    "knowledge_graph":           os.getenv("FEATURE_FLAG_KNOWLEDGE_GRAPH", "false").lower() == "true",
    "multi_agent":               os.getenv("AGENT_SYSTEM_ENABLED", "false").lower() == "true",

    # Maintenance / rollout gates
    "maintenance_mode":          os.getenv("FEATURE_FLAG_MAINTENANCE_MODE", "false").lower() == "true",
    "beta_users_only":           os.getenv("FEATURE_FLAG_BETA_ONLY", "false").lower() == "true",
}


class FeatureFlagService:
    """
    Resolves feature flags at runtime.

    Resolution order (first truthy source wins):
      1. PostHog per-user flag evaluation  (requires POSTHOG_API_KEY + user_id)
      2. Environment variable override     (FEATURE_FLAG_<UPPER_NAME>=true/false)
      3. FLAG_DEFAULTS dict               (hardcoded safe defaults)
    """

    def __init__(self) -> None:
        self._posthog_client: Optional[Any] = None
        self._posthog_available: bool = False
        self._init_posthog()

    def _init_posthog(self) -> None:
        """Attempt to connect to PostHog. Silently degrades if unavailable."""
        api_key = os.getenv("POSTHOG_API_KEY", "")
        host = os.getenv("POSTHOG_HOST", "https://app.posthog.com")

        if not api_key:
            logger.info(
                "POSTHOG_API_KEY not set — feature flags will use env-var / "
                "FLAG_DEFAULTS fallback only."
            )
            return

        try:
            import posthog as ph
            ph.api_key = api_key
            ph.host = host
            ph.debug = False
            # disable_gzip avoids a known threading issue in some envs
            self._posthog_client = ph
            self._posthog_available = True
            logger.info("FeatureFlagService: PostHog connected (%s)", host)
        except ImportError:
            logger.warning(
                "posthog package not installed — falling back to env-var flags. "
                "Install with: pip install posthog"
            )
        except Exception as exc:
            logger.warning("FeatureFlagService: PostHog init failed: %s", exc)

    # ── Public API ───────────────────────────────────────────────────────────

    def is_enabled(
        self,
        flag_name: str,
        user_id: Optional[str] = None,
        default: Optional[bool] = None,
    ) -> bool:
        """
        Return True if the named feature flag is enabled.

        Args:
            flag_name:  Name of the flag (must exist in FLAG_DEFAULTS or PostHog).
            user_id:    Optional user ID for per-user PostHog evaluation.
            default:    Override the FLAG_DEFAULTS fallback for this call only.

        Returns:
            bool — whether the feature is enabled for this user/context.
        """
        # 1. PostHog real-time evaluation (requires user_id for per-user targeting)
        if self._posthog_available and user_id:
            try:
                result = self._posthog_client.feature_enabled(
                    flag_name,
                    user_id,
                )
                if result is not None:
                    return bool(result)
            except Exception as exc:
                logger.debug(
                    "PostHog flag eval failed for '%s' (user=%s): %s — using fallback",
                    flag_name, user_id, exc,
                )

        # 2. Env-var override: FEATURE_FLAG_<UPPER_NAME>
        env_key = f"FEATURE_FLAG_{flag_name.upper()}"
        env_val = os.getenv(env_key)
        if env_val is not None:
            return env_val.lower() in ("true", "1", "yes")

        # 3. FLAG_DEFAULTS or caller-supplied default
        if default is not None:
            return default
        return FLAG_DEFAULTS.get(flag_name, False)

    def get_all_flags(self, user_id: Optional[str] = None) -> Dict[str, bool]:
        """Return the resolved state of all registered flags for a user."""
        return {
            name: self.is_enabled(name, user_id=user_id)
            for name in FLAG_DEFAULTS
        }

    def get_flag_metadata(self) -> Dict[str, Any]:
        """Return flag registry metadata for health/debug endpoints."""
        return {
            "posthog_connected": self._posthog_available,
            "registered_flags": list(FLAG_DEFAULTS.keys()),
            "flag_count": len(FLAG_DEFAULTS),
        }


# ---------------------------------------------------------------------------
# Module-level singleton — import and use directly:
#   from backend.feature_flags import flags
# ---------------------------------------------------------------------------
flags = FeatureFlagService()


def is_feature_enabled(
    flag_name: str,
    user_id: Optional[str] = None,
    default: Optional[bool] = None,
) -> bool:
    """Convenience function wrapping the module singleton."""
    return flags.is_enabled(flag_name, user_id=user_id, default=default)
