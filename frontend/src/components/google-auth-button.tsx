"use client";

import { beginGoogleSignIn } from "@/lib/google-oauth";
import { getSafeNextPath } from "@/lib/safe-next";

type GoogleAuthButtonProps = {
  intent: "login" | "signup";
  returnTo?: string;
};

export function GoogleAuthButton({ intent, returnTo }: GoogleAuthButtonProps) {
  // The redirect URI always resolves in the browser (it falls back to this
  // origin's callback), so the client id alone says whether sign-in works,
  // and it reads the same on the server and the client.
  const ready = Boolean(process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID);

  const label =
    intent === "login" ? "Sign in with Google" : "Sign up with Google";

  const handleClick = () => {
    const url = beginGoogleSignIn(intent, getSafeNextPath(returnTo));
    if (url) window.location.href = url;
  };

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={handleClick}
        disabled={!ready}
        className="flex w-full items-center justify-center gap-2 rounded-xl border border-line bg-surface px-4 py-3 text-sm font-semibold text-foreground transition hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-60"
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
      {!ready && (
        <p className="text-center text-xs text-muted">
          Google sign-in is currently unavailable.
        </p>
      )}
    </div>
  );
}
