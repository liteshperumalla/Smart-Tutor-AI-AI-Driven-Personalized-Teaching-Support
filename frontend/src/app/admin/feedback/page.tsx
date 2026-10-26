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
import { SkeletonList, SkeletonRegion } from "@/components/skeleton";

type TabFilter = "all" | "feedback" | "bug" | "report";

const statusColors: Record<string, string> = {
  new: "bg-primary-bg text-primary",
  reviewed: "bg-warning-bg text-warning",
  resolved: "bg-success-bg text-success",
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
      <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
        <MessageSquare className="h-5 w-5" />
        Feedback, Reports & Bugs
        <span className="ml-2 rounded-full bg-line px-2.5 py-0.5 text-xs font-medium text-foreground">
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
                  ? "bg-primary-solid text-white"
                  : "bg-surface-2 text-muted hover:bg-line",
              ].join(" ")}
            >
              <Icon className="h-4 w-4" />
              {t.label}
            </button>
          );
        })}
        <label className="sr-only" htmlFor="feedback-search">Search feedback</label><div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" /><input id="feedback-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search feedback" className="rounded-xl border border-line bg-surface py-2 pl-9 pr-3 text-sm" /></div>
        <label className="sr-only" htmlFor="feedback-course">Course</label><select id="feedback-course" value={courseId} onChange={(event) => setCourseId(event.target.value)} className="ml-auto rounded-xl border border-line bg-surface px-3 py-2 text-sm text-foreground">
          <option value="">All courses and unscoped</option>
          {courses.map((course) => <option key={course.id} value={course.id}>{course.code}</option>)}
        </select>
      </div>

      {loading ? (
        <SkeletonRegion label="Loading feedback">
          <SkeletonList rows={4} />
        </SkeletonRegion>
      ) : visibleEntries.length === 0 ? (
        <div className="rounded-2xl border border-line bg-surface-2 p-8 text-center text-muted">
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
                className="rounded-2xl border border-line bg-surface transition"
              >
                {/* Header row */}
                <button
                  onClick={() => setExpanded(isExpanded ? null : entry.id)}
                  className="flex w-full items-center gap-3 px-5 py-4 text-left"
                >
                  {isFeedback ? (
                    <MessageSquare className="h-4 w-4 flex-shrink-0 text-primary" />
                  ) : isReport ? (
                    <Flag className="h-4 w-4 flex-shrink-0 text-warning" />
                  ) : (
                    <Bug className="h-4 w-4 flex-shrink-0 text-danger" />
                  )}

                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
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
                    <p className="text-xs text-muted">
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
                    <ChevronUp className="h-4 w-4 flex-shrink-0 text-muted" />
                  ) : (
                    <ChevronDown className="h-4 w-4 flex-shrink-0 text-muted" />
                  )}
                </button>

                {/* Expanded content */}
                {isExpanded && (
                  <div className="border-t border-line px-5 py-4">
                    <div className="space-y-3 text-sm text-foreground">
                      {isFeedback ? (
                        <>
                          <div>
                            <span className="font-medium text-muted">Category: </span>
                            {entry.category || "—"}
                          </div>
                          <div>
                            <span className="font-medium text-muted">Message: </span>
                            {entry.message || "—"}
                          </div>
                        </>
                      ) : isReport ? (
                        <>
                          <div>
                            <span className="font-medium text-muted">Reason: </span>
                            {entry.reason || entry.message || "—"}
                          </div>
                          <div>
                            <span className="font-medium text-muted">Session ID: </span>
                            {entry.session_id || "—"}
                          </div>
                          {entry.session_id && <Link href={`/chat?session=${encodeURIComponent(entry.session_id)}${entry.course_id ? `&course=${encodeURIComponent(entry.course_id)}` : ""}`} className="inline-flex text-sm font-semibold text-primary hover:underline">Open reported conversation</Link>}
                          <div>
                            <span className="font-medium text-muted">Message Index: </span>
                            {typeof entry.message_index === "number" ? entry.message_index : "—"}
                          </div>
                        </>
                      ) : (
                        <>
                          <div>
                            <span className="font-medium text-muted">Feature: </span>
                            {entry.feature || "—"}
                          </div>
                          <div>
                            <span className="font-medium text-muted">Severity: </span>
                            <span
                              className={
                                entry.severity === "critical"
                                  ? "font-semibold text-danger"
                                  : entry.severity === "high"
                                  ? "font-semibold text-warning"
                                  : ""
                              }
                            >
                              {entry.severity || "—"}
                            </span>
                          </div>
                          <div>
                            <span className="font-medium text-muted">Description: </span>
                            {entry.description || "—"}
                          </div>
                          {entry.steps && (
                            <div>
                              <span className="font-medium text-muted">Steps: </span>
                              {entry.steps}
                            </div>
                          )}
                        </>
                      )}
                      <div>
                        <span className="font-medium text-muted">Course: </span>
                        {entry.course_id || "Unscoped / legacy"}
                      </div>
                      <div>
                        <span className="font-medium text-muted">Contact: </span>
                        {entry.name || "Anonymous"} {entry.email ? `(${entry.email})` : ""}
                      </div>

                      {/* Status controls */}
                      <div className="flex items-center gap-2 pt-2">
                        <span className="text-xs font-medium text-muted">
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
                                : "border border-line text-muted hover:bg-surface-2",
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
