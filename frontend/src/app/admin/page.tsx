"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuthToken } from "@/hooks/useAuthToken";
import { fetchAdminStats, AdminStats } from "@/lib/api";
import {
  Users,
  MessageSquare,
  Activity,
  Megaphone,
  CalendarDays,
  HardDrive,
  ShieldAlert,
  TrendingUp,
  ThumbsUp,
  ThumbsDown,
  Flag,
  Share2,
  ChevronRight,
} from "lucide-react";

export default function AdminDashboard() {
  const { token } = useAuthToken({ redirectTo: "/login" });
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    fetchAdminStats(token)
      .then((data) => {
        setStats(data);
        setError(data.error ?? null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-danger/30 bg-danger-bg p-6 text-center text-danger">
        Failed to load admin stats: {error}
      </div>
    );
  }

  // Items someone has to act on. They turn amber only while non-zero, so a
  // quiet day reads as quiet instead of a wall of coloured tiles. Reported
  // messages is a running total (reviewing a report doesn't lower it), so it
  // sits under Usage.
  const attention = [
    { label: "Pending feedback", value: stats?.new_feedback ?? 0, icon: MessageSquare, href: "/admin/feedback" },
    { label: "Pending appointments", value: stats?.pending_appointments ?? 0, icon: CalendarDays, href: "/admin/appointments" },
  ];

  const usage = [
    { label: "Users", value: stats?.total_users ?? 0, icon: Users },
    { label: "Tutor queries", value: stats?.total_queries ?? 0, icon: Activity },
    { label: "Helpful votes", value: stats?.total_message_likes ?? 0, icon: ThumbsUp },
    { label: "Unhelpful votes", value: stats?.total_message_dislikes ?? 0, icon: ThumbsDown },
    { label: "Shared chats", value: stats?.total_chat_shares ?? 0, icon: Share2 },
    { label: "Feedback received", value: stats?.total_feedback ?? 0, icon: TrendingUp },
    { label: "Reported messages", value: stats?.total_message_reports ?? 0, icon: Flag },
    { label: "Announcements", value: stats?.active_announcements ?? 0, icon: Megaphone },
    { label: "Admins", value: stats?.admin_users ?? 0, icon: ShieldAlert },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-foreground">
        Dashboard Overview
      </h2>

      {stats && !stats.storage_readiness.ready && (
        <div className="rounded-2xl border border-warning/40 bg-warning-bg p-5">
          <div className="flex items-start gap-3">
            <HardDrive className="mt-0.5 h-5 w-5 text-warning" />
            <div>
              <p className="text-sm font-semibold text-warning">
                Shared storage is not confirmed for production
              </p>
              <p className="mt-1 text-sm text-warning">
                {stats.storage_readiness.warning || "Appointments and feedback are stored under USER_DATA_ROOT."}
              </p>
              <p className="mt-2 text-xs text-warning/80">
                Path: {stats.storage_readiness.user_data_root || "Unavailable"} · Shared flag: {stats.storage_readiness.shared_storage_configured ? "enabled" : "disabled"}
              </p>
            </div>
          </div>
        </div>
      )}

      <section aria-labelledby="admin-attention">
        <h3 id="admin-attention" className="micro-label">
          Needs attention
        </h3>
        <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {attention.map(({ label, value, icon: Icon, href }) => {
            const pending = value > 0;
            return (
              <Link
                key={label}
                href={href}
                className={[
                  // Admin stat cards: neutral surface + a 3px left accent by meaning
                  // (attention → warning) instead of tinted card backgrounds.
                  "group flex items-center gap-4 rounded-[14px] border border-l-[3px] border-line bg-surface p-5 transition hover:-translate-y-0.5 hover:shadow-md focus-ring",
                  pending ? "border-l-warning" : "border-l-line",
                ].join(" ")}
              >
                <span
                  className={[
                    "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl",
                    pending
                      ? "bg-warning-bg text-warning"
                      : "bg-surface-2 text-muted",
                  ].join(" ")}
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-display text-2xl font-bold tabular-nums text-foreground">{value.toLocaleString()}</span>
                  <span className="block text-sm text-muted">{label}</span>
                  <span className={`mt-0.5 block text-xs ${pending ? "font-medium text-warning" : "text-muted"}`}>
                    {pending ? "Review now" : "All clear"}
                  </span>
                </span>
                <ChevronRight className="h-4 w-4 shrink-0 text-muted transition group-hover:translate-x-0.5" aria-hidden="true" />
              </Link>
            );
          })}
        </div>
      </section>

      <section aria-labelledby="admin-usage">
        <h3 id="admin-usage" className="micro-label">
          Usage
        </h3>
        <div className="mt-3 grid grid-cols-2 gap-4 lg:grid-cols-3">
          {usage.map(({ label, value, icon: Icon }) => (
            <div
              key={label}
              className="flex items-center gap-3 rounded-[14px] border border-l-[3px] border-line border-l-secondary bg-surface p-4"
            >
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-success-bg text-success">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <span className="min-w-0">
                <span className="block font-display text-xl font-bold tabular-nums text-foreground">{value.toLocaleString()}</span>
                <span className="block truncate text-sm text-muted">{label}</span>
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
