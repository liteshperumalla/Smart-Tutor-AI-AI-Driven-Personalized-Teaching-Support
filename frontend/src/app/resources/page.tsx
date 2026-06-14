"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchResources, fetchResearchUploads, getResourceDownloadUrl, ResearchUpload, Resource } from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { PageShell } from "@/components/page-shell";
import { PageHero } from "@/components/page-hero";
import { FolderOpen, ExternalLink, FileText, Download } from "lucide-react";

type CategoryMap = Record<string, { title: string; url: string }[]>;

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

  return (
    <PageShell className="max-w-5xl" contentClassName="gap-8" noCard>
      <PageHero
        icon={FolderOpen}
        title="Resource"
        accent="Hub"
        subtitle="Lecture slides, Canvas links, readings, and uploaded files — curated for INFO 5731 in one place."
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

      {/* Link Resources by Category */}
      {!loading && (
        <section className="space-y-4">
          {categoryEntries.map(([name, links]) => (
            <article key={name} className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm transition hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900">
              <h2 className="flex items-center gap-3 text-xl font-semibold text-zinc-900 dark:text-white">
                <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                  </svg>
                </span>
                {name}
              </h2>
              <ul className="mt-4 space-y-3 text-sm">
                {links.map((link) => (
                  <li key={link.url} className="flex items-start gap-3">
                    <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                      </svg>
                    </span>
                    <a href={link.url} target="_blank" rel="noreferrer" className="font-medium text-blue-600 hover:underline dark:text-blue-400">
                      {link.title}
                    </a>
                  </li>
                ))}
              </ul>
            </article>
          ))}

          {categoryEntries.length === 0 && !error && !loading && (
            <div className="flex flex-col items-center gap-3 rounded-2xl border border-zinc-200 bg-zinc-50 p-8 text-center dark:border-zinc-800 dark:bg-zinc-900/30">
              <FolderOpen className="h-10 w-10 text-zinc-300 dark:text-zinc-600" />
              <p className="text-sm text-zinc-500 dark:text-zinc-400">No curated resources available yet.</p>
            </div>
          )}
        </section>
      )}

      {/* Course Materials (file downloads) */}
      {!loading && fileResources.length > 0 && (
        <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="flex items-center gap-3 text-xl font-semibold text-zinc-900 dark:text-white">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400">
              <FileText className="h-5 w-5" />
            </span>
            Course Materials
          </h2>
          <div className="mt-4 space-y-3">
            {fileResources.map((res) => (
              <div
                key={res.id}
                className="flex items-center justify-between rounded-xl border border-zinc-100 bg-zinc-50 p-4 transition hover:shadow-md dark:border-zinc-800 dark:bg-zinc-800/50"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-zinc-900 dark:text-white">{res.title}</p>
                  {res.description && (
                    <p className="mt-0.5 text-xs text-zinc-600 dark:text-zinc-400">{res.description}</p>
                  )}
                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                    {res.file_name} · {formatBytes(res.file_size_bytes)} · {res.category}
                  </p>
                </div>
                <button
                  onClick={() => handleDownload(res.id)}
                  disabled={downloading === res.id}
                  className="ml-4 flex items-center gap-2 rounded-lg bg-purple-100 px-3 py-2 text-xs font-medium text-purple-700 transition hover:bg-purple-200 disabled:opacity-50 dark:bg-purple-900/30 dark:text-purple-400 dark:hover:bg-purple-900/50"
                >
                  <Download className="h-3.5 w-3.5" />
                  {downloading === res.id ? "…" : "Download"}
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Suggestion CTA */}
      {!loading && (
        <section className="rounded-2xl border border-dashed border-zinc-200 bg-zinc-50 p-6 text-sm text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-400">
          <p>
            See something missing?{" "}
            <Link href="/feedback" className="font-semibold text-blue-600 hover:underline dark:text-blue-400">
              Suggest a resource
            </Link>{" "}
            and we&apos;ll review it for the next release.
          </p>
        </section>
      )}

      {/* Knowledge Uploads */}
      {uploads.length > 0 && (
        <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">Knowledge uploads</h2>
          </div>
          <div className="mt-4 space-y-3 max-h-[360px] overflow-auto pr-1 text-sm">
            {uploads.map((upload) => (
              <div key={upload.id} className="rounded-xl border border-zinc-100 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-800/50">
                <p className="font-semibold text-zinc-900 dark:text-white">{upload.file_name}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Stored at {upload.path}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  {Math.round(upload.size_bytes / 1024)} KB · Uploaded {new Date(upload.uploaded_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </PageShell>
  );
}
