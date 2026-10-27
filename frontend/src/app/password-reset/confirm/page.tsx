"use client";

import { FormEvent, useEffect, useState, Suspense } from "react";
import { clearAuthHandoff, readAuthHandoff } from "@/lib/auth-handoff";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { getApiBaseUrl } from "@/lib/api";
import { SkeletonAuthForm } from "@/components/skeleton";

type PasswordErrorDetail = { message?: string; requirements?: string[] };

const PASSWORD_SPECIAL_REGEX = /[!@#$%^&*(),.?":{}|<>]/;
const PASSWORD_RULES = [
  { test: (p: string) => p.length >= 12, message: "at least 12 characters" },
  { test: (p: string) => /[A-Z]/.test(p), message: "an uppercase letter" },
  { test: (p: string) => /[a-z]/.test(p), message: "a lowercase letter" },
  { test: (p: string) => /\d/.test(p), message: "a number" },
  { test: (p: string) => PASSWORD_SPECIAL_REGEX.test(p), message: "a special character like !@#$" },
];

function parseApiError(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "Unable to reset password.";
  const p = payload as Record<string, unknown>;
  if (p.detail && typeof p.detail === "object") {
    const detail = p.detail as PasswordErrorDetail;
    if (typeof detail.message === "string" && Array.isArray(detail.requirements) && detail.requirements.length > 0) {
      return `${detail.message}: ${detail.requirements[0]}`;
    }
    if (typeof detail.message === "string") return detail.message;
  }
  if (typeof p.detail === "string") return p.detail;
  return "Unable to reset password.";
}

function PasswordResetConfirmPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handoff = readAuthHandoff("password-reset", searchParams);
    if (handoff.token) {
      setToken(handoff.token);
    }
    if (handoff.username) {
      setUsername(handoff.username);
    }
    // Keep the reset token and username out of history, logs and Referer.
    if (handoff.fromUrl) {
      router.replace("/password-reset/confirm");
    }
  }, [router, searchParams]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!username.trim() || !token.trim()) {
      setError("Provide both username and reset token.");
      return;
    }
    const failedRule = PASSWORD_RULES.find((rule) => !rule.test(password));
    if (failedRule) {
      setError(`Password must include ${failedRule.message}.`);
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setStatus("loading");
    try {
      const apiBaseUrl = getApiBaseUrl();
      const response = await fetch(`${apiBaseUrl}/auth/password/reset/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: username.trim(),
          token: token.trim(),
          new_password: password,
          confirm_password: confirmPassword,
        }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(parseApiError(payload));
      }

      clearAuthHandoff("password-reset");
      setStatus("success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reset password.");
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
            Set a new password
          </h1>
          <p className="mt-2 text-sm text-muted">
            Paste the token from your email if it didn’t auto-fill.
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
              Reset token
            </label>
            <input
              value={token}
              onChange={(event) => setToken(event.target.value)}
              className="input"
              placeholder="Paste the token from email"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              New password
            </label>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="input"
              placeholder="12+ chars, upper/lower/number/special"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Confirm password
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              className="input"
              placeholder="Repeat password"
            />
          </div>

          {error && (
            <div className="rounded-xl border border-danger/30 bg-danger-bg px-4 py-3 text-sm text-danger">
              {error}
            </div>
          )}

          {status === "success" && (
            <div className="rounded-xl border border-success/30 bg-success-bg px-4 py-3 text-sm text-success">
              Password updated. You can now sign in.
            </div>
          )}

          <button
            type="submit"
            disabled={status === "loading"}
            className="w-full btn-primary disabled:cursor-not-allowed disabled:opacity-75 disabled:hover:scale-100"
          >
            {status === "loading" ? (
              <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Updating…</>
            ) : (
              "Reset password"
            )}
          </button>

          <div className="text-center text-sm text-muted">
            Remembered your password?{" "}
            <Link href="/login" className="font-medium text-foreground underline">
              Sign in
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function PasswordResetConfirmPage() {
  return (
    <Suspense fallback={
      <SkeletonAuthForm label="Loading password reset" fields={3} />
    }>
      <PasswordResetConfirmPageContent />
    </Suspense>
  );
}
