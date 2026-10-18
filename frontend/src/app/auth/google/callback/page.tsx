"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getApiBaseUrl } from "@/lib/api";
import { saveAuthToken } from "@/lib/auth";
import { getGoogleOAuthRedirectUri } from "@/lib/google-oauth";
import { getSafeNextPath } from "@/lib/safe-next";

// This page uses useSearchParams(), so must be dynamic
export const dynamic = "force-dynamic";

function GoogleCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState("Verifying Google sign-in…");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state") || "";
    if (!code) {
      setError("Missing authorization code.");
      return;
    }
    let intent = "login";
    let returnTo = "/";
    if (state) {
      try {
        const parsed = JSON.parse(atob(state));
        intent = parsed.intent || "login";
        returnTo = getSafeNextPath(parsed.next);
        // Read nonce from cookie (more reliable than sessionStorage on iOS Safari,
        // which can clear sessionStorage during cross-origin OAuth navigation)
        const cookieMatch = document.cookie.match(/(?:^|;\s*)google_oauth_nonce=([^;]*)/);
        const stored = cookieMatch ? decodeURIComponent(cookieMatch[1]) : null;
        if (!stored || parsed.nonce !== stored) {
          setError("Invalid or expired OAuth state.");
          return;
        }
        // Clear the nonce cookie
        document.cookie = "google_oauth_nonce=; path=/; max-age=0";
      } catch (err) {
        setError("Invalid OAuth state.");
        return;
      }
    } else {
      setError("Missing OAuth state.");
      return;
    }
    const run = async () => {
      try {
        const apiBaseUrl = getApiBaseUrl();
        const redirectUri = getGoogleOAuthRedirectUri(
          process.env.NEXT_PUBLIC_GOOGLE_REDIRECT_URI
        );
        const response = await fetch(`${apiBaseUrl}/auth/google/callback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include", // Required to store HttpOnly auth cookies from response
          body: JSON.stringify({ code, state: intent, redirect_uri: redirectUri }),
        });
        const payload = await response.json().catch(() => ({})) as {
          detail?: string;
          requires_password_setup?: boolean;
          password_setup_token?: string;
          username?: string;
        };

        if (response.status === 428 && payload.requires_password_setup) {
          if (payload.password_setup_token && payload.username) {
            const params = new URLSearchParams({
              token: payload.password_setup_token,
              username: payload.username,
            });
          params.set("next", returnTo);
          router.replace(`/password-setup?${params.toString()}`);
            return;
          }
          throw new Error("Password setup required but token missing.");
        }

        if (!response.ok) {
          throw new Error(payload.detail || "Failed to verify Google account.");
        }

        saveAuthToken("authenticated");
        setStatus("Signed in successfully. Redirecting…");
        setTimeout(() => {
          router.replace(returnTo);
        }, 800);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unexpected error.");
      }
    };
    run();
  }, [router, searchParams]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50 px-4 text-center">
      <div className="max-w-md space-y-4 rounded-2xl border border-zinc-200 bg-white p-8 shadow">
        <h1 className="text-xl font-semibold text-zinc-900">Connecting Google account…</h1>
        {error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : (
          <p className="text-sm text-zinc-600">{status}</p>
        )}
      </div>
    </div>
  );
}

export default function GoogleCallbackPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50 px-4 text-center">
        <div className="max-w-md space-y-4 rounded-2xl border border-zinc-200 bg-white p-8 shadow">
          <h1 className="text-xl font-semibold text-zinc-900">Loading…</h1>
        </div>
      </div>
    }>
      <GoogleCallbackContent />
    </Suspense>
  );
}
