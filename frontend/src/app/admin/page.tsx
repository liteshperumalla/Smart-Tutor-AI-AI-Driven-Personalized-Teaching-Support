"use client";

import { useEffect, useState } from "react";
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

  const cards = [
    {
      label: "Total Users",
      value: stats?.total_users ?? 0,
      icon: Users,
      color: "text-blue-600 dark:text-blue-400",
      bg: "bg-blue-50 dark:bg-blue-950/30",
      border: "border-blue-200 dark:border-blue-900",
    },
    {
      label: "Total Queries",
      value: stats?.total_queries ?? 0,
      icon: Activity,
      color: "text-emerald-600 dark:text-emerald-400",
      bg: "bg-emerald-50 dark:bg-emerald-950/30",
      border: "border-emerald-200 dark:border-emerald-900",
    },
    {
      label: "Pending Feedback",
      value: stats?.new_feedback ?? 0,
      icon: MessageSquare,
      color: "text-amber-600 dark:text-amber-400",
      bg: "bg-amber-50 dark:bg-amber-950/30",
      border: "border-amber-200 dark:border-amber-900",
    },
    {
      label: "Message Likes",
      value: stats?.total_message_likes ?? 0,
      icon: ThumbsUp,
      color: "text-green-600 dark:text-green-400",
      bg: "bg-green-50 dark:bg-green-950/30",
      border: "border-green-200 dark:border-green-900",
    },
    {
      label: "Message Dislikes",
      value: stats?.total_message_dislikes ?? 0,
      icon: ThumbsDown,
      color: "text-red-600 dark:text-red-400",
      bg: "bg-red-50 dark:bg-red-950/30",
      border: "border-red-200 dark:border-red-900",
    },
    {
      label: "Message Reports",
      value: stats?.total_message_reports ?? 0,
      icon: Flag,
      color: "text-amber-600 dark:text-amber-400",
      bg: "bg-amber-50 dark:bg-amber-950/30",
      border: "border-amber-200 dark:border-amber-900",
    },
    {
      label: "Share Activity",
      value: stats?.total_chat_shares ?? 0,
      icon: Share2,
      color: "text-indigo-600 dark:text-indigo-400",
      bg: "bg-indigo-50 dark:bg-indigo-950/30",
      border: "border-indigo-200 dark:border-indigo-900",
    },
    {
      label: "Active Announcements",
      value: stats?.active_announcements ?? 0,
      icon: Megaphone,
      color: "text-purple-600 dark:text-purple-400",
      bg: "bg-purple-50 dark:bg-purple-950/30",
      border: "border-purple-200 dark:border-purple-900",
    },
    {
      label: "Admin Users",
      value: stats?.admin_users ?? 0,
      icon: ShieldAlert,
      color: "text-zinc-600 dark:text-zinc-400",
      bg: "bg-zinc-50 dark:bg-zinc-800/50",
      border: "border-zinc-200 dark:border-zinc-700",
    },
    {
      label: "Total Feedback",
      value: stats?.total_feedback ?? 0,
      icon: TrendingUp,
      color: "text-rose-600 dark:text-rose-400",
      bg: "bg-rose-50 dark:bg-rose-950/30",
      border: "border-rose-200 dark:border-rose-900",
    },
    {
      label: "Pending Appointments",
      value: stats?.pending_appointments ?? 0,
      icon: CalendarDays,
      color: "text-cyan-600 dark:text-cyan-400",
      bg: "bg-cyan-50 dark:bg-cyan-950/30",
      border: "border-cyan-200 dark:border-cyan-900",
    },
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

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.label}
              className={`flex items-center gap-4 rounded-2xl border p-5 ${card.bg} ${card.border}`}
            >
              <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${card.bg}`}>
                <Icon className={`h-6 w-6 ${card.color}`} />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-white">
                  {card.value.toLocaleString()}
                </p>
                <p className="text-sm text-zinc-500 dark:text-zinc-400">{card.label}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
