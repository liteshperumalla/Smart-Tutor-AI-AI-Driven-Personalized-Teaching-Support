#!/usr/bin/env python3
"""
System Monitoring and Health Check Tool
Displays cache statistics, Langfuse status, and feature configuration
"""

import json
import sys
from datetime import datetime


def print_section(title: str):
    """Print a section header"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def print_status_icon(status: str) -> str:
    """Return an icon for the status"""
    icons = {
        "healthy": "✅",
        "warning": "⚠️",
        "error": "❌",
        "disabled": "⭕",
        "unknown": "❓"
    }
    return icons.get(status.lower(), "❓")


def print_health_component(name: str, info: dict, indent: int = 0):
    """Print health component information"""
    prefix = "  " * indent
    status = info.get("status", "unknown")
    icon = print_status_icon(status)

    print(f"{prefix}{icon} {name.upper()}: {status.upper()}")

    if info.get("enabled") is not None:
        enabled_icon = "✓" if info.get("enabled") else "✗"
        print(f"{prefix}   Enabled: {enabled_icon}")

    if "message" in info:
        print(f"{prefix}   Message: {info['message']}")

    if "error" in info:
        print(f"{prefix}   Error: {info['error']}")

    if "backend" in info:
        print(f"{prefix}   Backend: {info['backend']}")

    if "statistics" in info and isinstance(info["statistics"], dict):
        print(f"{prefix}   Statistics:")
        for cache_name, cache_stats in info["statistics"].items():
            print(f"{prefix}     - {cache_name}:")
            for key, value in cache_stats.items():
                if key != 'backend':
                    print(f"{prefix}         {key}: {value}")


def print_feature_status(features: dict, phase_name: str):
    """Print feature status for a phase"""
    print(f"\n{phase_name}:")
    for feature_name, feature_info in features.items():
        if isinstance(feature_info, dict):
            if "enabled" in feature_info:
                icon = "✓" if feature_info["enabled"] else "✗"
                print(f"  {icon} {feature_name.replace('_', ' ').title()}")
                for key, value in feature_info.items():
                    if key != "enabled":
                        print(f"      {key}: {value}")
            else:
                print(f"  • {feature_name.replace('_', ' ').title()}")
                for key, value in feature_info.items():
                    print(f"      {key}: {value}")
        else:
            print(f"  • {feature_name.replace('_', ' ').title()}: {feature_info}")


def main():
    """Main function"""
    try:
        from backend.monitoring import get_monitoring_service
        from backend.config import config

        print_section("Smart AI Tutor - System Monitoring")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Environment: {config.ENVIRONMENT}")

        monitoring = get_monitoring_service()

        # System Health
        print_section("System Health")
        health = monitoring.get_system_health()
        overall_status = health.get("status", "unknown")
        icon = print_status_icon(overall_status)
        print(f"{icon} Overall Status: {overall_status.upper()}")
        print(f"⏱️  Uptime: {health.get('uptime_seconds', 0):.2f} seconds")

        # Components
        print("\nComponents:")
        for component_name, component_info in health.get("components", {}).items():
            print_health_component(component_name, component_info, indent=1)

        # Feature Status
        print_section("Feature Configuration")
        features = monitoring.get_feature_status()

        if "phase1" in features:
            print_feature_status(features["phase1"], "Phase 1: Foundation Improvements")

        if "phase2" in features:
            print_feature_status(features["phase2"], "Phase 2: Advanced Retrieval")

        if "phase3" in features:
            print_feature_status(features["phase3"], "Phase 3: Context & Quality")

        if "caching" in features:
            print_feature_status({"caching": features["caching"]}, "Caching")

        if "monitoring" in features:
            print_feature_status({"monitoring": features["monitoring"]}, "Monitoring")

        # Cache Statistics
        print_section("Cache Statistics")
        cache_stats = monitoring.get_cache_statistics()
        if "error" in cache_stats:
            print(f"❌ Error getting cache statistics: {cache_stats['error']}")
        elif not cache_stats:
            print("⭕ No cache statistics available")
        else:
            for cache_name, stats in cache_stats.items():
                print(f"\n{cache_name.upper()}:")
                for key, value in stats.items():
                    print(f"  {key}: {value}")

        # Recommendations
        print_section("Recommendations")
        recommendations = []

        # Check if Langfuse is configured
        langfuse_info = health.get("components", {}).get("langfuse", {})
        if langfuse_info.get("status") == "disabled":
            recommendations.append(
                "📊 Enable Langfuse monitoring for production observability:\n"
                "   Set LANGFUSE_ENABLED=true and configure API keys"
            )
        elif langfuse_info.get("status") == "warning":
            recommendations.append(
                "⚠️  Configure Langfuse API keys:\n"
                "   Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in .env"
            )

        # Check if Redis is enabled
        cache_info = health.get("components", {}).get("cache", {})
        if cache_info.get("backend") == "in-memory" and not config.REDIS_ENABLED:
            recommendations.append(
                "🚀 Enable Redis for better cache performance:\n"
                "   1. Install Redis: pip install redis\n"
                "   2. Start Redis server: redis-server\n"
                "   3. Set REDIS_ENABLED=true in .env"
            )

        # Check cache hit rate
        for cache_name, stats in cache_stats.items():
            hit_rate_str = stats.get("hit_rate", "0%")
            try:
                hit_rate = float(hit_rate_str.rstrip('%'))
                if hit_rate < 10 and stats.get("hits", 0) + stats.get("misses", 0) > 100:
                    recommendations.append(
                        f"📈 Low cache hit rate for {cache_name} ({hit_rate_str}):\n"
                        "   Consider increasing CACHE_TTL or investigating query patterns"
                    )
            except ValueError:
                pass

        # Check Phase 3 features
        phase3_info = health.get("components", {}).get("phase3_features", {})
        if phase3_info:
            features_phase3 = phase3_info.get("features", {})
            all_disabled = all(
                not feature.get("enabled", False)
                for feature in features_phase3.values()
            )
            if all_disabled:
                recommendations.append(
                    "🎯 Phase 3 features are all disabled:\n"
                    "   Consider enabling them for +20-30% accuracy improvement"
                )

        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                print(f"\n{i}. {rec}")
        else:
            print("✅ All systems optimally configured!")

        print("\n" + "=" * 80 + "\n")

    except Exception as e:
        print(f"❌ Error running monitoring check: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
