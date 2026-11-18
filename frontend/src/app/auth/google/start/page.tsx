"use client";

import { useEffect } from "react";
import { beginGoogleSignIn, GOOGLE_START_PATH } from "@/lib/google-oauth";
import { getSafeNextPath } from "@/lib/safe-next";

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
    // Only ever leave for Google from here: a URL back to this page means
    // this isn't the callback's origin, and following it would loop. Sign-in
    // isn't available from here then, so go back to the login page.
    if (!url || url.includes(GOOGLE_START_PATH)) {
      window.location.replace("/login");
      return;
    }
    window.location.replace(url);
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
