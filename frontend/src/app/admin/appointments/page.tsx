"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuthToken } from "@/hooks/useAuthToken";
import {
  fetchAdminAppointments,
  updateAdminAppointmentStatus,
  AdminAppointmentEntry,
} from "@/lib/api";
import { CalendarDays, ChevronDown, ChevronUp, Filter } from "lucide-react";
import { toast } from "sonner";
import { SkeletonList, SkeletonRegion } from "@/components/skeleton";

type AppointmentFilter = "all" | "pending" | "confirmed" | "cancelled" | "completed";

const statusColors: Record<string, string> = {
  pending: "bg-warning-bg text-warning",
  confirmed: "bg-success-bg text-success",
  cancelled: "bg-danger-bg text-danger",
  completed: "bg-primary-bg text-primary",
};

export default function AdminAppointmentsPage() {
  const { token } = useAuthToken({ redirectTo: "/login" });
  const [entries, setEntries] = useState<AdminAppointmentEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<AppointmentFilter>("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const status = tab === "all" ? undefined : tab;
      const data = await fetchAdminAppointments(token, status, 500);
      setEntries(data.appointments);
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
      const response = await updateAdminAppointmentStatus(token, id, newStatus);
      setEntries((prev) =>
        prev.map((entry) => (entry.id === id ? response.appointment : entry))
      );
      toast.success(`Appointment marked ${newStatus}`);
    } catch {
      toast.error("Failed to update appointment status");
    } finally {
      setActionLoading(null);
    }
  };

  const tabs: AppointmentFilter[] = [
    "all",
    "pending",
    "confirmed",
    "completed",
    "cancelled",
  ];

  return (
    <div className="space-y-6">
      <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
        <CalendarDays className="h-5 w-5" />
        Appointment Requests
        <span className="ml-2 rounded-full bg-line px-2.5 py-0.5 text-xs font-medium text-foreground">
          {entries.length}
        </span>
      </h2>

      <div className="flex flex-wrap gap-2">
        {tabs.map((status) => (
          <button
            key={status}
            onClick={() => setTab(status)}
            className={[
              "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition",
              tab === status
                ? "bg-primary-solid text-white"
                : "bg-surface-2 text-muted hover:bg-line",
            ].join(" ")}
          >
            <Filter className="h-4 w-4" />
            {status[0].toUpperCase() + status.slice(1)}
          </button>
        ))}
      </div>

      {loading ? (
        <SkeletonRegion label="Loading appointment requests">
          <SkeletonList rows={4} />
        </SkeletonRegion>
      ) : entries.length === 0 ? (
        <div className="rounded-2xl border border-line bg-surface-2 p-8 text-center text-muted">
          No appointment requests found.
        </div>
      ) : (
        <div className="space-y-3">
          {entries.map((entry) => {
            const isExpanded = expanded === entry.id;
            return (
              <div
                key={entry.id}
                className="rounded-2xl border border-line bg-surface transition"
              >
                <button
                  onClick={() => setExpanded(isExpanded ? null : entry.id)}
                  className="flex w-full items-center gap-3 px-5 py-4 text-left"
                >
                  <CalendarDays className="h-4 w-4 flex-shrink-0 text-info" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
                      {entry.user_name || entry.user_id || "Unknown user"} · {entry.appointment_with}
                    </p>
                    <p className="text-xs text-muted">
                      {entry.preferred_date} at {entry.preferred_time} · {entry.primary_reason}
                    </p>
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statusColors[entry.status] || statusColors.pending}`}
                  >
                    {entry.status}
                  </span>
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 flex-shrink-0 text-muted" />
                  ) : (
                    <ChevronDown className="h-4 w-4 flex-shrink-0 text-muted" />
                  )}
                </button>

                {isExpanded && (
                  <div className="border-t border-line px-5 py-4">
                    <div className="space-y-3 text-sm text-foreground">
                      <div>
                        <span className="font-medium text-muted">User: </span>
                        {entry.user_name || "Unknown"} ({entry.user_id || "—"})
                      </div>
                      <div>
                        <span className="font-medium text-muted">Email: </span>
                        {entry.user_email || "—"}
                      </div>
                      <div>
                        <span className="font-medium text-muted">Requested at: </span>
                        {entry.requested_at ? new Date(entry.requested_at).toLocaleString() : "—"}
                      </div>
                      <div>
                        <span className="font-medium text-muted">Reason: </span>
                        {entry.primary_reason || "—"}
                      </div>
                      {entry.additional_details && (
                        <div>
                          <span className="font-medium text-muted">Details: </span>
                          {entry.additional_details}
                        </div>
                      )}
                      <div className="flex flex-wrap items-center gap-2 pt-2">
                        <span className="text-xs font-medium text-muted">
                          Set status:
                        </span>
                        {(["pending", "confirmed", "completed", "cancelled"] as const).map((status) => (
                          <button
                            key={status}
                            onClick={() => handleStatusChange(entry.id, status)}
                            disabled={entry.status === status || actionLoading === entry.id}
                            className={[
                              "rounded-lg px-3 py-1 text-xs font-medium transition",
                              entry.status === status
                                ? "cursor-default opacity-50 " + (statusColors[status] || statusColors.pending)
                                : "border border-line text-muted hover:bg-surface-2",
                              "disabled:opacity-40",
                            ].join(" ")}
                          >
                            {status}
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
