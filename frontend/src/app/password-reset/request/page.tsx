"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { getApiBaseUrl } from "@/lib/api";

export default function PasswordResetRequestPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!username.trim() && !email.trim()) {
      setError("Enter your username or email.");
      return;
    }

    setStatus("loading");
    try {
      const apiBaseUrl = getApiBaseUrl();
      const redirectUrl = `${window.location.origin}/password-reset/confirm`;
      const response = await fetch(`${apiBaseUrl}/auth/password/reset/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: username.trim() || undefined,
          email: email.trim() || undefined,
          redirect_url: redirectUrl,
        }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Unable to request a reset email.");
      }

      setStatus("success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to request a reset email.");
      setStatus("error");
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-surface-2">
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-12">
        <div className="mb-8 text-center">
          <Link href="/login" className="text-sm font-semibold text-primary">
            ← Back to sign in
          </Link>
          <h1 className="mt-4 text-2xl font-semibold text-foreground">
            Reset your password
          </h1>
          <p className="mt-2 text-sm text-muted">
            We’ll email a reset link if the account exists.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-5 rounded-2xl border border-line bg-surface p-8 shadow-sm"
        >
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Username
            </label>
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="input"
              placeholder="your@email.edu"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="input"
              placeholder="student@unt.edu"
            />
          </div>

          {error && (
            <div className="rounded-xl border border-danger/30 bg-danger-bg px-4 py-3 text-sm text-danger">
              {error}
            </div>
          )}

          {status === "success" && (
            <div className="rounded-xl border border-success/30 bg-success-bg px-4 py-3 text-sm text-success">
              If the account exists, we’ve sent a reset email.
            </div>
          )}

          <button
            type="submit"
            disabled={status === "loading"}
            className="w-full btn-primary disabled:cursor-not-allowed disabled:opacity-75 disabled:hover:scale-100"
          >
            {status === "loading" ? (
              <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Sending…</>
            ) : (
              "Send reset link"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
