"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getApiBaseUrl } from "@/lib/api";
import { GoogleAuthButton } from "@/components/google-auth-button";
import { CheckCircle, XCircle } from "lucide-react";

type SignupResponse = {
  user?: { username: string };
};

type PydanticDetail = { loc: string[]; msg: string; type: string };
type PasswordErrorDetail = { message?: string; requirements?: string[] };

function parseApiError(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "Unexpected error";
  const p = payload as Record<string, unknown>;
  if (Array.isArray(p.detail)) {
    // Pydantic 422 validation error
    const items = p.detail as PydanticDetail[];
    const first = items[0];
    if (first) {
      const field = first.loc[first.loc.length - 1];
      const msg = first.msg.replace(/^Value error,\s*/i, "");
      return field ? `${String(field).replace("_", " ")}: ${msg}` : msg;
    }
  }
  if (p.detail && typeof p.detail === "object") {
    const detail = p.detail as PasswordErrorDetail;
    if (typeof detail.message === "string" && Array.isArray(detail.requirements) && detail.requirements.length > 0) {
      return `${detail.message}: ${detail.requirements[0]}`;
    }
    if (typeof detail.message === "string") return detail.message;
  }
  if (typeof p.detail === "string") return p.detail;
  return "Unexpected error. Please try again.";
}

const PASSWORD_SPECIAL_REGEX = /[!@#$%^&*(),.?":{}|<>]/;

const PASSWORD_RULES = [
  { label: "At least 12 characters", test: (p: string) => p.length >= 12 },
  { label: "Uppercase letter", test: (p: string) => /[A-Z]/.test(p) },
  { label: "Lowercase letter", test: (p: string) => /[a-z]/.test(p) },
  { label: "Number", test: (p: string) => /\d/.test(p) },
  { label: "Special character (!@#$…)", test: (p: string) => PASSWORD_SPECIAL_REGEX.test(p) },
];

export default function SignupPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [passwordTouched, setPasswordTouched] = useState(false);

  const passwordRuleResults = PASSWORD_RULES.map((r) => ({
    ...r,
    passed: r.test(password),
  }));
  const allRulesPassed = passwordRuleResults.every((r) => r.passed);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (!allRulesPassed) {
      setError("Please satisfy all password requirements before continuing.");
      return;
    }

    setIsSubmitting(true);

    try {
      const apiBaseUrl = getApiBaseUrl();
      const response = await fetch(`${apiBaseUrl}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          password,
          confirm_password: confirmPassword,
          email,
        }),
      });

      const payload = (await response.json().catch(() => ({}))) as
        | SignupResponse
        | { detail?: unknown };

      if (!response.ok) {
        throw new Error(parseApiError(payload));
      }

      const params = new URLSearchParams({
        username: username.trim(),
        email: email.trim(),
      });
      router.push(`/verify?${params.toString()}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Left: Visual side */}
      <div className="relative hidden lg:flex flex-col justify-center bg-zinc-900 overflow-hidden p-16">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-0 right-0 h-96 w-96 bg-emerald-500 rounded-full blur-3xl animate-float"></div>
          <div className="absolute bottom-0 left-0 h-64 w-64 bg-teal-500 rounded-full blur-3xl" style={{ animationDelay: "1.5s" }}></div>
        </div>
        <div className="relative z-10 text-white">
          <h2 className="font-display text-6xl font-bold leading-tight animate-fade-in-up">
            Start Your<br />Learning Journey
          </h2>
          <p className="mt-6 text-xl text-white/80 max-w-xl animate-fade-in-up stagger-1">
            Create your account and unlock AI-powered tutoring, personalized quizzes, and intelligent study tools.
          </p>
          <div className="mt-12 space-y-4 animate-fade-in-up stagger-2">
            {["Free to get started", "Instant access to all features", "No credit card required"].map((text) => (
              <div key={text} className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 backdrop-blur">
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <span className="text-lg">{text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right: Signup form */}
      <div className="flex items-center justify-center p-8 bg-zinc-50 dark:bg-zinc-950">
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

          <form onSubmit={handleSubmit} className="space-y-5 card animate-fade-in-up stagger-1">
            {/* Username */}
            <div className="space-y-2">
              <label htmlFor="username" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Username
              </label>
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input"
                placeholder="johndoe123"
              />
            </div>

            {/* Email */}
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input"
                placeholder="student@unt.edu"
              />
            </div>

            {/* Password */}
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="new-password"
                required
                value={password}
                onChange={(e) => { setPassword(e.target.value); setPasswordTouched(true); }}
                className="input"
                placeholder="Create a strong password"
              />
              {/* Live password rules */}
              {passwordTouched && (
                <ul className="mt-2 space-y-1">
                  {passwordRuleResults.map((r) => (
                    <li key={r.label} className={`flex items-center gap-2 text-xs ${r.passed ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}`}>
                      {r.passed
                        ? <CheckCircle className="h-3.5 w-3.5 shrink-0" />
                        : <XCircle className="h-3.5 w-3.5 shrink-0" />}
                      {r.label}
                    </li>
                  ))}
                </ul>
              )}
              {!passwordTouched && (
                <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">
                  Must be 12+ characters with uppercase, lowercase, number &amp; special character.
                </p>
              )}
            </div>

            {/* Confirm password */}
            <div className="space-y-2">
              <label htmlFor="confirmPassword" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Confirm password
              </label>
              <input
                id="confirmPassword"
                name="confirmPassword"
                type="password"
                autoComplete="new-password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={`input ${confirmPassword && confirmPassword !== password ? "border-red-400 focus:border-red-500 focus:ring-red-500/10" : ""}`}
                placeholder="Repeat password"
              />
              {confirmPassword && confirmPassword !== password && (
                <p className="mt-1 text-xs text-red-500">Passwords do not match.</p>
              )}
            </div>

            {/* Global error */}
            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400">
                <p className="font-medium">Unable to create account</p>
                <p className="mt-0.5">{error}</p>
                {(error.toLowerCase().includes("email already") || error.toLowerCase().includes("already exists")) && (
                  <p className="mt-2 border-t border-red-200 pt-2 dark:border-red-800">
                    Already have an account?{" "}
                    <Link href="/login" className="font-semibold underline hover:opacity-80">
                      Sign in →
                    </Link>
                  </p>
                )}
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
      </div>
    </div>
  );
}
