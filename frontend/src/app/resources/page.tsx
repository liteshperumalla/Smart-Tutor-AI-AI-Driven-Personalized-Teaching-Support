"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchResources, fetchResearchUploads, getResourceDownloadUrl, ResearchUpload, Resource } from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { PageShell } from "@/components/page-shell";
import { PageHero } from "@/components/page-hero";
import { FolderOpen, ExternalLink, FileText, Download, Search } from "lucide-react";

type CategoryMap = Record<string, { title: string; url: string }[]>;

/** Colored file-type badge derived from a file name's extension. */
function FileBadge({ name }: { name?: string | null }) {
  const ext = (name?.split(".").pop() || "file").toUpperCase();
  const palette: Record<string, string> = {
    PDF: "bg-danger-bg text-danger",
    IPYNB: "bg-warning-bg text-warning",
    PPTX: "bg-warning-bg text-warning",
    PPT: "bg-warning-bg text-warning",
    DOCX: "bg-primary-bg text-primary",
    DOC: "bg-primary-bg text-primary",
    PY: "bg-success-bg text-success",
  };
  const cls = palette[ext] || "bg-surface-2 text-muted";
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
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.25em] text-muted">
        <FileText className="h-4 w-4" />
        {label}
      </div>
      <span className="text-xs text-muted">
        {count} {unit}
      </span>
    </div>
  );
}

type KindFilter = "all" | "files" | "links";

const KIND_FILTERS: { id: KindFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "files", label: "Files" },
  { id: "links", label: "Links" },
];

const ROW_CARD =
  "flex items-center gap-4 rounded-2xl border border-line bg-surface px-4 py-3.5 shadow-sm transition hover:shadow-md";

export default function ResourcesPage() {
  const { token } = useAuthToken();
  const [categories, setCategories] = useState<CategoryMap>({});
  const [fileResources, setFileResources] = useState<Resource[]>([]);
  // Typed links keep a description that `categories` drops; keyed by URL so
  // search can match it.
  const [linkDescriptions, setLinkDescriptions] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploads, setUploads] = useState<ResearchUpload[]>([]);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<KindFilter>("all");

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    fetchResources(token)
      .then((data) => {
        setCategories(data.categories || {});
        // Collect file-type resources from the full list
        const files = (data.resources ?? []).filter((r: Resource) => r.type === "file");
        setFileResources(files);
        const descriptions: Record<string, string> = {};
        for (const r of data.resources ?? []) {
          if (r.type === "link" && r.url && r.description) descriptions[r.url] = r.description;
        }
        setLinkDescriptions(descriptions);
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

  const needle = query.trim().toLowerCase();
  const matches = (...fields: (string | null | undefined)[]) =>
    !needle || fields.some((f) => f?.toLowerCase().includes(needle));
  const showFiles = kind !== "links";
  const showLinks = kind !== "files";
  const visibleFiles = showFiles ? fileResources.filter((r) => matches(r.title, r.description, r.file_name, r.category)) : [];
  const visibleUploads = showFiles ? uploads.filter((u) => matches(u.file_name)) : [];
  const visibleLinkEntries = showLinks
    ? categoryEntries
        .map(([name, links]) => [name, links.filter((l) => matches(l.title, linkDescriptions[l.url], name))] as const)
        .filter(([, links]) => links.length > 0)
    : [];

  // Group downloadable files by their category so each becomes a labeled section.
  const filesByCategory = visibleFiles.reduce<Record<string, Resource[]>>((acc, r) => {
    const key = r.category || "Course materials";
    (acc[key] ||= []).push(r);
    return acc;
  }, {});
  const fileSections = Object.entries(filesByCategory);

  const totalLinks = categoryEntries.reduce((n, [, links]) => n + links.length, 0);
  const totalFiles = fileResources.length + uploads.length;
  const totalDocs = totalFiles + totalLinks;
  const isEmpty = !loading && !error && totalDocs === 0;
  const visibleCount =
    visibleFiles.length + visibleUploads.length + visibleLinkEntries.reduce((n, [, links]) => n + links.length, 0);
  const noMatches = !loading && !error && totalDocs > 0 && visibleCount === 0;

  return (
    <PageShell className="max-w-5xl" contentClassName="gap-8" noCard>
      <PageHero
        icon={FolderOpen}
        eyebrow="Resources"
        title="Everything your"
        accent="tutor cites."
        subtitle="Slides, readings, and code demos — indexed and searchable from the chat."
        actions={
          <div className="rounded-2xl border border-line bg-surface/80 px-5 py-4 shadow-sm backdrop-blur">
            <p className="text-[11px] font-semibold uppercase tracking-[0.25em] text-muted">
              Indexed
            </p>
            <p className="font-display text-2xl font-bold text-success">
              {totalDocs} docs
            </p>
            <p className="text-xs text-muted">· {totalFiles} files</p>
          </div>
        }
      />

      {error && (
        <p className="rounded-xl border border-danger/30 bg-danger-bg px-4 py-3 text-sm text-danger">
          {error}
        </p>
      )}

      {/* Search and type filter */}
      {!loading && totalDocs > 0 && (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className="relative min-w-0 flex-1">
            <span className="sr-only">Search resources</span>
            <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden="true" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by title, topic or file name"
              className="w-full rounded-xl border border-line bg-surface py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted outline-none transition focus:border-transparent focus:ring-2 focus:ring-success"
            />
          </label>
          <div role="group" aria-label="Resource type" className="flex shrink-0 gap-1 rounded-xl bg-surface-2 p-1">
            {KIND_FILTERS.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                aria-pressed={kind === id}
                onClick={() => setKind(id)}
                className={[
                  "rounded-lg px-3.5 py-1.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-success",
                  kind === id
                    ? "bg-surface text-foreground shadow-sm ring-1 ring-line"
                    : "text-muted hover:text-foreground",
                ].join(" ")}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {noMatches && (
        <div role="status" className="flex flex-col items-center gap-3 rounded-2xl border border-line bg-surface-2 p-10 text-center">
          <Search className="h-8 w-8 text-muted/40" aria-hidden="true" />
          <p className="text-sm text-muted">Nothing matches your search.</p>
          <button
            type="button"
            onClick={() => {
              setQuery("");
              setKind("all");
            }}
            className="text-sm font-semibold text-success hover:underline"
          >
            Clear filters
          </button>
        </div>
      )}

      {/* Loading state */}
      {loading && !error && (
        <div className="flex items-center justify-center py-20">
          <div className="flex flex-col items-center gap-4">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-primary" />
            <p className="text-sm text-muted">Loading resources…</p>
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
                    <p className="truncate font-semibold text-foreground">{res.title}</p>
                    {res.description && (
                      <p className="truncate text-xs text-muted">{res.description}</p>
                    )}
                  </div>
                  <span className="hidden flex-shrink-0 text-xs tabular-nums text-muted sm:block">
                    {formatBytes(res.file_size_bytes)}
                  </span>
                  <button
                    onClick={() => handleDownload(res.id)}
                    disabled={downloading === res.id}
                    aria-label={`Download ${res.title}`}
                    className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-line text-muted transition hover:bg-surface-2 hover:text-foreground disabled:opacity-50"
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
        visibleLinkEntries.map(([name, links]) => (
          <section key={name} className="animate-fade-in-up">
            <SectionHeader label={name} count={links.length} unit={links.length === 1 ? "link" : "links"} />
            <div className="space-y-3">
              {links.map((link) => (
                <a
                  key={link.url}
                  href={link.url}
                  target="_blank"
                  rel="noreferrer"
                  className={`group ${ROW_CARD} hover:border-success/30`}
                >
                  <span className="flex-shrink-0 rounded-md bg-success-bg px-2 py-1 text-[10px] font-bold tracking-wider text-success">
                    .LINK
                  </span>
                  <p className="min-w-0 flex-1 truncate font-semibold text-foreground transition group-hover:text-success">
                    {link.title}
                  </p>
                  <ExternalLink className="h-4 w-4 flex-shrink-0 text-muted" />
                </a>
              ))}
            </div>
          </section>
        ))}

      {/* Knowledge uploads */}
      {!loading && visibleUploads.length > 0 && (
        <section className="animate-fade-in-up">
          <SectionHeader label="Uploads" count={visibleUploads.length} unit={visibleUploads.length === 1 ? "file" : "files"} />
          <div className="space-y-3">
            {visibleUploads.map((upload) => (
              <div key={upload.id} className={ROW_CARD}>
                <FileBadge name={upload.file_name} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold text-foreground">{upload.file_name}</p>
                  <p className="truncate text-xs text-muted">
                    Uploaded {new Date(upload.uploaded_at).toLocaleDateString()}
                  </p>
                </div>
                <span className="hidden flex-shrink-0 text-xs tabular-nums text-muted sm:block">
                  {Math.round(upload.size_bytes / 1024)} KB
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Empty state */}
      {isEmpty && (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-line bg-surface-2 p-10 text-center">
          <FolderOpen className="h-10 w-10 text-muted/40" />
          <p className="text-sm text-muted">No curated resources available yet.</p>
        </div>
      )}

      {/* Suggestion CTA */}
      {!loading && (
        <section className="rounded-2xl border border-dashed border-line bg-surface-2 p-6 text-sm text-muted">
          <p>
            See something missing?{" "}
            <Link href="/feedback" className="font-semibold text-success hover:underline">
              Suggest a resource
            </Link>{" "}
            and we&apos;ll review it for the next release.
          </p>
        </section>
      )}
    </PageShell>
  );
}
