"use client";

import { FormEvent, useMemo, useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { getApiBaseUrl } from "@/lib/api";
import { saveAuthToken } from "@/lib/auth";
import { GoogleAuthButton } from "@/components/google-auth-button";
import { User, Lock, LogIn, ArrowLeft } from "lucide-react";

type LoginResponse = {
  user: {
    username: string;
    email: string;
    full_name: string;
  };
  token_type: string;
  message: string;
};

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [unverified, setUnverified] = useState(false);
  const [resendMessage, setResendMessage] = useState<string | null>(null);
  const [isResending, setIsResending] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const signupSuccess = useMemo(
    () => searchParams.get("signup") === "success",
    [searchParams]
  );
  const signupVerified = useMemo(
    () => searchParams.get("signup") === "verified",
    [searchParams]
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setUnverified(false);
    setResendMessage(null);
    setIsSubmitting(true);

    try {
      const apiBaseUrl = getApiBaseUrl();
      const normalizedUsername = username.trim().replace(/\s+/g, "_");
      const response = await fetch(`${apiBaseUrl}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include", // Important: Include cookies in request/response
        body: JSON.stringify({ username: normalizedUsername, password: password.trim() }),
      });

      const payload = (await response.json().catch(() => ({}))) as
        | LoginResponse
        | { detail?: string };

      if (!response.ok) {
        const serverDetail = (payload as { detail?: string }).detail;
        const message = serverDetail ? `Unable to sign in: ${serverDetail}` : "Unable to sign in";
        if (serverDetail && serverDetail.toLowerCase().includes("email not verified")) {
          setUnverified(true);
        }
        throw new Error(message);
      }

      // Authentication successful - tokens are in HttpOnly cookies
      // Trigger auth state change event so useAuthToken hook updates
      saveAuthToken("authenticated");

      // Redirect to home page
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setIsSubmitting(false);
    }
  }

  async function handleResend() {
    setResendMessage(null);
    setError(null);
    setIsResending(true);
    try {
      const apiBaseUrl = getApiBaseUrl();
      const response = await fetch(`${apiBaseUrl}/auth/verify/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim() || undefined }),
      });
      const payload = (await response.json().catch(() => ({}))) as { detail?: string };
      if (!response.ok) {
        throw new Error(payload.detail || "Unable to resend verification code");
      }
      setResendMessage("Verification code sent. Check your email.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setIsResending(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Left: Visual side with atmosphere */}
      <div className="relative hidden lg:flex flex-col justify-center bg-zinc-900 overflow-hidden p-16">
        {/* Decorative background */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-0 right-0 h-96 w-96 bg-indigo-500 rounded-full blur-3xl animate-float"></div>
          <div className="absolute bottom-0 left-0 h-64 w-64 bg-purple-500 rounded-full blur-3xl" style={{animationDelay: '1.5s'}}></div>
        </div>

        <div className="relative z-10 text-white">
          <h2 className="font-display text-6xl font-bold leading-tight animate-fade-in-up">
            Learn Advanced<br />Computational Methods
          </h2>

          <p className="mt-6 text-xl text-white/80 max-w-xl animate-fade-in-up stagger-1">
            AI-powered tutoring that adapts to your learning style. Get instant help, generate quizzes, and ace your courses.
          </p>

          <div className="mt-12 space-y-4 animate-fade-in-up stagger-2">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 backdrop-blur">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span className="text-lg">24/7 AI tutor assistance</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 backdrop-blur">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span className="text-lg">Smart quiz generation</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 backdrop-blur">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span className="text-lg">Document research mode</span>
            </div>
          </div>
        </div>
      </div>

      {/* Right: Login form */}
      <div className="flex items-center justify-center p-8 bg-zinc-50 dark:bg-zinc-950">
        <div className="w-full max-w-md animate-scale-in">
          <div className="mb-10 text-center lg:text-left">
            <Link href="/" className="inline-flex items-center gap-2 text-sm font-semibold text-indigo-600 dark:text-indigo-400 hover:gap-3 transition-all">
              <span>←</span> Back to home
            </Link>
            <h1 className="font-display mt-6 text-4xl font-bold text-zinc-900 dark:text-white">
              Welcome back
            </h1>
            <p className="mt-3 text-zinc-600 dark:text-zinc-400">
              Sign in to continue your learning journey
            </p>
          </div>

          {signupSuccess && (
            <div className="mb-6 rounded-2xl border-2 border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300 animate-fade-in-down">
              <div className="flex items-center gap-2">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Account created successfully. Sign in with your new credentials.
              </div>
            </div>
          )}
          {signupVerified && (
            <div className="mb-6 rounded-2xl border-2 border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300 animate-fade-in-down">
              <div className="flex items-center gap-2">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Email verified. You can now sign in.
              </div>
            </div>
          )}

          <form
            onSubmit={handleSubmit}
            className="space-y-6 card animate-fade-in-up stagger-1"
          >
          <div className="space-y-2">
            <label
              htmlFor="username"
              className="text-sm font-medium text-zinc-900 dark:text-zinc-300"
            >
              Username / Email
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
              className="text-sm font-medium text-zinc-900 dark:text-zinc-300"
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
              <p className="font-medium">Sign-in failed</p>
              <p className="mt-0.5">{error}</p>
              {(error.toLowerCase().includes("incorrect") || error.toLowerCase().includes("invalid") || error.toLowerCase().includes("not found") || error.toLowerCase().includes("no account")) && (
                <p className="mt-2 border-t border-red-200 pt-2 dark:border-red-800">
                  No account?{" "}
                  <Link href="/signup" className="font-semibold underline hover:opacity-80">
                    Create one →
                  </Link>
                </p>
              )}
            </div>
          )}
          {unverified && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
              <p>Email not verified.</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={isResending}
                  className="btn-secondary"
                >
                  {isResending ? "Resending…" : "Resend code"}
                </button>
                <Link href={`/verify?username=${encodeURIComponent(username.trim())}`} className="btn-secondary">
                  Enter code
                </Link>
              </div>
              {resendMessage && <p className="mt-2 text-xs">{resendMessage}</p>}
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="btn-primary w-full disabled:cursor-not-allowed disabled:opacity-75 disabled:hover:scale-100"
          >
            {isSubmitting ? (
              <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Signing in…</>
            ) : (
              <>Sign in <span className="transition-transform group-hover:translate-x-1">→</span></>
            )}
          </button>

          <div className="space-y-3">
            <div className="text-center text-xs uppercase tracking-[0.3em] text-zinc-400 dark:text-zinc-500">
              or continue with Google
            </div>
            <GoogleAuthButton intent="login" />
          </div>
        </form>

        <div className="mt-8 space-y-3 text-center text-sm">
          <p className="text-zinc-600 dark:text-zinc-400">
            Don&apos;t have an account?{" "}
            <Link href="/signup" className="font-semibold text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">
              Create one →
            </Link>
          </p>
          <p className="text-zinc-600 dark:text-zinc-400">
            Forgot your password?{" "}
            <Link href="/password-reset/request" className="font-semibold text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">
              Reset it
            </Link>
          </p>
        </div>
      </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <p className="text-zinc-500">Loading...</p>
      </div>
    }>
      <LoginPageContent />
    </Suspense>
  );
}
