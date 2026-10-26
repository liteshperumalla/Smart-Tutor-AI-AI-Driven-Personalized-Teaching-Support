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
  triggerReindex,
  fetchIndexStatus,
  fetchCourses,
  Resource,
  IndexStatus,
  Course,
} from "@/lib/api";
import { toast } from "sonner";
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
  Loader2,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
} from "lucide-react";

const INDEXABLE_EXTENSIONS = new Set([".pdf", ".pptx", ".docx", ".txt", ".md", ".ipynb"]);

function isIndexable(resource: Resource): boolean {
  if (resource.type !== "file" || !resource.file_name) return false;
  const dot = resource.file_name.lastIndexOf(".");
  const ext = dot >= 0 ? resource.file_name.slice(dot).toLowerCase() : "";
  return INDEXABLE_EXTENSIONS.has(ext);
}

type TabFilter = "all" | "link" | "file";

export default function AdminResourcesPage() {
  const { token } = useAuthToken({ redirectTo: "/login" });
  const [resources, setResources] = useState<Resource[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
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
  const [formCourseId, setFormCourseId] = useState("");
  const [formFile, setFormFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [migrating, setMigrating] = useState(false);
  const [migrateResult, setMigrateResult] = useState<string | null>(null);
  const [indexStatus, setIndexStatus] = useState<Record<string, IndexStatus>>({});

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await fetchAdminResources(token);
      setResources(data.resources ?? []);
      const availableCourses = await fetchCourses(token);
      setCourses(availableCourses);
      if (!availableCourses.some((course) => course.id === formCourseId)) {
        setFormCourseId(availableCourses[0]?.id ?? "");
      }
    } catch {
      setResources([]);
    } finally {
      setLoading(false);
    }
  }, [token, formCourseId]);

  useEffect(() => {
    load();
  }, [load]);

  // Poll indexing status for in-progress jobs every 2 seconds
  useEffect(() => {
    if (!token) return;
    const activeIds = Object.entries(indexStatus)
      .filter(([, s]) => s.status !== "complete" && s.status !== "error" && s.status !== "not_started")
      .map(([id]) => id);
    if (activeIds.length === 0) return;

    const timer = setInterval(async () => {
      for (const resourceId of activeIds) {
        try {
          const updated = await fetchIndexStatus(token, resourceId);
          setIndexStatus((prev) => ({ ...prev, [resourceId]: updated }));
        } catch { /* ignore — keep polling */ }
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [indexStatus, token]);

  const handleReindex = async (resourceId: string) => {
    if (!token) return;
    try {
      await triggerReindex(token, resourceId);
      setIndexStatus((prev) => ({
        ...prev,
        [resourceId]: { status: "queued", progress_pct: 0, chunks_created: 0, total_chunks: null, error: null },
      }));
      toast.success("Indexing started");
    } catch {
      toast.error("Failed to start indexing");
    }
  };

  const resetForm = () => {
    setShowForm(false);
    setEditingId(null);
    setFormCategory("");
    setFormTitle("");
    setFormUrl("");
    setFormDescription("");
    setFormCourseId(courses[0]?.id ?? "");
    setFormFile(null);
    setFormMode("link");
  };

  const handleCreateLink = async () => {
    if (!token || !formCourseId || !formTitle.trim() || !formUrl.trim() || !formCategory.trim()) return;
    setSaving(true);
    try {
      await createResource(token, {
        category: formCategory,
        title: formTitle,
        url: formUrl,
        description: formDescription,
        course_id: formCourseId,
      });
      resetForm();
      await load();
      toast.success("Resource created");
    } catch {
      toast.error("Failed to create resource");
    } finally {
      setSaving(false);
    }
  };

  const handleUploadFile = async () => {
    if (!token || !formCourseId || !formTitle.trim() || !formCategory.trim() || !formFile) return;
    setSaving(true);
    try {
      const result = await uploadResourceFile({
        token,
        file: formFile,
        category: formCategory,
        title: formTitle,
        description: formDescription,
        courseId: formCourseId,
      });
      resetForm();
      await load();
      toast.success("File uploaded");

      // Auto-trigger indexing for supported file types (backend already started it;
      // we just initialise the local status so the progress bar shows immediately)
      if (result?.id && isIndexable(result)) {
        setIndexStatus((prev) => ({
          ...prev,
          [result.id]: { status: "queued", progress_pct: 0, chunks_created: 0, total_chunks: null, error: null },
        }));
        toast.info("Indexing started automatically");
      }
    } catch {
      toast.error("Failed to upload file");
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (!token || !editingId || !formCourseId) return;
    setSaving(true);
    try {
      await updateResource(token, editingId, {
        category: formCategory || undefined,
        title: formTitle || undefined,
        url: formUrl || undefined,
        description: formDescription,
        course_id: formCourseId,
      });
      resetForm();
      await load();
      toast.success("Resource updated");
    } catch {
      toast.error("Failed to update resource");
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
      toast.success(currentActive ? "Resource hidden" : "Resource shown");
    } catch {
      toast.error("Failed to toggle resource");
    }
  };

  const handleDelete = async (id: string) => {
    if (!token) return;
    try {
      await deleteResource(token, id);
      setResources((prev) => prev.filter((r) => r.id !== id));
      setDeleteConfirm(null);
      toast.success("Resource deleted");
    } catch {
      toast.error("Failed to delete resource");
    }
  };

  const handleMigrate = async () => {
    if (!token) return;
    setMigrating(true);
    setMigrateResult(null);
    try {
      const result = await migrateStaticResources(token);
      const msg = result.success
        ? `Imported ${result.imported} resources (${result.total} total)`
        : result.imported === 0
          ? "No new resources to import"
          : "Migration failed";
      setMigrateResult(msg);
      await load();
      toast.success(msg);
    } catch {
      setMigrateResult("Migration failed");
      toast.error("Migration failed");
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
    setFormCourseId(res.course_id ?? "");
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
        <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
          <FolderOpen className="h-5 w-5" />
          Resources
          <span className="ml-2 rounded-full bg-line px-2.5 py-0.5 text-xs font-medium text-foreground">
            {resources.length}
          </span>
        </h2>
        <div className="flex items-center gap-2">
          {!showForm && (
            <button
              onClick={() => setShowForm(true)}
              className="btn-primary btn-sm"
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
                ? "bg-primary-solid text-white"
                : "border border-line text-muted hover:bg-surface-2",
            ].join(" ")}
          >
            {t === "all" ? `All (${resources.length})` : t === "link" ? `Links (${resources.filter((r) => r.type === "link").length})` : `Files (${resources.filter((r) => r.type === "file").length})`}
          </button>
        ))}

        {/* Migrate Button */}
        <div className="ml-auto flex items-center gap-2">
          {migrateResult && (
            <span className="text-xs text-success">{migrateResult}</span>
          )}
          <button
            onClick={handleMigrate}
            disabled={migrating}
            className="flex items-center gap-2 rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-muted transition hover:bg-surface-2 disabled:opacity-50"
          >
            <DatabaseBackup className="h-3.5 w-3.5" />
            {migrating ? "Importing…" : "Import Static Resources"}
          </button>
        </div>
      </div>

      {/* Create / Edit Form */}
      {showForm && (
        <div className="rounded-2xl border border-line bg-surface p-6">
          <h3 className="mb-4 text-sm font-semibold text-foreground">
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
                    ? "bg-primary-bg text-primary"
                    : "border border-line text-muted",
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
                    ? "bg-lavender/15 text-violet-700 dark:text-lavender"
                    : "border border-line text-muted",
                ].join(" ")}
              >
                <Upload className="h-3.5 w-3.5" />
                File Upload
              </button>
            </div>
          )}

          <div className="space-y-4">
            <label className="block text-sm font-medium text-foreground">
              Course workspace
              <select
                value={formCourseId}
                onChange={(event) => setFormCourseId(event.target.value)}
                className="mt-1.5 w-full rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-foreground outline-none focus:border-muted"
              >
                <option value="" disabled>Select a course workspace</option>
                {courses.map((course) => <option key={course.id} value={course.id}>{course.code} — {course.title}</option>)}
              </select>
            </label>
            {/* Category with suggestions */}
            <div>
              <input
                type="text"
                placeholder="Category (e.g. Python Fundamentals)"
                value={formCategory}
                onChange={(e) => setFormCategory(e.target.value)}
                list="resource-categories"
                className="w-full rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-foreground outline-none focus:border-muted"
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
              className="w-full rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-foreground outline-none focus:border-muted"
            />

            {formMode === "link" && !editingId ? (
              <input
                type="url"
                placeholder="URL (https://...)"
                value={formUrl}
                onChange={(e) => setFormUrl(e.target.value)}
                className="w-full rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-foreground outline-none focus:border-muted"
              />
            ) : editingId && formMode === "link" ? (
              <input
                type="url"
                placeholder="URL (https://...)"
                value={formUrl}
                onChange={(e) => setFormUrl(e.target.value)}
                className="w-full rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-foreground outline-none focus:border-muted"
              />
            ) : !editingId ? (
              /* File upload zone */
              <div
                role="button"
                tabIndex={0}
                aria-label="Choose a file to upload"
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); fileInputRef.current?.click(); } }}
                onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  const f = e.dataTransfer.files[0];
                  if (f) setFormFile(f);
                }}
                className="flex cursor-pointer flex-col items-center gap-3 rounded-xl border-2 border-dashed border-line bg-surface-2 px-6 py-8 text-center transition hover:border-muted"
              >
                <Upload className="h-8 w-8 text-muted" />
                {formFile ? (
                  <p className="text-sm font-medium text-foreground">
                    {formFile.name} ({formatBytes(formFile.size)})
                  </p>
                ) : (
                  <>
                    <p className="text-sm text-muted">
                      Click to choose or drag a file here
                    </p>
                    <p className="text-xs text-muted">
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
              className="w-full rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-foreground outline-none focus:border-muted"
            />

            <div className="flex gap-3">
              <button
                onClick={editingId ? handleUpdate : formMode === "link" ? handleCreateLink : handleUploadFile}
                disabled={
                  saving ||
                  !formCourseId ||
                  !formTitle.trim() ||
                  !formCategory.trim() ||
                  (!editingId && formMode === "link" && !formUrl.trim()) ||
                  (!editingId && formMode === "file" && !formFile)
                }
                className="btn-primary btn-sm disabled:opacity-50"
              >
                {saving ? "Saving…" : editingId ? "Update" : formMode === "link" ? "Add Link" : "Upload File"}
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

      {/* Resource List */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-primary" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-line bg-surface-2 p-8 text-center">
          <FolderOpen className="h-10 w-10 text-muted/40" />
          <p className="text-sm text-muted">
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
                  ? "border-lavender/40 bg-lavender/15"
                  : "border-line bg-surface"
              } ${!res.active ? "opacity-50" : ""}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    {res.type === "file" ? (
                      <FileText className="h-4 w-4 flex-shrink-0 text-violet-700 dark:text-lavender" />
                    ) : (
                      <LinkIcon className="h-4 w-4 flex-shrink-0 text-primary" />
                    )}
                    <h3 className="text-sm font-semibold text-foreground">
                      {res.title}
                    </h3>
                    <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[10px] font-medium text-muted">
                      {res.category}
                    </span>
                    {!res.active && (
                      <span className="rounded-full bg-line px-2 py-0.5 text-[10px] font-medium text-muted">
                        Inactive
                      </span>
                    )}
                  </div>
                  {res.description && (
                    <p className="mt-1 text-sm text-muted">{res.description}</p>
                  )}
                  <p className="mt-2 text-xs text-muted">
                    {res.type === "link" && res.url && (
                      <a href={res.url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
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

                  {/* Indexing progress (file resources only) */}
                  {isIndexable(res) && indexStatus[res.id] && (() => {
                    const idx = indexStatus[res.id];
                    const isActive = idx.status !== "complete" && idx.status !== "error" && idx.status !== "not_started";
                    return (
                      <div className="mt-2">
                        {idx.status === "complete" ? (
                          <p className="flex items-center gap-1 text-xs text-success">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            Indexed — {idx.chunks_created} chunks
                          </p>
                        ) : idx.status === "error" ? (
                          <p className="flex items-center gap-1 text-xs text-danger">
                            <AlertCircle className="h-3.5 w-3.5" />
                            Index error: {idx.error ?? "unknown"}
                          </p>
                        ) : isActive ? (
                          <div className="space-y-1">
                            <div className="flex items-center justify-between">
                              <p className="flex items-center gap-1 text-xs text-primary">
                                <Loader2 className="h-3 w-3 animate-spin" />
                                {idx.status === "queued" ? "Queued…"
                                  : idx.status === "extracting" ? "Extracting text…"
                                  : idx.status === "chunking" ? "Chunking…"
                                  : idx.status === "embedding" ? `Embedding${idx.total_chunks ? ` (${idx.chunks_created}/${idx.total_chunks})` : "…"}`
                                  : `Uploading chunks (${idx.chunks_created})`}
                              </p>
                              <span className="text-xs text-muted">{idx.progress_pct}%</span>
                            </div>
                            <div className="h-1.5 w-full rounded-full bg-line">
                              <div
                                className="h-1.5 rounded-full bg-primary-solid transition-all duration-500"
                                style={{ width: `${idx.progress_pct}%` }}
                              />
                            </div>
                          </div>
                        ) : null}
                      </div>
                    );
                  })()}
                </div>

                <div className="flex items-center gap-1">
                  {/* Re-index button for indexable file resources */}
                  {isIndexable(res) && (() => {
                    const idx = indexStatus[res.id];
                    const busy = idx && idx.status !== "complete" && idx.status !== "error" && idx.status !== "not_started";
                    return (
                      <button
                        onClick={() => handleReindex(res.id)}
                        disabled={!!busy}
                        className="rounded-lg p-2 text-primary transition hover:bg-primary-bg disabled:opacity-50"
                        title={busy ? "Indexing…" : "Re-index for RAG"}
                      >
                        {busy
                          ? <Loader2 className="h-4 w-4 animate-spin" />
                          : <RefreshCw className="h-4 w-4" />}
                      </button>
                    );
                  })()}
                  <button
                    onClick={() => handleToggleActive(res.id, res.active)}
                    className="rounded-lg p-2 text-muted transition hover:bg-surface-2"
                    title={res.active ? "Deactivate" : "Activate"}
                  >
                    {res.active ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                  <button
                    onClick={() => startEdit(res)}
                    className="rounded-lg p-2 text-muted transition hover:bg-surface-2"
                    title="Edit"
                  >
                    <Edit2 className="h-4 w-4" />
                  </button>
                  {deleteConfirm === res.id ? (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleDelete(res.id)}
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
                      onClick={() => setDeleteConfirm(res.id)}
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
