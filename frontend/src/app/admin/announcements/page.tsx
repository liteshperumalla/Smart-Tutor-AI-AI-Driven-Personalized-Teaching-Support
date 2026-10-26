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
import { toast } from "sonner";
import { Megaphone, Plus, Trash2, Edit2, Eye, EyeOff } from "lucide-react";
import { SkeletonCard, SkeletonRegion } from "@/components/skeleton";

const priorityStyles: Record<string, string> = {
  info: "border-primary/30 bg-primary-bg",
  warning: "border-warning/40 bg-warning-bg",
  critical: "border-danger/30 bg-danger-bg",
};

const priorityBadge: Record<string, string> = {
  info: "bg-primary-bg text-primary",
  warning: "bg-warning-bg text-warning",
  critical: "bg-danger-bg text-danger",
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
      toast.success("Announcement published");
    } catch {
      toast.error("Failed to create announcement");
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
      toast.success("Announcement updated");
    } catch {
      toast.error("Failed to update announcement");
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
      toast.success(currentActive ? "Announcement hidden" : "Announcement shown");
    } catch {
      toast.error("Failed to toggle announcement");
    }
  };

  const handleDelete = async (id: string) => {
    if (!token) return;
    try {
      await deleteAnnouncement(token, id);
      setAnnouncements((prev) => prev.filter((a) => a.id !== id));
      setDeleteConfirm(null);
      toast.success("Announcement deleted");
    } catch {
      toast.error("Failed to delete announcement");
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
        <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
          <Megaphone className="h-5 w-5" />
          Announcements
          <span className="ml-2 rounded-full bg-line px-2.5 py-0.5 text-xs font-medium text-foreground">
            {announcements.length}
          </span>
        </h2>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="btn-primary btn-sm"
          >
            <Plus className="h-4 w-4" />
            New Announcement
          </button>
        )}
      </div>

      {/* Create / Edit Form */}
      {showForm && (
        <div className="rounded-2xl border border-line bg-surface p-6">
          <h3 className="mb-4 text-sm font-semibold text-foreground">
            {editingId ? "Edit Announcement" : "Create Announcement"}
          </h3>
          <div className="space-y-4">
            <input
              type="text"
              placeholder="Title"
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              className="w-full rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-foreground outline-none focus:border-muted"
            />
            <textarea
              placeholder="Content"
              value={formContent}
              onChange={(e) => setFormContent(e.target.value)}
              rows={4}
              className="w-full rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-foreground outline-none focus:border-muted"
            />
            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-muted">Priority:</label>
              {(["info", "warning", "critical"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setFormPriority(p)}
                  className={[
                    "rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition",
                    formPriority === p
                      ? priorityBadge[p]
                      : "border border-line text-muted",
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
                className="btn-primary btn-sm disabled:opacity-50"
              >
                {saving ? "Saving…" : editingId ? "Update" : "Publish"}
              </button>
              <button
                onClick={resetForm}
                className="rounded-xl border border-line px-6 py-2 text-sm font-medium text-foreground transition hover:bg-surface-2"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Announcements List */}
      {loading ? (
        <SkeletonRegion label="Loading announcements" className="space-y-4">
          <SkeletonCard lines={2} />
          <SkeletonCard lines={2} />
          <SkeletonCard lines={1} />
        </SkeletonRegion>
      ) : announcements.length === 0 ? (
        <div className="rounded-2xl border border-line bg-surface-2 p-8 text-center text-muted">
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
                    <h3 className="text-sm font-semibold text-foreground">
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
                      <span className="rounded-full bg-line px-2 py-0.5 text-[10px] font-medium text-muted">
                        Inactive
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-sm text-foreground">{ann.content}</p>
                  <p className="mt-2 text-xs text-muted">
                    by {ann.author} · {new Date(ann.created_at).toLocaleDateString()}
                  </p>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handleToggleActive(ann.id, ann.active)}
                    className="rounded-lg p-2 text-muted transition hover:bg-surface-2"
                    title={ann.active ? "Deactivate" : "Activate"}
                  >
                    {ann.active ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                  <button
                    onClick={() => startEdit(ann)}
                    className="rounded-lg p-2 text-muted transition hover:bg-surface-2"
                    title="Edit"
                  >
                    <Edit2 className="h-4 w-4" />
                  </button>
                  {deleteConfirm === ann.id ? (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleDelete(ann.id)}
                        className="rounded-lg bg-danger-solid px-2 py-1 text-xs text-white hover:brightness-110"
                      >
                        Yes
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(null)}
                        className="rounded-lg bg-line px-2 py-1 text-xs text-foreground hover:bg-line"
                      >
                        No
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setDeleteConfirm(ann.id)}
                      className="rounded-lg p-2 text-danger transition hover:bg-danger-bg"
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
