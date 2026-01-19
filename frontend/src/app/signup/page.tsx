"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getApiBaseUrl } from "@/lib/api";
import { GoogleAuthButton } from "@/components/google-auth-button";
import { User, Mail, Lock, UserPlus, ArrowLeft } from "lucide-react";

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
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Left: Visual side with atmosphere */}
      <div className="relative hidden lg:flex flex-col justify-center bg-gradient-to-br from-amber-500 via-orange-500 to-pink-500 overflow-hidden p-16">
        {/* Decorative background */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-0 right-0 h-96 w-96 bg-white rounded-full blur-3xl animate-float"></div>
          <div className="absolute bottom-0 left-0 h-64 w-64 bg-purple-300 rounded-full blur-3xl" style={{animationDelay: '1.5s'}}></div>
        </div>

        <div className="relative z-10 text-white">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-2 text-sm font-medium backdrop-blur mb-8 animate-fade-in-down">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white opacity-75"></span>
              <span className="relative inline-flex h-2 w-2 rounded-full bg-white"></span>
            </span>
            Join thousands of learners
          </div>

          <h2 className="font-display text-6xl font-bold leading-tight animate-fade-in-up">
            Start Your<br />Learning Journey
          </h2>

          <p className="mt-6 text-xl text-white/80 max-w-xl animate-fade-in-up stagger-1">
            Create your account and unlock AI-powered tutoring, personalized quizzes, and intelligent study tools.
          </p>

          <div className="mt-12 space-y-4 animate-fade-in-up stagger-2">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 backdrop-blur">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span className="text-lg">Free to get started</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 backdrop-blur">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span className="text-lg">Instant access to all features</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 backdrop-blur">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span className="text-lg">No credit card required</span>
            </div>
          </div>
        </div>
      </div>

      {/* Right: Signup form */}
      <main className="flex items-center justify-center p-8 bg-zinc-50 dark:bg-zinc-950">
        <div className="w-full max-w-md animate-scale-in">
          <div className="mb-10 text-center lg:text-left">
            <Link href="/" className="inline-flex items-center gap-2 text-sm font-semibold text-indigo-600 dark:text-indigo-400 hover:gap-3 transition-all">
              <span>←</span> Back to home
            </Link>
            <h1 className="font-display mt-6 text-4xl font-bold text-zinc-900 dark:text-white">
              Create your account
            </h1>
            <p className="mt-3 text-zinc-600 dark:text-zinc-400">
              Get started with Smart AI Tutor in seconds
            </p>
          </div>

          <form
            onSubmit={handleSubmit}
            className="space-y-5 card animate-fade-in-up stagger-1"
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
                className="input"
                placeholder="your@email.edu"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Email <span className="text-zinc-400">(optional)</span>
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="input"
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
                className="input"
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
                className="input"
                placeholder="Repeat password"
              />
            </div>

            {error && (
              <div className="rounded-xl border-2 border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary w-full disabled:cursor-not-allowed disabled:opacity-75 disabled:hover:scale-100"
            >
              {isSubmitting ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Creating account…</>
              ) : (
                <>Create account <span className="transition-transform group-hover:translate-x-1">→</span></>
              )}
            </button>

            <div className="space-y-3">
              <div className="text-center text-xs uppercase tracking-[0.3em] text-zinc-400 dark:text-zinc-500">
                or sign up with Google
              </div>
              <GoogleAuthButton intent="signup" />
            </div>
          </form>

          <div className="mt-8 text-center text-sm">
            <p className="text-zinc-600 dark:text-zinc-400">
              Already registered?{" "}
              <Link href="/login" className="font-semibold text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">
                Sign in →
              </Link>
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
