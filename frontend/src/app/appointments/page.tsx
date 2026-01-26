"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { createAppointment, fetchAppointments, AppointmentRecord } from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { PageShell } from "@/components/page-shell";
import { Calendar, User, Mail, Clock, MessageSquare, Send, CheckCircle } from "lucide-react";

const REASONS = [
  "Discuss course material/concepts",
  "Questions about an assignment",
  "Project discussion/guidance",
  "Career advice/mentorship",
  "Other",
];

export default function AppointmentsPage() {
  const { token } = useAuthToken();
  const [appointments, setAppointments] = useState<AppointmentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [formState, setFormState] = useState<{ loading: boolean; error: string | null; success: boolean }>({
    loading: false,
    error: null,
    success: false,
  });

  useEffect(() => {
    if (!token) return;
    fetchAppointments(token)
      .then((data) => setAppointments(data.appointments || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    const formData = new FormData(event.currentTarget);
    const payload = {
      name: formData.get("name")?.toString() || "",
      email: formData.get("email")?.toString() || "",
      appointment_with: formData.get("appointment_with")?.toString() || "Professor (Dr. Chen)",
      preferred_date: formData.get("preferred_date")?.toString() || "",
      preferred_time: formData.get("preferred_time")?.toString() || "",
      primary_reason: formData.get("primary_reason")?.toString() || "",
      additional_details: formData.get("additional_details")?.toString() || "",
    };
    setFormState({ loading: true, error: null, success: false });
    try {
      const response = await createAppointment({ token, payload });
      setAppointments((prev) => [response.appointment, ...prev]);
      setFormState({ loading: false, error: null, success: true });
      event.currentTarget.reset();
    } catch (error) {
      setFormState({
        loading: false,
        success: false,
        error: error instanceof Error ? error.message : "Failed to submit request",
      });
    }
  }

  return (
    <PageShell className="max-w-4xl" contentClassName="gap-8" noCard>
      <header className="relative overflow-hidden rounded-full p-12 animate-fade-in-down">
        <div className="relative z-10">
          <h1 className="font-display text-5xl font-bold text-zinc-900 dark:text-white">
            Schedule time with the teaching team
          </h1>
          <p className="mt-4 text-lg text-zinc-600 max-w-2xl dark:text-zinc-400">
            Requests are logged for the professor and TAs. You'll receive confirmation via email once someone accepts
          </p>
        </div>
      </header>

      <section className="rounded-2xl-zinc-200 bg-white p-6 shadow-sm">
        <h2 className="text-xl font-medium text-zinc-900">Request an appointment</h2>
        
        <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
          <div className="grid gap-4 md:grid-cols-2">
            <input name="name" placeholder="Your name" className="input" required />
            <input type="email" name="email" placeholder="Your email" className="input" required />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <select name="appointment_with" className="input">
              <option>Professor (Dr. Chen)</option>
              <option>Teaching Assistant (TA)</option>
            </select>
            <select name="primary_reason" className="input">
              {REASONS.map((reason) => (
                <option key={reason}>{reason}</option>
              ))}
            </select>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <input type="date" name="preferred_date" className="input" required />
            <input type="time" name="preferred_time" className="input" required />
          </div>

          <textarea
            name="additional_details"
            className="input min-h-[160px]"
            placeholder="Share specific questions or context (optional)"
          />

          {formState.error && (
            <div className="rounded-full-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/30">
              <div className="flex items-start gap-3">
                <svg className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div>
                  <p className="text-sm font-medium text-red-700 dark:text-red-400">Submission failed</p>
                  <p className="text-sm text-red-600 dark:text-red-400/80 mt-1">{formState.error}</p>
                </div>
              </div>
            </div>
          )}
          {formState.success && (
            <div className="rounded-full-emerald-200 bg-emerald-50 p-4 dark:border-emerald-800 dark:bg-emerald-900/30">
              <div className="flex items-start gap-3">
                <svg className="h-5 w-5 text-emerald-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div>
                  <p className="text-sm font-medium text-emerald-700 dark:text-emerald-400">Request submitted!</p>
                  <p className="text-sm text-emerald-600 dark:text-emerald-400/80 mt-1">We'll be in touch shortly to confirm your appointment.</p>
                </div>
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={formState.loading}
            className="btn-primary disabled:cursor-not-allowed disabled:opacity-60"
          >
            {formState.loading ? (
              <><span className="inline-block h-4 w-4 animate-spin rounded-full-2-white-t-transparent"></span> Submitting…</>
            ) : (
              <>Submit request <span className="transition-transform group-hover:translate-x-1">→</span></>
            )}
          </button>
        </form>
      </section>

      <section className="rounded-full-zinc-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-medium text-zinc-900">Your appointment history</h2>
            <p className="text-sm text-zinc-500">Most recent requests appear first.</p>
          </div>
          <Link href="/feedback" className="text-sm font-semibold text-blue-600">
            Need other help?
          </Link>
        </div>

        <div className="mt-4 space-y-3">
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="rounded-xl-zinc-100 bg-zinc-50 p-4 animate-pulse">
                  <div className="h-4 w-1/3 bg-zinc-200 dark:bg-zinc-700 rounded mb-2"></div>
                  <div className="h-3 w-1/2 bg-zinc-200 dark:bg-zinc-700 rounded"></div>
                </div>
              ))}
            </div>
          ) : appointments.length === 0 ? (
            <div className="rounded-xl-2-dashed-zinc-200 bg-zinc-50 p-8 text-center dark:border-zinc-700 dark:bg-zinc-800/50">
              <div className="mx-auto h-12 w-12 rounded-full bg-zinc-100 dark:bg-zinc-700 flex items-center justify-center mb-3">
                <svg className="h-6 w-6 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">No appointment requests yet</p>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Submit the form to request a meeting with the professor or TA.</p>
            </div>
          ) : (
            <>
              {appointments.map((appt) => (
                <div key={appt.id} className="rounded-xl-zinc-100 bg-zinc-50 p-4 text-sm text-zinc-700">
                  <p className="font-semibold text-zinc-900">{appt.appointment_with}</p>
                  <p className="text-xs text-zinc-500">
                    {appt.preferred_date} at {appt.preferred_time} · {appt.primary_reason}
                  </p>
                  {appt.additional_details && <p className="mt-2 text-xs text-zinc-500">{appt.additional_details}</p>}
                  <p className="mt-2 text-xs text-zinc-500">
                    Status: <span className="font-medium text-zinc-900 uppercase">{appt.status}</span>
                  </p>
                </div>
              ))}
            </>
          )}
        </div>
      </section>
    </PageShell>
  );
}
