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
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-zinc-950">
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-12">
        <div className="mb-8 text-center">
          <Link href="/login" className="text-sm font-semibold text-blue-600 dark:text-blue-400">
            ← Back to sign in
          </Link>
          <h1 className="mt-4 text-2xl font-semibold text-zinc-900 dark:text-white">
            Reset your password
          </h1>
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            We’ll email a reset link if the account exists.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-5 rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
        >
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Username
            </label>
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="w-full rounded-xl border border-zinc-200 px-4 py-3 text-sm text-zinc-900 outline-none ring-0 transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:focus:border-zinc-500"
              placeholder="your@email.edu"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-xl border border-zinc-200 px-4 py-3 text-sm text-zinc-900 outline-none ring-0 transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:focus:border-zinc-500"
              placeholder="student@unt.edu"
            />
          </div>

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400">
              {error}
            </div>
          )}

          {status === "success" && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300">
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
