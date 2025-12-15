"use client";

import { useMemo } from "react";

type GoogleAuthButtonProps = {
  intent: "login" | "signup";
};

export function GoogleAuthButton({ intent }: GoogleAuthButtonProps) {
  const config = useMemo(() => {
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    const redirectEnv = process.env.NEXT_PUBLIC_GOOGLE_REDIRECT_URI;
    const fallbackRedirect =
      typeof window !== "undefined"
        ? `${window.location.origin}/auth/google/callback`
        : undefined;
    const redirectUri = redirectEnv || fallbackRedirect;

    if (!clientId || !redirectUri) {
      return { ready: false } as const;
    }

    const params = new URLSearchParams({
      client_id: clientId,
      redirect_uri: redirectUri,
      response_type: "code",
      scope: "openid email profile",
      access_type: "offline",
      prompt: "consent",
      state: intent,
    });

    return {
      ready: true,
      url: `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`,
    } as const;
  }, [intent]);

  const label =
    intent === "login" ? "Sign in with Google" : "Sign up with Google";

  const handleClick = () => {
    if (config.ready && config.url) {
      window.location.href = config.url;
    }
  };

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={handleClick}
        disabled={!config.ready || !config.url}
        className="flex w-full items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm font-semibold text-zinc-900 transition hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60"
      >
        <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
          <path
            d="M17.64 9.2c0-.64-.06-1.25-.18-1.84H9v3.48h4.84a4.14 4.14 0 01-1.8 2.72v2.26h2.9c1.7-1.57 2.68-3.9 2.68-6.62z"
            fill="#4285F4"
          />
          <path
            d="M9 18c2.43 0 4.47-.8 5.96-2.17l-2.9-2.26c-.8.54-1.82.86-3.06.86-2.35 0-4.33-1.59-5.04-3.72H.96v2.34A9 9 0 009 18z"
            fill="#34A853"
          />
          <path
            d="M3.96 10.71A5.41 5.41 0 013.68 9c0-.59.1-1.17.28-1.71V4.95H.96A9 9 0 000 9c0 1.44.34 2.8.96 4.05l2.99-2.34z"
            fill="#FBBC05"
          />
          <path
            d="M9 3.58c1.32 0 2.5.45 3.44 1.32l2.58-2.58C13.47.89 11.43 0 9 0A9 9 0 000 4.95l2.99 2.34C3.7 5.16 5.68 3.58 9 3.58z"
            fill="#EA4335"
          />
        </svg>
        {label}
      </button>
      {!config.ready && (
        <p className="text-center text-xs text-zinc-400">
          Google authentication not configured. Set NEXT_PUBLIC_GOOGLE_* env
          vars.
        </p>
      )}
    </div>
  );
}
