"use client";

import { FormEvent, Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { getApiBaseUrl } from "@/lib/api";
import { saveAuthToken } from "@/lib/auth";
import { CheckCircle, XCircle } from "lucide-react";

const SETUP_TOKEN_STORAGE_KEY = "password_setup_token";
const SETUP_USERNAME_STORAGE_KEY = "password_setup_username";

type PydanticDetail = { loc: string[]; msg: string; type: string };

const PASSWORD_RULES = [
  { label: "At least 12 characters", test: (p: string) => p.length >= 12 },
  { label: "Uppercase letter", test: (p: string) => /[A-Z]/.test(p) },
  { label: "Lowercase letter", test: (p: string) => /[a-z]/.test(p) },
  { label: "Number", test: (p: string) => /\d/.test(p) },
  { label: "Special character (!@#$…)", test: (p: string) => /[^A-Za-z0-9]/.test(p) },
];

function parseApiError(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "Unable to set password";
  const p = payload as Record<string, unknown>;
  if (Array.isArray(p.detail)) {
    const items = p.detail as PydanticDetail[];
    const first = items[0];
    if (first) {
      const field = first.loc[first.loc.length - 1];
      return field ? `${String(field).replace("_", " ")}: ${first.msg}` : first.msg;
    }
  }
  if (typeof p.detail === "string") return p.detail;
  return "Unable to set password";
}

function PasswordSetupContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [passwordTouched, setPasswordTouched] = useState(false);
  const hasSanitizedUrlRef = useRef(false);

  const passwordRuleResults = PASSWORD_RULES.map((r) => ({
    ...r,
    passed: r.test(password),
  }));
  const allRulesPassed = passwordRuleResults.every((r) => r.passed);

  useEffect(() => {
    // Read token and username from URL query params (passed by the Google callback).
    const urlToken = searchParams.get("token");
    const urlUsername = searchParams.get("username");

    if (urlToken) {
      sessionStorage.setItem(SETUP_TOKEN_STORAGE_KEY, urlToken);
      setToken(urlToken);
    } else {
      const cachedToken = sessionStorage.getItem(SETUP_TOKEN_STORAGE_KEY);
      if (cachedToken) {
        setToken(cachedToken);
      }
    }

    if (urlUsername) {
      sessionStorage.setItem(SETUP_USERNAME_STORAGE_KEY, urlUsername);
      setUsername(urlUsername);
    } else {
      const cachedUsername = sessionStorage.getItem(SETUP_USERNAME_STORAGE_KEY);
      if (cachedUsername) {
        setUsername(cachedUsername);
      }
    }

    // Immediately strip the sensitive token from the URL so it does not linger
    // in the browser history or server logs.
    if ((urlToken || urlUsername) && !hasSanitizedUrlRef.current) {
      hasSanitizedUrlRef.current = true;
      router.replace("/password-setup");
    }
  }, [router, searchParams]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!token || !username.trim()) {
      setError("Your password setup session expired. Please sign in with Google again.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (!allRulesPassed) {
      setError("Please satisfy all password requirements before continuing.");
      return;
    }

    setIsSubmitting(true);
    try {
      const apiBaseUrl = getApiBaseUrl();
      const response = await fetch(`${apiBaseUrl}/auth/password/setup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          username: username.trim(),
          token,
          new_password: password,
          confirm_password: confirmPassword,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(parseApiError(payload));
      }
      sessionStorage.removeItem(SETUP_TOKEN_STORAGE_KEY);
      sessionStorage.removeItem(SETUP_USERNAME_STORAGE_KEY);
      saveAuthToken("authenticated");
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4">
      <div className="w-full max-w-md rounded-3xl border border-zinc-200 bg-white p-8 shadow-sm">
        <div className="mb-6">
          <Link
            href="/login"
            className="text-sm font-semibold text-indigo-600 hover:text-indigo-700"
          >
            ← Back to sign in
          </Link>
          <h1 className="mt-4 text-2xl font-bold text-zinc-900">
            Set your password
          </h1>
          <p className="mt-2 text-sm text-zinc-600">
            Google sign-in requires creating a password for future logins.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-700" htmlFor="username">
              Username
            </label>
            <input
              id="username"
              name="username"
              type="text"
              required
              value={username}
              readOnly
              className="input"
              placeholder="yourusername"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-700" htmlFor="password">
              New password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                setPasswordTouched(true);
              }}
              className="input"
              placeholder="At least 12 characters"
            />
            {passwordTouched && (
              <ul className="mt-2 space-y-1">
                {passwordRuleResults.map((r) => (
                  <li key={r.label} className={`flex items-center gap-2 text-xs ${r.passed ? "text-emerald-600" : "text-red-500"}`}>
                    {r.passed
                      ? <CheckCircle className="h-3.5 w-3.5 shrink-0" />
                      : <XCircle className="h-3.5 w-3.5 shrink-0" />}
                    {r.label}
                  </li>
                ))}
              </ul>
            )}
            {!passwordTouched && (
              <p className="mt-1 text-xs text-zinc-400">
                Must be 12+ characters with uppercase, lowercase, number, and special character.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-700" htmlFor="confirmPassword">
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
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting || !token || !username.trim()}
            className="btn-primary w-full disabled:cursor-not-allowed disabled:opacity-75 disabled:hover:scale-100"
          >
            {isSubmitting ? "Saving…" : "Set password"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function PasswordSetupPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4">
        <div className="w-full max-w-md rounded-3xl border border-zinc-200 bg-white p-8 shadow-sm">
          <h1 className="text-2xl font-bold text-zinc-900">Loading…</h1>
        </div>
      </div>
    }>
      <PasswordSetupContent />
    </Suspense>
  );
}
