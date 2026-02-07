"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuthToken } from "@/hooks/useAuthToken";
import {
  fetchAdminResources,
  createResource,
  uploadResourceFile,
  updateResource,
  deleteResource,
  migrateStaticResources,
  Resource,
} from "@/lib/api";
import {
  FolderOpen,
  Plus,
  Trash2,
  Edit2,
  Eye,
  EyeOff,
  Link as LinkIcon,
  FileText,
  Upload,
  ArrowDownToLine,
  DatabaseBackup,
} from "lucide-react";

type TabFilter = "all" | "link" | "file";

export default function AdminResourcesPage() {
  const { token } = useAuthToken({ redirectTo: "/login" });
  const [resources, setResources] = useState<Resource[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabFilter>("all");
  const [showForm, setShowForm] = useState(false);
  const [formMode, setFormMode] = useState<"link" | "file">("link");
  const [editingId, setEditingId] = useState<string | null>(null);

  // Form fields
  const [formCategory, setFormCategory] = useState("");
  const [formTitle, setFormTitle] = useState("");
  const [formUrl, setFormUrl] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formFile, setFormFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [migrating, setMigrating] = useState(false);
  const [migrateResult, setMigrateResult] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await fetchAdminResources(token);
      setResources(data.resources ?? []);
    } catch {
      setResources([]);
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
    setFormCategory("");
    setFormTitle("");
    setFormUrl("");
    setFormDescription("");
    setFormFile(null);
    setFormMode("link");
  };

  const handleCreateLink = async () => {
    if (!token || !formTitle.trim() || !formUrl.trim() || !formCategory.trim()) return;
    setSaving(true);
    try {
      await createResource(token, {
        category: formCategory,
        title: formTitle,
        url: formUrl,
        description: formDescription,
      });
      resetForm();
      await load();
    } catch {
      /* silently fail */
    } finally {
      setSaving(false);
    }
  };

  const handleUploadFile = async () => {
    if (!token || !formTitle.trim() || !formCategory.trim() || !formFile) return;
    setSaving(true);
    try {
      await uploadResourceFile({
        token,
        file: formFile,
        category: formCategory,
        title: formTitle,
        description: formDescription,
      });
      resetForm();
      await load();
    } catch {
      /* silently fail */
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (!token || !editingId) return;
    setSaving(true);
    try {
      await updateResource(token, editingId, {
        category: formCategory || undefined,
        title: formTitle || undefined,
        url: formUrl || undefined,
        description: formDescription,
      });
      resetForm();
      await load();
    } catch {
      /* silently fail */
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (id: string, currentActive: boolean) => {
    if (!token) return;
    try {
      await updateResource(token, id, { active: !currentActive });
      setResources((prev) =>
        prev.map((r) => (r.id === id ? { ...r, active: !currentActive } : r))
      );
    } catch {
      /* silently fail */
    }
  };

  const handleDelete = async (id: string) => {
    if (!token) return;
    try {
      await deleteResource(token, id);
      setResources((prev) => prev.filter((r) => r.id !== id));
      setDeleteConfirm(null);
    } catch {
      /* silently fail */
    }
  };

  const handleMigrate = async () => {
    if (!token) return;
    setMigrating(true);
    setMigrateResult(null);
    try {
      const result = await migrateStaticResources(token);
      setMigrateResult(
        result.success
          ? `Imported ${result.imported} resources (${result.total} total)`
          : result.imported === 0
            ? "No new resources to import"
            : "Migration failed"
      );
      await load();
    } catch {
      setMigrateResult("Migration failed");
    } finally {
      setMigrating(false);
    }
  };

  const startEdit = (res: Resource) => {
    setEditingId(res.id);
    setFormCategory(res.category);
    setFormTitle(res.title);
    setFormUrl(res.url ?? "");
    setFormDescription(res.description);
    setFormMode(res.type);
    setShowForm(true);
  };

  // Filter resources by tab
  const filtered = resources.filter((r) => {
    if (tab === "link") return r.type === "link";
    if (tab === "file") return r.type === "file";
    return true;
  });

  // Unique categories for info
  const uniqueCategories = [...new Set(resources.map((r) => r.category))].sort();

  const formatBytes = (bytes: number | null) => {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-zinc-900 dark:text-white">
          <FolderOpen className="h-5 w-5" />
          Resources
          <span className="ml-2 rounded-full bg-zinc-200 px-2.5 py-0.5 text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
            {resources.length}
          </span>
        </h2>
        <div className="flex items-center gap-2">
          {!showForm && (
            <button
              onClick={() => setShowForm(true)}
              className="flex items-center gap-2 rounded-xl bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-200"
            >
              <Plus className="h-4 w-4" />
              Add Resource
            </button>
          )}
        </div>
      </div>

      {/* Tab Filter */}
      <div className="flex items-center gap-2">
        {(["all", "link", "file"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={[
              "rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition",
              tab === t
                ? "bg-zinc-900 text-white dark:bg-white dark:text-zinc-900"
                : "border border-zinc-200 text-zinc-500 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800",
            ].join(" ")}
          >
            {t === "all" ? `All (${resources.length})` : t === "link" ? `Links (${resources.filter((r) => r.type === "link").length})` : `Files (${resources.filter((r) => r.type === "file").length})`}
          </button>
        ))}

        {/* Migrate Button */}
        <div className="ml-auto flex items-center gap-2">
          {migrateResult && (
            <span className="text-xs text-green-600 dark:text-green-400">{migrateResult}</span>
          )}
          <button
            onClick={handleMigrate}
            disabled={migrating}
            className="flex items-center gap-2 rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-600 transition hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800"
          >
            <DatabaseBackup className="h-3.5 w-3.5" />
            {migrating ? "Importing…" : "Import Static Resources"}
          </button>
        </div>
      </div>

      {/* Create / Edit Form */}
      {showForm && (
        <div className="rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900/60">
          <h3 className="mb-4 text-sm font-semibold text-zinc-900 dark:text-white">
            {editingId ? "Edit Resource" : "Add Resource"}
          </h3>

          {/* Mode Toggle (only for new) */}
          {!editingId && (
            <div className="mb-4 flex gap-2">
              <button
                onClick={() => setFormMode("link")}
                className={[
                  "flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition",
                  formMode === "link"
                    ? "bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400"
                    : "border border-zinc-200 text-zinc-500 dark:border-zinc-700 dark:text-zinc-400",
                ].join(" ")}
              >
                <LinkIcon className="h-3.5 w-3.5" />
                Link
              </button>
              <button
                onClick={() => setFormMode("file")}
                className={[
                  "flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition",
                  formMode === "file"
                    ? "bg-purple-100 text-purple-700 dark:bg-purple-950/40 dark:text-purple-400"
                    : "border border-zinc-200 text-zinc-500 dark:border-zinc-700 dark:text-zinc-400",
                ].join(" ")}
              >
                <Upload className="h-3.5 w-3.5" />
                File Upload
              </button>
            </div>
          )}

          <div className="space-y-4">
            {/* Category with suggestions */}
            <div>
              <input
                type="text"
                placeholder="Category (e.g. Python Fundamentals)"
                value={formCategory}
                onChange={(e) => setFormCategory(e.target.value)}
                list="resource-categories"
                className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 outline-none focus:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
              />
              <datalist id="resource-categories">
                {uniqueCategories.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
            </div>

            <input
              type="text"
              placeholder="Title"
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 outline-none focus:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
            />

            {formMode === "link" && !editingId ? (
              <input
                type="url"
                placeholder="URL (https://...)"
                value={formUrl}
                onChange={(e) => setFormUrl(e.target.value)}
                className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 outline-none focus:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
              />
            ) : editingId && formMode === "link" ? (
              <input
                type="url"
                placeholder="URL (https://...)"
                value={formUrl}
                onChange={(e) => setFormUrl(e.target.value)}
                className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 outline-none focus:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
              />
            ) : !editingId ? (
              /* File upload zone */
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  const f = e.dataTransfer.files[0];
                  if (f) setFormFile(f);
                }}
                className="flex cursor-pointer flex-col items-center gap-3 rounded-xl border-2 border-dashed border-zinc-300 bg-zinc-50 px-6 py-8 text-center transition hover:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-800/30 dark:hover:border-zinc-600"
              >
                <Upload className="h-8 w-8 text-zinc-400" />
                {formFile ? (
                  <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    {formFile.name} ({formatBytes(formFile.size)})
                  </p>
                ) : (
                  <>
                    <p className="text-sm text-zinc-600 dark:text-zinc-400">
                      Click to choose or drag a file here
                    </p>
                    <p className="text-xs text-zinc-400 dark:text-zinc-500">
                      PDF, PPTX, DOCX, or any document (max 50 MB)
                    </p>
                  </>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setFormFile(f);
                  }}
                />
              </div>
            ) : null}

            <textarea
              placeholder="Description (optional)"
              value={formDescription}
              onChange={(e) => setFormDescription(e.target.value)}
              rows={2}
              className="w-full rounded-xl border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 outline-none focus:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
            />

            <div className="flex gap-3">
              <button
                onClick={editingId ? handleUpdate : formMode === "link" ? handleCreateLink : handleUploadFile}
                disabled={
                  saving ||
                  !formTitle.trim() ||
                  !formCategory.trim() ||
                  (!editingId && formMode === "link" && !formUrl.trim()) ||
                  (!editingId && formMode === "file" && !formFile)
                }
                className="rounded-xl bg-zinc-900 px-6 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-50 dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-200"
              >
                {saving ? "Saving…" : editingId ? "Update" : formMode === "link" ? "Add Link" : "Upload File"}
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

      {/* Resource List */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-white" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-zinc-200 bg-zinc-50 p-8 text-center dark:border-zinc-800 dark:bg-zinc-900/30">
          <FolderOpen className="h-10 w-10 text-zinc-300 dark:text-zinc-600" />
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            {resources.length === 0
              ? 'No resources yet. Click "Import Static Resources" to seed from the catalog, or add one manually.'
              : "No resources match this filter."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((res) => (
            <div
              key={res.id}
              className={`rounded-2xl border p-5 transition hover:shadow-md ${
                res.type === "file"
                  ? "border-purple-200 bg-purple-50/30 dark:border-purple-900 dark:bg-purple-950/10"
                  : "border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/60"
              } ${!res.active ? "opacity-50" : ""}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    {res.type === "file" ? (
                      <FileText className="h-4 w-4 flex-shrink-0 text-purple-500" />
                    ) : (
                      <LinkIcon className="h-4 w-4 flex-shrink-0 text-blue-500" />
                    )}
                    <h3 className="text-sm font-semibold text-zinc-900 dark:text-white">
                      {res.title}
                    </h3>
                    <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                      {res.category}
                    </span>
                    {!res.active && (
                      <span className="rounded-full bg-zinc-200 px-2 py-0.5 text-[10px] font-medium text-zinc-500 dark:bg-zinc-700 dark:text-zinc-400">
                        Inactive
                      </span>
                    )}
                  </div>
                  {res.description && (
                    <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{res.description}</p>
                  )}
                  <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                    {res.type === "link" && res.url && (
                      <a href={res.url} target="_blank" rel="noreferrer" className="text-blue-500 hover:underline">
                        {res.url.length > 60 ? res.url.slice(0, 60) + "…" : res.url}
                      </a>
                    )}
                    {res.type === "file" && (
                      <span className="flex items-center gap-1">
                        <ArrowDownToLine className="h-3 w-3" />
                        {res.file_name} · {formatBytes(res.file_size_bytes)}
                      </span>
                    )}
                    <span className="ml-2">
                      by {res.created_by} · {new Date(res.created_at).toLocaleDateString()}
                    </span>
                  </p>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handleToggleActive(res.id, res.active)}
                    className="rounded-lg p-2 text-zinc-500 transition hover:bg-zinc-100 dark:hover:bg-zinc-800"
                    title={res.active ? "Deactivate" : "Activate"}
                  >
                    {res.active ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                  <button
                    onClick={() => startEdit(res)}
                    className="rounded-lg p-2 text-zinc-500 transition hover:bg-zinc-100 dark:hover:bg-zinc-800"
                    title="Edit"
                  >
                    <Edit2 className="h-4 w-4" />
                  </button>
                  {deleteConfirm === res.id ? (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleDelete(res.id)}
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
                      onClick={() => setDeleteConfirm(res.id)}
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
