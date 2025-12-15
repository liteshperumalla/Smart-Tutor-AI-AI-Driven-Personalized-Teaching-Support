"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getApiBaseUrl } from "@/lib/api";
import { saveAuthToken } from "@/lib/auth";

export default function GoogleCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState("Verifying Google sign-in…");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state") || "login";
    if (!code) {
      setError("Missing authorization code.");
      return;
    }
    const run = async () => {
      try {
        const apiBaseUrl = getApiBaseUrl();
        const redirectUri =
          process.env.NEXT_PUBLIC_GOOGLE_REDIRECT_URI ||
          `${window.location.origin}/auth/google/callback`;
        const response = await fetch(`${apiBaseUrl}/auth/google/callback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, state, redirect_uri: redirectUri }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(payload.detail || "Failed to verify Google account.");
        }
        if (payload.token) {
          saveAuthToken(payload.token);
        }
        setStatus("Signed in successfully. Redirecting…");
        setTimeout(() => {
          router.replace("/");
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
