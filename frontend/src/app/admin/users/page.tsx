"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuthToken } from "@/hooks/useAuthToken";
import {
  fetchAdminUsers,
  updateUserRole,
  deleteAdminUser,
  AdminUser,
} from "@/lib/api";
import { toast } from "sonner";
import { Users, Trash2, Search } from "lucide-react";
import { Skeleton, SkeletonRegion, SkeletonTable } from "@/components/skeleton";

export default function AdminUsersPage() {
  const { token } = useAuthToken({ redirectTo: "/login" });
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await fetchAdminUsers(token);
      setUsers(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRoleChange = async (username: string, newRole: string) => {
    if (!token) return;
    // Granting or removing admin rights is a one-click select; confirm it
    // first (the select is controlled, so cancelling leaves the old role).
    const message =
      newRole === "Admin"
        ? `Make ${username} an Admin? Admins can manage every user, course and setting.`
        : `Remove admin rights from ${username}?`;
    if (!window.confirm(message)) return;
    setActionLoading(username);
    try {
      await updateUserRole(token, username, newRole);
      setUsers((prev) =>
        prev.map((u) => (u.username === username ? { ...u, role: newRole } : u))
      );
      toast.success(`Role updated to ${newRole}`);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to update role");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (username: string) => {
    if (!token) return;
    setActionLoading(username);
    try {
      await deleteAdminUser(token, username);
      setUsers((prev) => prev.filter((u) => u.username !== username));
      setDeleteConfirm(null);
      toast.success("User deleted");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to delete user");
    } finally {
      setActionLoading(null);
    }
  };

  const filtered = users.filter(
    (u) =>
      (u.username || "").toLowerCase().includes(search.toLowerCase()) ||
      (u.email || "").toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <SkeletonRegion label="Loading users" className="space-y-6">
        <div className="flex items-center justify-between gap-4">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-10 w-56 rounded-md" />
        </div>
        <SkeletonTable rows={6} columns={4} />
      </SkeletonRegion>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
          <Users className="h-5 w-5" />
          User Management
          <span className="ml-2 rounded-full bg-line px-2.5 py-0.5 text-xs font-medium text-foreground">
            {users.length}
          </span>
        </h2>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <input
            type="text"
            placeholder="Search users…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded-xl border border-line bg-surface py-2 pl-10 pr-4 text-sm text-foreground outline-none focus:border-muted"
          />
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-danger/30 bg-danger-bg p-4 text-sm text-danger">
          {error}
        </div>
      )}

      <div className="overflow-x-auto rounded-2xl border border-line">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-line bg-surface-2">
              <th className="px-4 py-3 font-medium text-muted">Username</th>
              <th className="px-4 py-3 font-medium text-muted">Email</th>
              <th className="px-4 py-3 font-medium text-muted">Role</th>
              <th className="hidden px-4 py-3 font-medium text-muted xl:table-cell">Created</th>
              <th className="hidden px-4 py-3 font-medium text-muted xl:table-cell">Last Login</th>
              <th className="px-4 py-3 font-medium text-muted">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((user) => (
              <tr
                key={user.username}
                className="border-b border-line transition hover:bg-surface-2"
              >
                <td className="px-4 py-3 font-medium text-foreground">
                  {user.username}
                </td>
                <td className="max-w-[16rem] truncate px-4 py-3 text-muted" title={user.email || undefined}>
                  {user.email || "—"}
                </td>
                <td className="px-4 py-3">
                  <select
                    value={user.role || "User"}
                    onChange={(e) => handleRoleChange(user.username, e.target.value)}
                    disabled={actionLoading === user.username}
                    className={[
                      "rounded-lg border px-3 py-1.5 text-xs font-medium outline-none transition",
                      user.role === "Admin"
                        ? "border-warning/40 bg-warning-bg text-warning"
                        : "border-line bg-surface-2 text-foreground",
                      "disabled:opacity-50",
                    ].join(" ")}
                  >
                    <option value="User">User</option>
                    <option value="Admin">Admin</option>
                  </select>
                </td>
                {/* Dates hide below xl so Role and Actions stay on screen next to the sidebar. */}
                <td className="hidden px-4 py-3 text-xs text-muted xl:table-cell">
                  {user.created_at
                    ? new Date(user.created_at).toLocaleDateString()
                    : "—"}
                </td>
                <td className="hidden px-4 py-3 text-xs text-muted xl:table-cell">
                  {user.last_login
                    ? new Date(user.last_login).toLocaleDateString()
                    : "Never"}
                </td>
                <td className="px-4 py-3">
                  {deleteConfirm === user.username ? (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleDelete(user.username)}
                        disabled={actionLoading === user.username}
                        className="rounded-lg bg-danger-solid px-3 py-1 text-xs font-medium text-white transition hover:brightness-110 disabled:opacity-50"
                      >
                        Confirm
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(null)}
                        className="rounded-lg bg-line px-3 py-1 text-xs font-medium text-foreground transition hover:bg-line"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setDeleteConfirm(user.username)}
                      className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-danger transition hover:bg-danger-bg"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted">
                  {search ? "No users match your search." : "No users found."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
