"use client";

import { useEffect } from "react";
import { beginGoogleSignIn, GOOGLE_START_PATH } from "@/lib/google-oauth";
import { getSafeNextPath } from "@/lib/safe-next";

const GOOGLE_AUTH_ORIGIN = "https://accounts.google.com";

/**
 * Starts Google sign-in on the OAuth callback's origin. A sign-in begun on
 * another origin comes here first, so the state nonce cookie is saved where
 * the callback can read it (see beginGoogleSignIn).
 */
export default function GoogleStartPage() {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const intent = params.get("intent") === "signup" ? "signup" : "login";
    const url = beginGoogleSignIn(intent, getSafeNextPath(params.get("next") ?? undefined));
    // Only ever leave for Google's sign-in page. Anything else (sign-in not
    // configured, or a URL back to this page because this isn't the
    // callback's origin, which would loop) goes back to the login page.
    // The query only carries the state; "next" inside it was already
    // limited to a same-site path by getSafeNextPath.
    let target: URL | null = null;
    try {
      target = url && !url.includes(GOOGLE_START_PATH) ? new URL(url) : null;
    } catch {
      target = null;
    }
    if (!target || target.origin !== GOOGLE_AUTH_ORIGIN) {
      window.location.replace("/login");
      return;
    }
    window.location.replace(`${GOOGLE_AUTH_ORIGIN}${target.pathname}${target.search}`);
  }, []);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-surface-2 px-4 text-center">
      <div className="max-w-md space-y-4 rounded-2xl border border-line bg-surface p-8 shadow">
        <h1 className="text-xl font-semibold text-foreground">Connecting Google account…</h1>
        <p className="text-sm text-muted">Redirecting to Google…</p>
      </div>
    </div>
  );
}
