"use client";

import { FormEvent, useMemo, useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { getApiBaseUrl } from "@/lib/api";
import { saveAuthToken } from "@/lib/auth";
import { GoogleAuthButton } from "@/components/google-auth-button";
import { LogoMark } from "@/components/logo-mark";
import { getSafeNextPath } from "@/lib/safe-next";
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
  const returnTo = useMemo(() => getSafeNextPath(searchParams.get("next")), [searchParams]);

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

      router.push(returnTo);
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
      {/* Left: modern split — brand bar + gradient headline */}
      <div className="relative hidden lg:flex flex-col gap-6 overflow-hidden p-12 text-white" style={{ background: "#0F172A" }}>
        {/* Ambient brand glows */}
        <div className="pointer-events-none absolute top-28 -right-20 h-80 w-80 rounded-full blur-[100px] animate-float" style={{ background: "rgba(20,184,166,0.20)" }}></div>
        <div className="pointer-events-none absolute bottom-16 -left-24 h-72 w-72 rounded-full blur-[100px]" style={{ background: "rgba(59,130,246,0.22)", animationDelay: "1.5s" }}></div>

        {/* Brand bar */}
        <div className="relative z-10 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <LogoMark size={34} />
            <span className="font-display text-[17px] font-bold tracking-tight">Smart AI Tutor</span>
          </div>
        </div>

        {/* Headline */}
        <div className="relative z-10 flex flex-1 flex-col justify-center">
          <h2 className="font-display text-5xl font-bold leading-[1.04] tracking-tight animate-fade-in-up">
            Learn across{" "}
            <span style={{ backgroundImage: "linear-gradient(90deg, #93C5FD, #5EEAD4)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
              your courses
            </span>.
          </h2>
          <p className="mt-4 max-w-md text-base leading-relaxed text-white/65 animate-fade-in-up stagger-1">
            Grounded answers and targeted practice, sourced from your enrolled courses.
          </p>
        </div>

        {/* Footer note */}
        <div className="relative z-10 text-[11px] tracking-wide text-white/40">
          Built for university learners and instructors
        </div>
      </div>

      {/* Right: Login form */}
      <div className="flex items-center justify-center p-8 bg-surface-2">
        <div className="w-full max-w-md animate-scale-in">
          <div className="mb-10 text-center lg:text-left">
            <Link href="/" className="inline-flex items-center gap-2 text-sm font-semibold text-success hover:gap-3 transition-all">
              <span>←</span> Back to home
            </Link>
            <h1 className="font-display mt-6 text-4xl font-bold text-foreground">
              Welcome back
            </h1>
            <p className="mt-3 text-muted">
              Sign in to continue your learning journey
            </p>
          </div>

          {signupSuccess && (
            <div className="mb-6 rounded-2xl border-2 border-success/30 bg-success-bg px-4 py-3 text-sm text-success animate-fade-in-down">
              <div className="flex items-center gap-2">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Account created successfully. Sign in with your new credentials.
              </div>
            </div>
          )}
          {signupVerified && (
            <div className="mb-6 rounded-2xl border-2 border-success/30 bg-success-bg px-4 py-3 text-sm text-success animate-fade-in-down">
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
              className="text-sm font-medium text-foreground"
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
              className="input"
              placeholder="your@email.edu"
            />
          </div>

          <div className="space-y-2">
            <label
              htmlFor="password"
              className="text-sm font-medium text-foreground"
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
              className="input"
              placeholder="********"
            />
          </div>

          {error && (
            <div className="rounded-xl border border-danger/30 bg-danger-bg px-4 py-3 text-sm text-danger">
              <p className="font-medium">Sign-in failed</p>
              <p className="mt-0.5">{error}</p>
              {(error.toLowerCase().includes("incorrect") || error.toLowerCase().includes("invalid") || error.toLowerCase().includes("not found") || error.toLowerCase().includes("no account")) && (
                <p className="mt-2 border-t border-danger/30 pt-2">
                  No account?{" "}
                  <Link href="/signup" className="font-semibold underline hover:opacity-80">
                    Create one →
                  </Link>
                </p>
              )}
            </div>
          )}
          {unverified && (
            <div className="rounded-xl border border-warning/40 bg-warning-bg px-4 py-3 text-sm text-warning">
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
            <div className="text-center text-xs uppercase tracking-[0.2em] text-muted">
              or continue with Google
            </div>
          <GoogleAuthButton intent="login" returnTo={returnTo} />
          </div>
        </form>

        <div className="mt-8 space-y-3 text-center text-sm">
          <p className="text-muted">
            Don&apos;t have an account?{" "}
            <Link href="/signup" className="font-semibold text-success hover:text-success">
              Create one →
            </Link>
          </p>
          <p className="text-muted">
            Forgot your password?{" "}
            <Link href="/password-reset/request" className="font-semibold text-success hover:text-success">
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
      <div className="flex min-h-screen items-center justify-center bg-surface-2">
        <p className="text-muted">Loading...</p>
      </div>
    }>
      <LoginPageContent />
    </Suspense>
  );
}
