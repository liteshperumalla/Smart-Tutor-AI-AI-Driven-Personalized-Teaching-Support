"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { getApiBaseUrl } from "@/lib/api";
import { saveAuthToken } from "@/lib/auth";
import { GoogleAuthButton } from "@/components/google-auth-button";

type LoginResponse = {
  token: string;
  user?: { username: string };
};

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const signupSuccess = useMemo(
    () => searchParams.get("signup") === "success",
    [searchParams]
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const apiBaseUrl = getApiBaseUrl();
      const normalizedUsername = username.trim().replace(/\s+/g, "_");
      const response = await fetch(`${apiBaseUrl}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username: normalizedUsername, password: password.trim() }),
      });

      const payload = (await response.json().catch(() => ({}))) as
        | LoginResponse
        | { detail?: string };

      if (!response.ok) {
        const serverDetail = (payload as { detail?: string }).detail;
        throw new Error(serverDetail ? `Unable to sign in: ${serverDetail}` : "Unable to sign in");
      }

      if (payload.token) {
        saveAuthToken(payload.token);
      }

      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-zinc-950">
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-12">
        <div className="mb-10 text-center">
          <Link href="/" className="text-sm font-semibold text-blue-600 dark:text-blue-400">
            ← Back to home
          </Link>
          <h1 className="mt-4 text-2xl font-semibold text-zinc-900 dark:text-white">
            Sign in to Smart AI Tutor
          </h1>
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            Use the same credentials you created in the FastAPI backend.
          </p>
        </div>

        {signupSuccess && (
          <div className="mb-6 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300">
            Account created successfully. Sign in with your new credentials.
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="space-y-6 rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
        >
          <div className="space-y-2">
            <label
              htmlFor="username"
              className="text-sm font-medium text-zinc-700 dark:text-zinc-300"
            >
              Username
            </label>
            <input
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="w-full rounded-xl border border-zinc-200 px-4 py-3 text-sm text-zinc-900 outline-none ring-0 transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:focus:border-zinc-500"
              placeholder="your@email.edu"
            />
          </div>

          <div className="space-y-2">
            <label
              htmlFor="password"
              className="text-sm font-medium text-zinc-700 dark:text-zinc-300"
            >
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-xl border border-zinc-200 px-4 py-3 text-sm text-zinc-900 outline-none ring-0 transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:focus:border-zinc-500"
              placeholder="********"
            />
          </div>

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-xl bg-zinc-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-75 dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-100"
          >
            {isSubmitting ? "Signing in…" : "Sign in"}
          </button>

          <div className="space-y-3">
            <div className="text-center text-xs uppercase tracking-[0.3em] text-zinc-400 dark:text-zinc-500">
              or continue with Google
            </div>
            <GoogleAuthButton intent="login" />
          </div>
        </form>

        <p className="mt-8 text-center text-sm text-zinc-500 dark:text-zinc-400">
          Don't have an account?{" "}
          <Link href="/signup" className="font-medium text-zinc-900 underline dark:text-white">
            Create one
          </Link>
        </p>
      </main>
    </div>
  );
}
