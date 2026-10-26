"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { fetchCourses, postJSON, type Course } from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { MessageSquare, Bug, User, Mail, Tag, FileText, Send, CheckCircle, AlertTriangle, Sparkles, ThumbsUp, Zap, ShieldAlert } from "lucide-react";
import { PageHero } from "@/components/page-hero";
import { useUser } from "@/hooks/useUser";
import { toast } from "sonner";

type FeedbackType = 'feedback' | 'bug';

type UnifiedPayload = {
  type: FeedbackType;
  name?: string;
  email?: string;
  category?: string;
  message?: string;
  feature?: string;
  severity?: string;
  description?: string;
  steps?: string;
};

export default function FeedbackPage() {
  const router = useRouter();
  const { token } = useAuthToken();
  const { isAdmin } = useUser();
  const [feedbackType, setFeedbackType] = useState<FeedbackType>('feedback');
  const [courses, setCourses] = useState<Course[]>([]);
  const [courseId, setCourseId] = useState("");
  const [formState, setFormState] = useState<{
    loading: boolean;
    error: string | null;
    success: boolean;
  }>({ loading: false, error: null, success: false });

  useEffect(() => {
    if (!token) return;
    fetchCourses(token).then((items) => {
      setCourses(items);
      setCourseId(items[0]?.id ?? "");
    }).catch(() => {});
  }, [token]);

  async function submitToApi(path: string, payload: unknown) {
    if (!token) {
      router.push("/login");
      throw new Error("Please sign in to submit feedback.");
    }
    await postJSON<{ success: boolean }>({ path, body: payload, token });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);

    setFormState({ loading: true, error: null, success: false });

    try {
      if (feedbackType === 'feedback') {
        const payload = {
          name: formData.get("name")?.toString(),
          email: formData.get("email")?.toString(),
          category: formData.get("category")?.toString() || "general",
          message: formData.get("message")?.toString() || "",
          course_id: courseId || undefined,
        };
        await submitToApi("/feedback", payload);
      } else {
        const payload = {
          name: formData.get("name")?.toString(),
          email: formData.get("email")?.toString(),
          feature: formData.get("feature")?.toString() || "",
          severity: formData.get("severity")?.toString() || "low",
          description: formData.get("description")?.toString() || "",
          steps: formData.get("steps")?.toString(),
          course_id: courseId || undefined,
        };
        await submitToApi("/feedback/bug", payload);
      }

      setFormState({ loading: false, error: null, success: true });
      event.currentTarget.reset();
      toast.success("Feedback submitted, thank you!");
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to submit";
      setFormState({ loading: false, error: msg, success: false });
      toast.error(msg);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 animate-fade-in-up">
      {/* Header */}
      <PageHero
        className="mb-8"
        icon={MessageSquare}
        title="Feedback &"
        accent="Support"
        subtitle="Help us improve by sharing your thoughts or reporting issues."
      />

      {/* Admin Notice */}
      {isAdmin && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border border-warning/40 bg-warning-bg px-4 py-3">
          <ShieldAlert className="h-5 w-5 text-warning flex-shrink-0" />
          <p className="text-sm text-warning">
            As an admin, you can review all feedback in the{" "}
            <Link href="/admin/feedback" className="font-semibold underline hover:text-warning">
              Admin Feedback Panel
            </Link>
          </p>
        </div>
      )}

      {/* Type Selector — the active option gets a ring and a solid surface
          so it stands out from the track in both themes. */}
      <div className="flex gap-3 mb-6 p-1.5 rounded-2xl bg-surface-2">
        <button
          type="button"
          onClick={() => {
            setFeedbackType('feedback');
            setFormState({ loading: false, error: null, success: false });
          }}
          aria-pressed={feedbackType === 'feedback'}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-medium transition ${
            feedbackType === 'feedback'
              ? 'bg-surface text-foreground shadow-sm ring-1 ring-line [&>svg]:text-success'
              : 'text-muted hover:text-foreground'
          }`}
        >
          <ThumbsUp className="h-5 w-5" />
          General Feedback
        </button>
        <button
          type="button"
          onClick={() => {
            setFeedbackType('bug');
            setFormState({ loading: false, error: null, success: false });
          }}
          aria-pressed={feedbackType === 'bug'}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-medium transition ${
            feedbackType === 'bug'
              ? 'bg-surface text-foreground shadow-sm ring-1 ring-line [&>svg]:text-danger'
              : 'text-muted hover:text-foreground'
          }`}
        >
          <Bug className="h-5 w-5" />
          Report a Bug
        </button>
      </div>

      {/* Unified Form Card */}
      <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
        {/* Form Header */}
        <div className="flex items-center gap-3 mb-6 pb-4 border-b border-line">
          <div className={`p-2.5 rounded-xl ${
            feedbackType === 'feedback'
              ? 'bg-primary-bg'
              : 'bg-danger-bg'
          }`}>
            {feedbackType === 'feedback'
              ? <Sparkles className="h-5 w-5 text-primary" />
              : <AlertTriangle className="h-5 w-5 text-danger" />
            }
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              {feedbackType === 'feedback' ? 'Share Your Feedback' : 'Report an Issue'}
            </h2>
            <p className="text-sm text-muted">
              {feedbackType === 'feedback'
                ? 'Share usability notes, feature wishes, or content ideas'
                : 'Describe the issue so we can fix it quickly'
              }
            </p>
          </div>
        </div>

        <form className="space-y-5" onSubmit={handleSubmit}>
          {courses.length > 0 && <label className="block text-sm font-medium text-foreground">Course context<select value={courseId} onChange={(event) => setCourseId(event.target.value)} className="mt-1.5 w-full rounded-xl border border-line bg-surface-2 px-4 py-3 text-foreground">{courses.map((course) => <option key={course.id} value={course.id}>{course.code} — {course.title}</option>)}</select></label>}
          {/* Personal Info - Always Shown */}
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1.5">
                <User className="h-4 w-4 inline mr-1.5" />
                Name (Optional)
              </label>
              <input
                type="text"
                name="name"
                placeholder="Your name"
                className="w-full px-4 py-3 rounded-xl border border-line bg-surface-2 text-foreground placeholder:text-muted focus:ring-2 focus:ring-primary focus:border-transparent transition outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1.5">
                <Mail className="h-4 w-4 inline mr-1.5" />
                Email (Optional)
              </label>
              <input
                type="email"
                name="email"
                placeholder="your@email.com"
                className="w-full px-4 py-3 rounded-xl border border-line bg-surface-2 text-foreground placeholder:text-muted focus:ring-2 focus:ring-primary focus:border-transparent transition outline-none"
              />
            </div>
          </div>

          {/* Feedback-specific fields */}
          {feedbackType === 'feedback' && (
            <>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">
                  <Tag className="h-4 w-4 inline mr-1.5" />
                  Category
                </label>
                <select
                  name="category"
                  className="w-full px-4 py-3 rounded-xl border border-line bg-surface-2 text-foreground focus:ring-2 focus:ring-primary focus:border-transparent transition outline-none"
                >
                  <option value="general">General usability</option>
                  <option value="feature">Feature request</option>
                  <option value="content">Content quality</option>
                  <option value="performance">Performance</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">
                  <FileText className="h-4 w-4 inline mr-1.5" />
                  Your Feedback
                </label>
                <textarea
                  name="message"
                  placeholder="Share your detailed feedback, suggestions, or ideas..."
                  className="w-full px-4 py-3 rounded-xl border border-line bg-surface-2 text-foreground placeholder:text-muted focus:ring-2 focus:ring-primary focus:border-transparent transition outline-none resize-none"
                  rows={5}
                  required
                />
              </div>
            </>
          )}

          {/* Bug-specific fields */}
          {feedbackType === 'bug' && (
            <>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    <Zap className="h-4 w-4 inline mr-1.5" />
                    Affected Feature
                  </label>
                  <input
                    type="text"
                    name="feature"
                    placeholder="e.g., Chat, Quiz, Login"
                    className="w-full px-4 py-3 rounded-xl border border-line bg-surface-2 text-foreground placeholder:text-muted focus:ring-2 focus:ring-primary focus:border-transparent transition outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    <AlertTriangle className="h-4 w-4 inline mr-1.5" />
                    Severity
                  </label>
                  <select
                    name="severity"
                    className="w-full px-4 py-3 rounded-xl border border-line bg-surface-2 text-foreground focus:ring-2 focus:ring-primary focus:border-transparent transition outline-none"
                  >
                    <option value="low">Low · Minor inconvenience</option>
                    <option value="medium">Medium · Affects functionality</option>
                    <option value="high">High · Blocks feature</option>
                    <option value="critical">Critical · System crash/data loss</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">
                  <FileText className="h-4 w-4 inline mr-1.5" />
                  Bug Description
                </label>
                <textarea
                  name="description"
                  placeholder="Describe what happened and what you expected..."
                  className="w-full px-4 py-3 rounded-xl border border-line bg-surface-2 text-foreground placeholder:text-muted focus:ring-2 focus:ring-primary focus:border-transparent transition outline-none resize-none"
                  rows={4}
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">
                  <MessageSquare className="h-4 w-4 inline mr-1.5" />
                  Steps to Reproduce (Optional)
                </label>
                <textarea
                  name="steps"
                  placeholder="1. Go to...&#10;2. Click on...&#10;3. See error..."
                  className="w-full px-4 py-3 rounded-xl border border-line bg-surface-2 text-foreground placeholder:text-muted focus:ring-2 focus:ring-primary focus:border-transparent transition outline-none resize-none"
                  rows={3}
                />
              </div>
            </>
          )}

          {/* Status Messages */}
          {formState.error && (
            <div className="rounded-xl bg-danger-bg border border-danger/30 p-4">
              <div className="flex items-start gap-3">
                <svg className="h-5 w-5 text-danger flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div>
                  <p className="text-sm font-medium text-danger">Submission failed</p>
                  <p className="text-sm text-danger mt-1">{formState.error}</p>
                </div>
              </div>
            </div>
          )}

          {formState.success && (
            <div className="rounded-xl bg-success-bg border border-success/30 p-4">
              <div className="flex items-start gap-3">
                <CheckCircle className="h-5 w-5 text-success flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-success">
                    {feedbackType === 'feedback' ? 'Thanks for your feedback!' : 'Bug report submitted!'}
                  </p>
                  <p className="text-sm text-success mt-1">
                    {feedbackType === 'feedback'
                      ? 'We appreciate you taking the time to help us improve.'
                      : 'Our team will look into this issue shortly.'
                    }
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={formState.loading}
            className={`w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-semibold transition disabled:opacity-60 disabled:cursor-not-allowed ${
              feedbackType === 'feedback'
                ? 'gradient-primary text-white hover:brightness-110'
                : 'bg-danger-solid text-white hover:brightness-110'
            }`}
          >
            {formState.loading ? (
              <>
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
                Submitting...
              </>
            ) : (
              <>
                <Send className="h-5 w-5" />
                {feedbackType === 'feedback' ? 'Submit Feedback' : 'Submit Bug Report'}
              </>
            )}
          </button>
        </form>
      </div>

      {/* Help Link */}
      <div className="mt-6 text-center">
        <p className="text-sm text-muted">
          Need direct assistance?{" "}
          <Link href="/" className="font-medium text-primary hover:underline">
            Visit the home hub
          </Link>{" "}
          or contact{" "}
          <a href="mailto:support@smartaitutor.com" className="font-medium text-primary hover:underline">
            support@smartaitutor.com
          </a>
        </p>
      </div>
    </div>
  );
}
