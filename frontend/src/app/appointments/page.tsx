"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { createAppointment, fetchAppointments, AppointmentRecord } from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { PageShell } from "@/components/page-shell";

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
    <PageShell className="max-w-4xl" contentClassName="gap-8">
      <header className="space-y-2">
        <p className="text-sm uppercase tracking-[0.3em] text-zinc-500">Appointments</p>
        <h1 className="text-3xl font-semibold text-zinc-950">Schedule time with the teaching team</h1>
        <p className="text-zinc-600">
          Requests are logged for the professor and TAs. You’ll receive confirmation via email once someone accepts.
        </p>
      </header>

      <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
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

          {formState.error && <p className="text-sm text-red-600">{formState.error}</p>}
          {formState.success && <p className="text-sm text-emerald-600">Request submitted—we’ll be in touch.</p>}

          <button
            type="submit"
            disabled={formState.loading}
            className="rounded-full bg-zinc-900 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {formState.loading ? "Submitting…" : "Submit request"}
          </button>
        </form>
      </section>

      <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
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
          {loading && <p className="text-sm text-zinc-500">Loading appointments…</p>}
          {!loading && appointments.length === 0 && <p className="text-sm text-zinc-500">No appointment requests yet.</p>}
          {appointments.map((appt) => (
            <div key={appt.id} className="rounded-xl border border-zinc-100 bg-zinc-50 p-4 text-sm text-zinc-700">
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
        </div>
      </section>
    </PageShell>
  );
}
