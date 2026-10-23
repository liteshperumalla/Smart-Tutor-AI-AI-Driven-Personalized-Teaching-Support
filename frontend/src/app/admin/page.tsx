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
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-white" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-center text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-400">
        Failed to load admin stats: {error}
      </div>
    );
  }

  // Items someone has to act on. They turn amber only while non-zero, so a
  // quiet day reads as quiet instead of a wall of coloured tiles.
  const attention = [
    { label: "Pending feedback", value: stats?.new_feedback ?? 0, icon: MessageSquare, href: "/admin/feedback" },
    { label: "Pending appointments", value: stats?.pending_appointments ?? 0, icon: CalendarDays, href: "/admin/appointments" },
    { label: "Reported messages", value: stats?.total_message_reports ?? 0, icon: Flag, href: "/admin/feedback" },
  ];

  const usage = [
    { label: "Users", value: stats?.total_users ?? 0, icon: Users },
    { label: "Tutor queries", value: stats?.total_queries ?? 0, icon: Activity },
    { label: "Helpful votes", value: stats?.total_message_likes ?? 0, icon: ThumbsUp },
    { label: "Unhelpful votes", value: stats?.total_message_dislikes ?? 0, icon: ThumbsDown },
    { label: "Shared chats", value: stats?.total_chat_shares ?? 0, icon: Share2 },
    { label: "Feedback received", value: stats?.total_feedback ?? 0, icon: TrendingUp },
    { label: "Announcements", value: stats?.active_announcements ?? 0, icon: Megaphone },
    { label: "Admins", value: stats?.admin_users ?? 0, icon: ShieldAlert },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-zinc-900 dark:text-white">
        Dashboard Overview
      </h2>

      {stats && !stats.storage_readiness.ready && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 dark:border-amber-900 dark:bg-amber-950/30">
          <div className="flex items-start gap-3">
            <HardDrive className="mt-0.5 h-5 w-5 text-amber-600 dark:text-amber-400" />
            <div>
              <p className="text-sm font-semibold text-amber-800 dark:text-amber-300">
                Shared storage is not confirmed for production
              </p>
              <p className="mt-1 text-sm text-amber-700 dark:text-amber-400">
                {stats.storage_readiness.warning || "Appointments and feedback are stored under USER_DATA_ROOT."}
              </p>
              <p className="mt-2 text-xs text-amber-700/80 dark:text-amber-400/80">
                Path: {stats.storage_readiness.user_data_root || "Unavailable"} · Shared flag: {stats.storage_readiness.shared_storage_configured ? "enabled" : "disabled"}
              </p>
            </div>
          </div>
        </div>
      )}

      <section aria-labelledby="admin-attention">
        <h3 id="admin-attention" className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500 dark:text-zinc-400">
          Needs attention
        </h3>
        <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {attention.map(({ label, value, icon: Icon, href }) => {
            const pending = value > 0;
            return (
              <Link
                key={label}
                href={href}
                className={[
                  "group flex items-center gap-4 rounded-2xl border p-5 transition hover:-translate-y-0.5 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500",
                  pending
                    ? "border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30"
                    : "border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900",
                ].join(" ")}
              >
                <span
                  className={[
                    "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl",
                    pending
                      ? "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400"
                      : "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400",
                  ].join(" ")}
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-2xl font-bold tabular-nums text-zinc-900 dark:text-white">{value.toLocaleString()}</span>
                  <span className="block text-sm text-zinc-600 dark:text-zinc-400">{label}</span>
                  <span className={`mt-0.5 block text-xs ${pending ? "font-medium text-amber-700 dark:text-amber-400" : "text-zinc-400 dark:text-zinc-500"}`}>
                    {pending ? "Review now" : "All clear"}
                  </span>
                </span>
                <ChevronRight className="h-4 w-4 shrink-0 text-zinc-400 transition group-hover:translate-x-0.5" aria-hidden="true" />
              </Link>
            );
          })}
        </div>
      </section>

      <section aria-labelledby="admin-usage">
        <h3 id="admin-usage" className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500 dark:text-zinc-400">
          Usage
        </h3>
        <div className="mt-3 grid grid-cols-2 gap-4 xl:grid-cols-4">
          {usage.map(({ label, value, icon: Icon }) => (
            <div
              key={label}
              className="flex items-center gap-3 rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <span className="min-w-0">
                <span className="block text-xl font-bold tabular-nums text-zinc-900 dark:text-white">{value.toLocaleString()}</span>
                <span className="block truncate text-sm text-zinc-500 dark:text-zinc-400">{label}</span>
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
