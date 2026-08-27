"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuthToken } from "@/hooks/useAuthToken";
import {
  fetchAllFeedback,
  updateFeedbackStatus,
  AdminFeedbackEntry,
  Course,
  fetchCourses,
} from "@/lib/api";
import { toast } from "sonner";
import { MessageSquare, Bug, Filter, ChevronDown, ChevronUp, Flag, Search } from "lucide-react";

type TabFilter = "all" | "feedback" | "bug" | "report";

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
  const [courses, setCourses] = useState<Course[]>([]);
  const [courseId, setCourseId] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const feedbackType = tab === "all" ? undefined : tab;
      const [data, availableCourses] = await Promise.all([
        fetchAllFeedback(token, feedbackType, 500, courseId || undefined),
        fetchCourses(token),
      ]);
      setEntries(data.feedback);
      setCourses(availableCourses);
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [token, tab, courseId]);

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
      toast.success(`Status changed to ${newStatus}`);
    } catch {
      toast.error("Failed to update status");
    } finally {
      setActionLoading(null);
    }
  };

  const tabs: { key: TabFilter; label: string; icon: typeof MessageSquare }[] = [
    { key: "all", label: "All", icon: Filter },
    { key: "feedback", label: "Feedback", icon: MessageSquare },
    { key: "bug", label: "Bug Reports", icon: Bug },
    { key: "report", label: "Message Reports", icon: Flag },
  ];
  const visibleEntries = entries.filter((entry) => {
    const haystack = [entry.username, entry.message, entry.reason, entry.description, entry.category, entry.feature, entry.course_id, entry.severity].filter(Boolean).join(" ").toLowerCase();
    return haystack.includes(search.trim().toLowerCase());
  });

  return (
    <div className="space-y-6">
      <h2 className="flex items-center gap-2 text-lg font-semibold text-zinc-900 dark:text-white">
        <MessageSquare className="h-5 w-5" />
        Feedback, Reports & Bugs
        <span className="ml-2 rounded-full bg-zinc-200 px-2.5 py-0.5 text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
          {visibleEntries.length}
        </span>
      </h2>

      {/* Tab Filters */}
      <div className="flex flex-wrap gap-2">
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
        <label className="sr-only" htmlFor="feedback-search">Search feedback</label><div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" /><input id="feedback-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search feedback" className="rounded-xl border border-zinc-200 bg-white py-2 pl-9 pr-3 text-sm dark:border-zinc-700 dark:bg-zinc-900" /></div>
        <label className="sr-only" htmlFor="feedback-course">Course</label><select id="feedback-course" value={courseId} onChange={(event) => setCourseId(event.target.value)} className="ml-auto rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
          <option value="">All courses and unscoped</option>
          {courses.map((course) => <option key={course.id} value={course.id}>{course.code}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-white" />
        </div>
      ) : visibleEntries.length === 0 ? (
        <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-8 text-center text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/30 dark:text-zinc-400">
          No feedback entries found.
        </div>
      ) : (
        <div className="space-y-3">
          {visibleEntries.map((entry) => {
            const isExpanded = expanded === entry.id;
            const isFeedback = entry.type === "feedback";
            const isReport = entry.type === "report";

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
                  ) : isReport ? (
                    <Flag className="h-4 w-4 flex-shrink-0 text-amber-500" />
                  ) : (
                    <Bug className="h-4 w-4 flex-shrink-0 text-red-500" />
                  )}

                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-zinc-900 dark:text-white">
                      {isFeedback
                        ? entry.message?.slice(0, 80) || "No message"
                        : isReport
                        ? entry.reason?.slice(0, 80) || "No report reason"
                        : entry.description?.slice(0, 80) || "No description"}
                      {((isFeedback
                        ? entry.message
                        : isReport
                        ? entry.reason
                        : entry.description) || "").length > 80
                        ? "…"
                        : ""}
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      by {entry.username} · {entry.created_at ? new Date(entry.created_at).toLocaleDateString() : "—"}
                      {isFeedback && entry.category && ` · ${entry.category}`}
                      {isReport && entry.session_id && ` · Session ${entry.session_id.slice(0, 8)}`}
                      {entry.course_id && ` · ${entry.course_id}`}
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
                      ) : isReport ? (
                        <>
                          <div>
                            <span className="font-medium text-zinc-500 dark:text-zinc-400">Reason: </span>
                            {entry.reason || entry.message || "—"}
                          </div>
                          <div>
                            <span className="font-medium text-zinc-500 dark:text-zinc-400">Session ID: </span>
                            {entry.session_id || "—"}
                          </div>
                          {entry.session_id && <Link href={`/chat?session=${encodeURIComponent(entry.session_id)}${entry.course_id ? `&course=${encodeURIComponent(entry.course_id)}` : ""}`} className="inline-flex text-sm font-semibold text-indigo-600 hover:underline dark:text-indigo-300">Open reported conversation</Link>}
                          <div>
                            <span className="font-medium text-zinc-500 dark:text-zinc-400">Message Index: </span>
                            {typeof entry.message_index === "number" ? entry.message_index : "—"}
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
                        <span className="font-medium text-zinc-500 dark:text-zinc-400">Course: </span>
                        {entry.course_id || "Unscoped / legacy"}
                      </div>
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
