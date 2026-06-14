"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchResources, fetchResearchUploads, getResourceDownloadUrl, ResearchUpload, Resource } from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { PageShell } from "@/components/page-shell";
import { PageHero } from "@/components/page-hero";
import { FolderOpen, ExternalLink, FileText, Download } from "lucide-react";

type CategoryMap = Record<string, { title: string; url: string }[]>;

/** Colored file-type badge derived from a file name's extension. */
function FileBadge({ name }: { name?: string | null }) {
  const ext = (name?.split(".").pop() || "file").toUpperCase();
  const palette: Record<string, string> = {
    PDF: "bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400",
    IPYNB: "bg-orange-50 text-orange-600 dark:bg-orange-500/10 dark:text-orange-400",
    PPTX: "bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400",
    PPT: "bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400",
    DOCX: "bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400",
    DOC: "bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400",
    PY: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400",
  };
  const cls = palette[ext] || "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300";
  return (
    <span className={`flex-shrink-0 rounded-md px-2 py-1 text-[10px] font-bold tracking-wider ${cls}`}>
      .{ext}
    </span>
  );
}

/** Uppercase section header with an icon on the left and a count on the right. */
function SectionHeader({ label, count, unit }: { label: string; count: number; unit: string }) {
  return (
    <div className="mb-3 flex items-center justify-between px-1">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.25em] text-zinc-500 dark:text-zinc-400">
        <FileText className="h-4 w-4" />
        {label}
      </div>
      <span className="text-xs text-zinc-400 dark:text-zinc-500">
        {count} {unit}
      </span>
    </div>
  );
}

const ROW_CARD =
  "flex items-center gap-4 rounded-2xl border border-zinc-200 bg-white px-4 py-3.5 shadow-sm transition hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900";

export default function ResourcesPage() {
  const { token } = useAuthToken();
  const [categories, setCategories] = useState<CategoryMap>({});
  const [fileResources, setFileResources] = useState<Resource[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploads, setUploads] = useState<ResearchUpload[]>([]);
  const [downloading, setDownloading] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    fetchResources(token)
      .then((data) => {
        setCategories(data.categories || {});
        // Collect file-type resources from the full list
        const files = (data.resources ?? []).filter((r: Resource) => r.type === "file");
        setFileResources(files);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load resources"))
      .finally(() => setLoading(false));

    fetchResearchUploads(token)
      .then((data) => setUploads(data))
      .catch(() => setUploads([]));
  }, [token]);

  const handleDownload = async (resourceId: string) => {
    if (!token) return;
    setDownloading(resourceId);
    try {
      const { download_url, file_name } = await getResourceDownloadUrl(token, resourceId);
      // Open presigned URL in new tab
      const a = document.createElement("a");
      a.href = download_url;
      a.download = file_name;
      a.target = "_blank";
      a.rel = "noreferrer";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch {
      /* download failed silently */
    } finally {
      setDownloading(null);
    }
  };

  const categoryEntries = Object.entries(categories);

  const formatBytes = (bytes: number | null) => {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Group downloadable files by their category so each becomes a labeled section.
  const filesByCategory = fileResources.reduce<Record<string, Resource[]>>((acc, r) => {
    const key = r.category || "Course materials";
    (acc[key] ||= []).push(r);
    return acc;
  }, {});
  const fileSections = Object.entries(filesByCategory);

  const totalLinks = categoryEntries.reduce((n, [, links]) => n + links.length, 0);
  const totalFiles = fileResources.length + uploads.length;
  const totalDocs = totalFiles + totalLinks;
  const isEmpty = !loading && !error && totalDocs === 0;

  return (
    <PageShell className="max-w-5xl" contentClassName="gap-8" noCard>
      <PageHero
        icon={FolderOpen}
        eyebrow="Resources"
        title="Everything your"
        accent="tutor cites."
        subtitle="Slides, readings, and code demos — indexed and searchable from the chat."
        actions={
          <div className="rounded-2xl border border-zinc-200 bg-white/80 px-5 py-4 shadow-sm backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/70">
            <p className="text-[11px] font-semibold uppercase tracking-[0.25em] text-zinc-400 dark:text-zinc-500">
              Indexed
            </p>
            <p className="font-display text-2xl font-bold text-emerald-600 dark:text-emerald-400">
              {totalDocs} docs
            </p>
            <p className="text-xs text-zinc-400 dark:text-zinc-500">· {totalFiles} files</p>
          </div>
        }
      />

      {error && (
        <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400">
          {error}
        </p>
      )}

      {/* Loading state */}
      {loading && !error && (
        <div className="flex items-center justify-center py-20">
          <div className="flex flex-col items-center gap-4">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-white" />
            <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading resources…</p>
          </div>
        </div>
      )}

      {/* Downloadable course files, grouped by category */}
      {!loading &&
        fileSections.map(([name, files]) => (
          <section key={name} className="animate-fade-in-up">
            <SectionHeader label={name} count={files.length} unit={files.length === 1 ? "file" : "files"} />
            <div className="space-y-3">
              {files.map((res) => (
                <div key={res.id} className={ROW_CARD}>
                  <FileBadge name={res.file_name} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold text-zinc-900 dark:text-white">{res.title}</p>
                    {res.description && (
                      <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">{res.description}</p>
                    )}
                  </div>
                  <span className="hidden flex-shrink-0 text-xs tabular-nums text-zinc-400 dark:text-zinc-500 sm:block">
                    {formatBytes(res.file_size_bytes)}
                  </span>
                  <button
                    onClick={() => handleDownload(res.id)}
                    disabled={downloading === res.id}
                    aria-label={`Download ${res.title}`}
                    className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-zinc-200 text-zinc-500 transition hover:bg-zinc-50 hover:text-zinc-900 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white"
                  >
                    <Download className={`h-4 w-4 ${downloading === res.id ? "animate-pulse" : ""}`} />
                  </button>
                </div>
              ))}
            </div>
          </section>
        ))}

      {/* Curated external links, grouped by category */}
      {!loading &&
        categoryEntries.map(([name, links]) => (
          <section key={name} className="animate-fade-in-up">
            <SectionHeader label={name} count={links.length} unit={links.length === 1 ? "link" : "links"} />
            <div className="space-y-3">
              {links.map((link) => (
                <a
                  key={link.url}
                  href={link.url}
                  target="_blank"
                  rel="noreferrer"
                  className={`group ${ROW_CARD} hover:border-emerald-300 dark:hover:border-emerald-700`}
                >
                  <span className="flex-shrink-0 rounded-md bg-emerald-50 px-2 py-1 text-[10px] font-bold tracking-wider text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
                    .LINK
                  </span>
                  <p className="min-w-0 flex-1 truncate font-semibold text-zinc-900 transition group-hover:text-emerald-600 dark:text-white dark:group-hover:text-emerald-400">
                    {link.title}
                  </p>
                  <ExternalLink className="h-4 w-4 flex-shrink-0 text-zinc-400 dark:text-zinc-500" />
                </a>
              ))}
            </div>
          </section>
        ))}

      {/* Knowledge uploads */}
      {!loading && uploads.length > 0 && (
        <section className="animate-fade-in-up">
          <SectionHeader label="Uploads" count={uploads.length} unit={uploads.length === 1 ? "file" : "files"} />
          <div className="space-y-3">
            {uploads.map((upload) => (
              <div key={upload.id} className={ROW_CARD}>
                <FileBadge name={upload.file_name} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold text-zinc-900 dark:text-white">{upload.file_name}</p>
                  <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">
                    Uploaded {new Date(upload.uploaded_at).toLocaleDateString()}
                  </p>
                </div>
                <span className="hidden flex-shrink-0 text-xs tabular-nums text-zinc-400 dark:text-zinc-500 sm:block">
                  {Math.round(upload.size_bytes / 1024)} KB
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Empty state */}
      {isEmpty && (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-zinc-200 bg-zinc-50 p-10 text-center dark:border-zinc-800 dark:bg-zinc-900/30">
          <FolderOpen className="h-10 w-10 text-zinc-300 dark:text-zinc-600" />
          <p className="text-sm text-zinc-500 dark:text-zinc-400">No curated resources available yet.</p>
        </div>
      )}

      {/* Suggestion CTA */}
      {!loading && (
        <section className="rounded-2xl border border-dashed border-zinc-200 bg-zinc-50 p-6 text-sm text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-400">
          <p>
            See something missing?{" "}
            <Link href="/feedback" className="font-semibold text-emerald-600 hover:underline dark:text-emerald-400">
              Suggest a resource
            </Link>{" "}
            and we&apos;ll review it for the next release.
          </p>
        </section>
      )}
    </PageShell>
  );
}
