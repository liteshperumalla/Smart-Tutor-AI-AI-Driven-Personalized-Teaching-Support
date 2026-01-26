"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { postJSON } from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { PageShell } from "@/components/page-shell";
import { MessageSquare, Bug, User, Mail, Tag, FileText, Send } from "lucide-react";

type FeedbackPayload = {
  name?: string;
  email?: string;
  category: string;
  message: string;
};

type BugPayload = {
  name?: string;
  email?: string;
  feature: string;
  severity: string;
  description: string;
  steps?: string;
};

export default function FeedbackPage() {
  const router = useRouter();
  const { token } = useAuthToken();
  const [feedbackState, setFeedbackState] = useState<{
    loading: boolean;
    error: string | null;
    success: boolean;
  }>({ loading: false, error: null, success: false });
  const [bugState, setBugState] = useState({
    loading: false,
    error: null as string | null,
    success: false,
  });

  async function submitToApi(path: string, payload: unknown) {
    if (!token) {
      router.push("/login");
      return;
    }
    await postJSON<{ success: boolean }>({ path, body: payload, token });
  }

  async function handleFeedbackSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const payload: FeedbackPayload = {
      name: formData.get("name")?.toString(),
      email: formData.get("email")?.toString(),
      category: formData.get("category")?.toString() || "general",
      message: formData.get("message")?.toString() || "",
    };
    setFeedbackState({ loading: true, error: null, success: false });
    try {
      await submitToApi("/feedback", payload);
      setFeedbackState({ loading: false, error: null, success: true });
      event.currentTarget.reset();
    } catch (error) {
      setFeedbackState({
        loading: false,
        error: error instanceof Error ? error.message : "Failed to submit feedback",
        success: false,
      });
    }
  }

  async function handleBugSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const payload: BugPayload = {
      name: formData.get("bug-name")?.toString(),
      email: formData.get("bug-email")?.toString(),
      feature: formData.get("feature")?.toString() || "",
      severity: formData.get("severity")?.toString() || "low",
      description: formData.get("description")?.toString() || "",
      steps: formData.get("steps")?.toString(),
    };
    setBugState({ loading: true, error: null, success: false });
    try {
      await submitToApi("/feedback/bug", payload);
      setBugState({ loading: false, error: null, success: true });
      event.currentTarget.reset();
    } catch (error) {
      setBugState({
        loading: false,
        error: error instanceof Error ? error.message : "Failed to submit bug report",
        success: false,
      });
    }
  }

  return (
    <PageShell className="max-w-5xl" contentClassName="gap-8" noCard>
      <section className="grid gap-6 md:grid-cols-2">
        <article className="rounded-2xl-zinc-200 bg-white p-6 shadow-sm">
          <h2 className="text-xl font-medium text-zinc-900">Give general feedback</h2>
          <p className="mt-1 text-sm text-zinc-600">Share usability notes, feature wishes, or content ideas.</p>
          <form className="mt-4 space-y-4" onSubmit={handleFeedbackSubmit}>
            <input type="text" name="name" placeholder="Name (optional)" className="input" />
            <input type="email" name="email" placeholder="Email (optional)" className="input" />
            <select name="category" className="input">
              <option value="general">General usability</option>
              <option value="feature">Feature request</option>
              <option value="content">Content quality</option>
              <option value="performance">Performance</option>
              <option value="other">Other</option>
            </select>
            <textarea
              name="message"
              placeholder="Your detailed feedback"
              className="input min-h-[160px]"
              required
            />
            {feedbackState.error && <p className="text-sm text-red-600">{feedbackState.error}</p>}
            {feedbackState.success && <p className="text-sm text-emerald-600">Thanks! We received your input.</p>}
            <button
              type="submit"
              disabled={feedbackState.loading}
              className="w-full btn-primary disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:scale-100"
            >
              {feedbackState.loading ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full-2-white-t-transparent"></span> Submitting…</>
              ) : (
                "Submit feedback"
              )}
            </button>
          </form>
        </article>

        <article className="rounded-2xl-zinc-200 bg-white p-6 shadow-sm">
          <h2 className="text-xl font-medium text-zinc-900">Report a bug</h2>
          <p className="mt-1 text-sm text-zinc-600">Describe the issue so we can reproduce it quickly.</p>
          <form className="mt-4 space-y-4" onSubmit={handleBugSubmit}>
            <input type="text" name="bug-name" placeholder="Name (optional)" className="input" />
            <input type="email" name="bug-email" placeholder="Email (optional)" className="input" />
            <input
              type="text"
              name="feature"
              placeholder="Page or feature affected"
              className="input"
              required
            />
            <select name="severity" className="input">
              <option value="low">Low · Minor inconvenience</option>
              <option value="medium">Medium · Affects functionality</option>
              <option value="high">High · Blocks feature</option>
              <option value="critical">Critical · System crash/data loss</option>
            </select>
            <textarea
              name="description"
              placeholder="Detailed description"
              className="input min-h-[160px]"
              required
            />
            <textarea
              name="steps"
              placeholder="Steps to reproduce (optional)"
              className="input min-h-[120px]"
            />
            {bugState.error && <p className="text-sm text-red-600">{bugState.error}</p>}
            {bugState.success && <p className="text-sm text-emerald-600">Thanks! We logged this bug.</p>}
            <button
              type="submit"
              disabled={bugState.loading}
              className="w-full btn-primary disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:scale-100"
            >
              {bugState.loading ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full-2-white-t-transparent"></span> Submitting…</>
              ) : (
                "Submit bug report"
              )}
            </button>
          </form>
        </article>
      </section>

      <section className="rounded-2xl-dashed-zinc-200 bg-zinc-50 p-6 text-sm text-zinc-600">
        <p>
          Feedback entries are written to the server’s log folder (`logs/feedback_log.txt` and `logs/bug_reports_log.txt`
          in development). In production we’ll forward these to CloudWatch or another logging system.
        </p>
        <p className="mt-2">
          Looking for other support options? Visit{" "}
          <Link href="/" className="font-semibold text-blue-600">
            the home hub
          </Link>{" "}
          for the latest updates.
        </p>
      </section>
    </PageShell>
  );
}
