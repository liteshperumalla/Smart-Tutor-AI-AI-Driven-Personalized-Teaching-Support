"use client";

import posthog from "posthog-js";
import { PostHogProvider as PHProvider } from "posthog-js/react";
import { useEffect } from "react";

const POSTHOG_KEY = "phc_SaDDOcIq1AnKzpCsRHHpmRoDX7b8IEXNlv8xtPXNn7c";
const POSTHOG_HOST = "https://us.i.posthog.com";

export function PostHogProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    if (typeof window !== "undefined" && POSTHOG_KEY) {
      posthog.init(POSTHOG_KEY, {
        api_host: POSTHOG_HOST,
        capture_pageview: true,
        capture_pageleave: true,
        autocapture: false, // manual capture only — avoids noise from internal buttons
        persistence: "localStorage",
      });
    }
  }, []);

  return <PHProvider client={posthog}>{children}</PHProvider>;
}
