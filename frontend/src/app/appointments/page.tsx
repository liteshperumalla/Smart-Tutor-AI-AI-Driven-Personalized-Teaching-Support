"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { createAppointment, fetchAppointments, AppointmentRecord } from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { Calendar, User, Mail, Clock, MessageSquare, Send, CheckCircle, CalendarDays, Users, FileText } from "lucide-react";
import { PageHero } from "@/components/page-hero";
import { toast } from "sonner";

const REASONS = [
  "Discuss course material/concepts",
  "Questions about an assignment",
  "Project discussion/guidance",
  "Career advice/mentorship",
  "Other",
];

export default function AppointmentsPage() {
  const { token } = useAuthToken();
  const today = new Date().toISOString().split("T")[0];
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
      toast.success("Appointment requested");
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to submit request";
      setFormState({ loading: false, success: false, error: msg });
      toast.error(msg);
    }
  }

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'confirmed':
        return 'bg-success-bg text-success';
      case 'pending':
        return 'bg-warning-bg text-warning';
      case 'cancelled':
        return 'bg-danger-bg text-danger';
      default:
        return 'bg-surface-2 text-muted';
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 animate-fade-in-up">
      {/* Header */}
      <PageHero
        className="mb-8"
        icon={CalendarDays}
        title="Appointments"
        subtitle="Schedule meetings with professors and teaching assistants."
      />

      <div className="grid gap-8 lg:grid-cols-5">
        {/* Request Form */}
        <div className="lg:col-span-3">
          <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-primary-bg">
                <Calendar className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-foreground">Request an Appointment</h2>
                <p className="text-sm text-muted">Fill out the form below to schedule a meeting</p>
              </div>
            </div>

            <form className="space-y-5" onSubmit={handleSubmit}>
              {/* Personal Info Row */}
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    <User className="h-4 w-4 inline mr-1.5" />
                    Your Name
                  </label>
                  <input
                    name="name"
                    placeholder="Enter your name"
                    className="w-full px-4 py-3 rounded-xl border border-line bg-surface-2 text-foreground placeholder:text-muted focus:ring-2 focus:ring-primary focus:border-transparent transition outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    <Mail className="h-4 w-4 inline mr-1.5" />
                    Email Address
                  </label>
                  <input
                    type="email"
                    name="email"
                    placeholder="your@email.com"
                    className="w-full px-4 py-3 rounded-xl border border-line bg-surface-2 text-foreground placeholder:text-muted focus:ring-2 focus:ring-primary focus:border-transparent transition outline-none"
                    required
                  />
                </div>
              </div>

              {/* Appointment Details Row — Reason gets the wider column so
                  its longer options aren't cut off. */}
              <div className="grid gap-4 md:grid-cols-5">
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    <Users className="h-4 w-4 inline mr-1.5" />
                    Meet With
                  </label>
                  <select
                    name="appointment_with"
                    className="w-full px-4 py-3 rounded-xl border border-line bg-surface-2 text-foreground focus:ring-2 focus:ring-primary focus:border-transparent transition outline-none"
                  >
                    <option>Professor (Dr. Chen)</option>
                    <option>Teaching Assistant (TA)</option>
                  </select>
                </div>
                <div className="md:col-span-3">
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    <MessageSquare className="h-4 w-4 inline mr-1.5" />
                    Reason
                  </label>
                  <select
                    name="primary_reason"
                    className="w-full px-4 py-3 rounded-xl border border-line bg-surface-2 text-foreground focus:ring-2 focus:ring-primary focus:border-transparent transition outline-none"
                  >
                    {REASONS.map((reason) => (
                      <option key={reason}>{reason}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Date/Time Row */}
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    <CalendarDays className="h-4 w-4 inline mr-1.5" />
                    Preferred Date
                  </label>
                  <input
                    type="date"
                    name="preferred_date"
                    min={today}
                    className="w-full px-4 py-3 rounded-xl border border-line bg-surface-2 text-foreground focus:ring-2 focus:ring-primary focus:border-transparent transition outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">
                    <Clock className="h-4 w-4 inline mr-1.5" />
                    Preferred Time
                  </label>
                  <input
                    type="time"
                    name="preferred_time"
                    className="w-full px-4 py-3 rounded-xl border border-line bg-surface-2 text-foreground focus:ring-2 focus:ring-primary focus:border-transparent transition outline-none"
                    required
                  />
                </div>
              </div>

              {/* Additional Details */}
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">
                  <FileText className="h-4 w-4 inline mr-1.5" />
                  Additional Details (Optional)
                </label>
                <textarea
                  name="additional_details"
                  className="w-full px-4 py-3 rounded-xl border border-line bg-surface-2 text-foreground placeholder:text-muted focus:ring-2 focus:ring-primary focus:border-transparent transition outline-none resize-none"
                  rows={4}
                  placeholder="Share specific questions or context..."
                />
              </div>

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
                      <p className="text-sm font-medium text-success">Request submitted!</p>
                      <p className="text-sm text-success mt-1">We&apos;ll be in touch shortly to confirm your appointment.</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={formState.loading}
                className="w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl gradient-primary hover:brightness-110 text-white font-semibold focus-ring transition disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {formState.loading ? (
                  <>
                    <span className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
                    Submitting...
                  </>
                ) : (
                  <>
                    <Send className="h-5 w-5" />
                    Submit Request
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Appointment History */}
        <div className="lg:col-span-2">
          <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-lavender/15">
                  <Clock className="h-5 w-5 text-violet-700 dark:text-lavender" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-foreground">History</h2>
                  <p className="text-xs text-muted">Your recent appointments</p>
                </div>
              </div>
              <Link
                href="/feedback"
                className="text-xs font-medium text-primary hover:underline"
              >
                Need help?
              </Link>
            </div>

            <div className="space-y-3">
              {loading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="rounded-xl bg-surface-2 p-4 animate-pulse">
                      <div className="h-4 w-2/3 bg-line rounded mb-2"></div>
                      <div className="h-3 w-1/2 bg-line rounded"></div>
                    </div>
                  ))}
                </div>
              ) : appointments.length === 0 ? (
                <div className="rounded-xl border-2 border-dashed border-line bg-surface-2 p-8 text-center">
                  <div className="mx-auto h-12 w-12 rounded-full bg-surface-2 flex items-center justify-center mb-3">
                    <Calendar className="h-6 w-6 text-muted" />
                  </div>
                  <p className="text-sm font-medium text-foreground">No appointments yet</p>
                  <p className="text-xs text-muted mt-1">Submit the form to request a meeting</p>
                </div>
              ) : (
                appointments.map((appt) => (
                  <div
                    key={appt.id}
                    className="rounded-xl bg-surface-2 p-4 border border-line hover:border-line transition"
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <p className="font-semibold text-foreground text-sm">{appt.appointment_with}</p>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColor(appt.status)}`}>
                        {appt.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted">
                      <CalendarDays className="h-3.5 w-3.5" />
                      <span>{appt.preferred_date}</span>
                      <span>•</span>
                      <Clock className="h-3.5 w-3.5" />
                      <span>{appt.preferred_time}</span>
                    </div>
                    <p className="text-xs text-muted mt-2 line-clamp-1">{appt.primary_reason}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
