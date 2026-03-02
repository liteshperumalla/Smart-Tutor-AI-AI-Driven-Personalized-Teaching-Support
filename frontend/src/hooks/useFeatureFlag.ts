"use client";

import { useFeatureFlagEnabled, useFeatureFlagPayload } from "posthog-js/react";

/**
 * Known PostHog feature flag keys for this project.
 * Add new keys here as flags are created in the PostHog dashboard.
 */
export type FeatureFlagKey =
  | "agent-system-enabled"
  | "enhanced-rag-enabled"
  | "llm-routing-enabled";

/**
 * Returns true/false for a boolean PostHog feature flag.
 * Falls back to `fallback` (default: false) when PostHog isn't loaded
 * or the flag isn't defined for the current user.
 *
 * Usage:
 *   const agentsEnabled = useFeatureFlag("agent-system-enabled");
 *   const ragEnabled = useFeatureFlag("enhanced-rag-enabled", true);
 */
export function useFeatureFlag(
  flagKey: FeatureFlagKey,
  fallback = false
): boolean {
  // useFeatureFlagEnabled returns undefined while loading, true/false when resolved
  const flagValue = useFeatureFlagEnabled(flagKey);
  return flagValue ?? fallback;
}

/**
 * Returns the payload (string/object) of a multivariate PostHog flag.
 * Useful for flags that carry configuration values rather than just on/off.
 *
 * Usage:
 *   const variant = useFeatureFlagVariant("llm-routing-enabled");
 */
export function useFeatureFlagVariant(flagKey: FeatureFlagKey) {
  return useFeatureFlagPayload(flagKey);
}
