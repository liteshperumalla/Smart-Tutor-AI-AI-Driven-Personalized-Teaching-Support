"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuthToken } from "@/hooks/useAuthToken";
import {
  fetchAdminAnnouncements,
  createAnnouncement,
  updateAnnouncement,
  deleteAnnouncement,
  Announcement,
} from "@/lib/api";
import { Megaphone, Plus, Trash2, Edit2, Eye, EyeOff } from "lucide-react";

const priorityStyles: Record<string, string> = {
  info: "border-blue-300 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/30",
  warning: "border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30",
  critical: "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950/30",
};

const priorityBadge: Record<string, string> = {
  info: "bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400",
  warning: "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400",
  critical: "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400",
};

export default function AdminAnnouncementsPage() {
  const { token } = useAuthToken({ redirectTo: "/login" });
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formTitle, setFormTitle] = useState("");
  const [formContent, setFormContent] = useState("");
  const [formPriority, setFormPriority] = useState("info");
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await fetchAdminAnnouncements(token);
      setAnnouncements(data);
    } catch {
      setAnnouncements([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const resetForm = () => {
    setShowForm(false);
    setEditingId(null);
    setFormTitle("");
    setFormContent("");
    setFormPriority("info");
  };

  const handleCreate = async () => {
    if (!token || !formTitle.trim() || !formContent.trim()) return;
    setSaving(true);
    try {
      await createAnnouncement(token, {
        title: formTitle,
        content: formContent,
        priority: formPriority,
      });
      resetForm();
      await load();
    } catch {
      // silently fail
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (!token || !editingId) return;
    setSaving(true);
    try {
      await updateAnnouncement(token, editingId, {
        title: formTitle || undefined,
        content: formContent || undefined,
        priority: formPriority,
      });
      resetForm();
      await load();
    } catch {
      // silently fail
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (id: string, currentActive: boolean) => {
    if (!token) return;
    try {
      await updateAnnouncement(token, id, { active: !currentActive });
      setAnnouncements((prev) =>
        prev.map((a) => (a.id === id ? { ...a, active: !currentActive } : a))
      );
    } catch {
      // silently fail
    }
  };

  const handleDelete = async (id: string) => {
    if (!token) return;
    try {
      await deleteAnnouncement(token, id);
      setAnnouncements((prev) => prev.filter((a) => a.id !== id));
      setDeleteConfirm(null);
    } catch {
      // silently fail
    }
  };

  const startEdit = (ann: Announcement) => {
    setEditingId(ann.id);
    setFormTitle(ann.title);
    setFormContent(ann.content);
    setFormPriority(ann.priority);
    setShowForm(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-zinc-900 dark:text-white">
          <Megaphone className="h-5 w-5" />
          Announcements
          <span className="ml-2 rounded-full bg-zinc-200 px-2.5 py-0.5 text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
            {announcements.length}
          </span>
        </h2>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-2 rounded-xl bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-200"
          >
            <Plus className="h-4 w-4" />
            New Announcement
          </button>
        )}
      </div>

      {/* Create / Edit Form */}
      {showForm && (
        <div className="rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900/60">
          <h3 className="mb-4 text-sm font-semibold text-zinc-900 dark:text-white">
            {editingId ? "Edit Announcement" : "Create Announcement"}
          </h3>
          <div className="space-y-4">
            <input
              type="text"
              placeholder="Title"
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 outline-none focus:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
            />
            <textarea
              placeholder="Content"
              value={formContent}
              onChange={(e) => setFormContent(e.target.value)}
              rows={4}
              className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 outline-none focus:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
            />
            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-zinc-600 dark:text-zinc-400">Priority:</label>
              {(["info", "warning", "critical"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setFormPriority(p)}
                  className={[
                    "rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition",
                    formPriority === p
                      ? priorityBadge[p]
                      : "border border-zinc-200 text-zinc-500 dark:border-zinc-700 dark:text-zinc-400",
                  ].join(" ")}
                >
                  {p}
                </button>
              ))}
            </div>
            <div className="flex gap-3">
              <button
                onClick={editingId ? handleUpdate : handleCreate}
                disabled={saving || !formTitle.trim() || !formContent.trim()}
                className="rounded-xl bg-zinc-900 px-6 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-50 dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-200"
              >
                {saving ? "Saving…" : editingId ? "Update" : "Publish"}
              </button>
              <button
                onClick={resetForm}
                className="rounded-xl border border-zinc-200 px-6 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Announcements List */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-white" />
        </div>
      ) : announcements.length === 0 ? (
        <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-8 text-center text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/30 dark:text-zinc-400">
          No announcements yet. Create one to get started.
        </div>
      ) : (
        <div className="space-y-3">
          {announcements.map((ann) => (
            <div
              key={ann.id}
              className={`rounded-2xl border-l-4 border p-5 ${
                priorityStyles[ann.priority] || priorityStyles.info
              } ${!ann.active ? "opacity-50" : ""}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-zinc-900 dark:text-white">
                      {ann.title}
                    </h3>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase ${
                        priorityBadge[ann.priority] || priorityBadge.info
                      }`}
                    >
                      {ann.priority}
                    </span>
                    {!ann.active && (
                      <span className="rounded-full bg-zinc-200 px-2 py-0.5 text-[10px] font-medium text-zinc-500 dark:bg-zinc-700 dark:text-zinc-400">
                        Inactive
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-sm text-zinc-700 dark:text-zinc-300">{ann.content}</p>
                  <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                    by {ann.author} · {new Date(ann.created_at).toLocaleDateString()}
                  </p>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handleToggleActive(ann.id, ann.active)}
                    className="rounded-lg p-2 text-zinc-500 transition hover:bg-zinc-100 dark:hover:bg-zinc-800"
                    title={ann.active ? "Deactivate" : "Activate"}
                  >
                    {ann.active ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                  <button
                    onClick={() => startEdit(ann)}
                    className="rounded-lg p-2 text-zinc-500 transition hover:bg-zinc-100 dark:hover:bg-zinc-800"
                    title="Edit"
                  >
                    <Edit2 className="h-4 w-4" />
                  </button>
                  {deleteConfirm === ann.id ? (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleDelete(ann.id)}
                        className="rounded-lg bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-700"
                      >
                        Yes
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(null)}
                        className="rounded-lg bg-zinc-200 px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-300"
                      >
                        No
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setDeleteConfirm(ann.id)}
                      className="rounded-lg p-2 text-red-500 transition hover:bg-red-50 dark:hover:bg-red-950/30"
                      title="Delete"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
