"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuthToken } from "@/hooks/useAuthToken";
import {
  fetchAllFeedback,
  updateFeedbackStatus,
  AdminFeedbackEntry,
} from "@/lib/api";
import { MessageSquare, Bug, Filter, ChevronDown, ChevronUp } from "lucide-react";

type TabFilter = "all" | "feedback" | "bug";

const statusColors: Record<string, string> = {
  new: "bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400",
  reviewed: "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400",
  resolved: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400",
};

export default function AdminFeedbackPage() {
  const { token } = useAuthToken({ redirectTo: "/login" });
  const [entries, setEntries] = useState<AdminFeedbackEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabFilter>("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const feedbackType = tab === "all" ? undefined : tab;
      const data = await fetchAllFeedback(token, feedbackType, 500);
      setEntries(data.feedback);
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [token, tab]);

  useEffect(() => {
    load();
  }, [load]);

  const handleStatusChange = async (id: string, newStatus: string) => {
    if (!token) return;
    setActionLoading(id);
    try {
      await updateFeedbackStatus(token, id, newStatus);
      setEntries((prev) =>
        prev.map((e) =>
          e.id === id ? { ...e, status: newStatus as AdminFeedbackEntry["status"] } : e
        )
      );
    } catch {
      // silently fail
    } finally {
      setActionLoading(null);
    }
  };

  const tabs: { key: TabFilter; label: string; icon: typeof MessageSquare }[] = [
    { key: "all", label: "All", icon: Filter },
    { key: "feedback", label: "Feedback", icon: MessageSquare },
    { key: "bug", label: "Bug Reports", icon: Bug },
  ];

  return (
    <div className="space-y-6">
      <h2 className="flex items-center gap-2 text-lg font-semibold text-zinc-900 dark:text-white">
        <MessageSquare className="h-5 w-5" />
        Feedback & Bug Reports
        <span className="ml-2 rounded-full bg-zinc-200 px-2.5 py-0.5 text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
          {entries.length}
        </span>
      </h2>

      {/* Tab Filters */}
      <div className="flex gap-2">
        {tabs.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={[
                "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition",
                tab === t.key
                  ? "bg-zinc-900 text-white dark:bg-white dark:text-zinc-900"
                  : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700",
              ].join(" ")}
            >
              <Icon className="h-4 w-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-white" />
        </div>
      ) : entries.length === 0 ? (
        <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-8 text-center text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/30 dark:text-zinc-400">
          No feedback entries found.
        </div>
      ) : (
        <div className="space-y-3">
          {entries.map((entry) => {
            const isExpanded = expanded === entry.id;
            const isFeedback = entry.type === "feedback";

            return (
              <div
                key={entry.id}
                className="rounded-2xl border border-zinc-200 bg-white transition dark:border-zinc-800 dark:bg-zinc-900/60"
              >
                {/* Header row */}
                <button
                  onClick={() => setExpanded(isExpanded ? null : entry.id)}
                  className="flex w-full items-center gap-3 px-5 py-4 text-left"
                >
                  {isFeedback ? (
                    <MessageSquare className="h-4 w-4 flex-shrink-0 text-blue-500" />
                  ) : (
                    <Bug className="h-4 w-4 flex-shrink-0 text-red-500" />
                  )}

                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-zinc-900 dark:text-white">
                      {isFeedback
                        ? entry.message?.slice(0, 80) || "No message"
                        : entry.description?.slice(0, 80) || "No description"}
                      {((isFeedback ? entry.message : entry.description) || "").length > 80
                        ? "…"
                        : ""}
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      by {entry.username} · {entry.created_at ? new Date(entry.created_at).toLocaleDateString() : "—"}
                      {isFeedback && entry.category && ` · ${entry.category}`}
                      {!isFeedback && entry.severity && ` · ${entry.severity}`}
                    </p>
                  </div>

                  {/* Status badge */}
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statusColors[entry.status] || statusColors.new}`}
                  >
                    {entry.status}
                  </span>

                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 flex-shrink-0 text-zinc-400" />
                  ) : (
                    <ChevronDown className="h-4 w-4 flex-shrink-0 text-zinc-400" />
                  )}
                </button>

                {/* Expanded content */}
                {isExpanded && (
                  <div className="border-t border-zinc-100 px-5 py-4 dark:border-zinc-800">
                    <div className="space-y-3 text-sm text-zinc-700 dark:text-zinc-300">
                      {isFeedback ? (
                        <>
                          <div>
                            <span className="font-medium text-zinc-500 dark:text-zinc-400">Category: </span>
                            {entry.category || "—"}
                          </div>
                          <div>
                            <span className="font-medium text-zinc-500 dark:text-zinc-400">Message: </span>
                            {entry.message || "—"}
                          </div>
                        </>
                      ) : (
                        <>
                          <div>
                            <span className="font-medium text-zinc-500 dark:text-zinc-400">Feature: </span>
                            {entry.feature || "—"}
                          </div>
                          <div>
                            <span className="font-medium text-zinc-500 dark:text-zinc-400">Severity: </span>
                            <span
                              className={
                                entry.severity === "critical"
                                  ? "font-semibold text-red-600 dark:text-red-400"
                                  : entry.severity === "high"
                                  ? "font-semibold text-amber-600 dark:text-amber-400"
                                  : ""
                              }
                            >
                              {entry.severity || "—"}
                            </span>
                          </div>
                          <div>
                            <span className="font-medium text-zinc-500 dark:text-zinc-400">Description: </span>
                            {entry.description || "—"}
                          </div>
                          {entry.steps && (
                            <div>
                              <span className="font-medium text-zinc-500 dark:text-zinc-400">Steps: </span>
                              {entry.steps}
                            </div>
                          )}
                        </>
                      )}
                      <div>
                        <span className="font-medium text-zinc-500 dark:text-zinc-400">Contact: </span>
                        {entry.name || "Anonymous"} {entry.email ? `(${entry.email})` : ""}
                      </div>

                      {/* Status controls */}
                      <div className="flex items-center gap-2 pt-2">
                        <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                          Set status:
                        </span>
                        {(["new", "reviewed", "resolved"] as const).map((s) => (
                          <button
                            key={s}
                            onClick={() => handleStatusChange(entry.id, s)}
                            disabled={entry.status === s || actionLoading === entry.id}
                            className={[
                              "rounded-lg px-3 py-1 text-xs font-medium transition",
                              entry.status === s
                                ? "cursor-default opacity-50 " + statusColors[s]
                                : "border border-zinc-200 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800",
                              "disabled:opacity-40",
                            ].join(" ")}
                          >
                            {s}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
