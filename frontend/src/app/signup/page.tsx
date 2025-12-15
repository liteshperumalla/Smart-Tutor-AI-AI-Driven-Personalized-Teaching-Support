"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getApiBaseUrl } from "@/lib/api";
import { GoogleAuthButton } from "@/components/google-auth-button";

type SignupResponse = {
  user?: { username: string };
};

export default function SignupPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setIsSubmitting(true);

    try {
      const apiBaseUrl = getApiBaseUrl();
      const response = await fetch(`${apiBaseUrl}/auth/signup`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username,
          password,
          confirm_password: confirmPassword,
          email: email || undefined,
        }),
      });

      const payload = (await response.json().catch(() => ({}))) as
        | SignupResponse
        | { detail?: string };

      if (!response.ok) {
        throw new Error(
          (payload as { detail?: string }).detail || "Unable to sign up"
        );
      }

      router.push("/login?signup=success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
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
            Create a Smart AI Tutor account
          </h1>
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            Access the FastAPI + Next.js experience with your credentials.
          </p>
        </div>

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
            <label htmlFor="email" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Email (optional)
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-xl border border-zinc-200 px-4 py-3 text-sm text-zinc-900 outline-none ring-0 transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:focus:border-zinc-500"
              placeholder="student@unt.edu"
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
              autoComplete="new-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-xl border border-zinc-200 px-4 py-3 text-sm text-zinc-900 outline-none ring-0 transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:focus:border-zinc-500"
              placeholder="Min 8 characters"
            />
          </div>

          <div className="space-y-2">
            <label
              htmlFor="confirmPassword"
              className="text-sm font-medium text-zinc-700 dark:text-zinc-300"
            >
              Confirm password
            </label>
            <input
              id="confirmPassword"
              name="confirmPassword"
              type="password"
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              className="w-full rounded-xl border border-zinc-200 px-4 py-3 text-sm text-zinc-900 outline-none ring-0 transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:focus:border-zinc-500"
              placeholder="Repeat password"
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
            {isSubmitting ? "Creating account…" : "Create account"}
          </button>

          <div className="space-y-3">
            <div className="text-center text-xs uppercase tracking-[0.3em] text-zinc-400 dark:text-zinc-500">
              or sign up with Google
            </div>
            <GoogleAuthButton intent="signup" />
          </div>
        </form>

        <p className="mt-8 text-center text-sm text-zinc-500 dark:text-zinc-400">
          Already registered?{" "}
          <Link href="/login" className="font-medium text-zinc-900 underline dark:text-white">
            Sign in
          </Link>
        </p>
      </main>
    </div>
  );
}
