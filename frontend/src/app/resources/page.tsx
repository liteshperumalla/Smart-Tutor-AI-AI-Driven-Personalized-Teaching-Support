"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchResources, fetchResearchUploads, ResearchUpload } from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { PageShell } from "@/components/page-shell";
import { FolderOpen, ExternalLink, BookOpen } from "lucide-react";

type CategoryMap = Record<string, { title: string; url: string }[]>;

export default function ResourcesPage() {
  const { token } = useAuthToken();
  const [categories, setCategories] = useState<CategoryMap>({});
  const [error, setError] = useState<string | null>(null);
  const [uploads, setUploads] = useState<ResearchUpload[]>([]);

  useEffect(() => {
    if (!token) return;
    fetchResources(token)
      .then((data) => setCategories(data.categories || {}))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load resources"));

    fetchResearchUploads(token)
      .then((data) => setUploads(data))
      .catch(() => setUploads([]));
  }, [token]);

  const categoryEntries = Object.entries(categories);

  return (
    <PageShell className="max-w-5xl" contentClassName="gap-8">
      <header className="relative overflow-hidden rounded-3xl gradient-mesh p-12 animate-fade-in-down">
        <div className="absolute top-0 right-0 h-64 w-64 bg-emerald-400/20 rounded-full blur-3xl animate-float"></div>
        <div className="absolute bottom-0 left-0 h-48 w-48 bg-teal-400/20 rounded-full blur-3xl" style={{animationDelay: '1s'}}></div>

        <div className="relative z-10">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-white/80 px-4 py-2 text-sm font-medium text-emerald-700 backdrop-blur dark:border-emerald-800 dark:bg-zinc-900/80 dark:text-emerald-300 mb-4">
            <BookOpen className="h-4 w-4" />
            Resources
          </div>
          <h1 className="font-display text-5xl font-bold text-zinc-900 dark:text-white">
            Course library
          </h1>
          <p className="mt-4 text-lg text-zinc-600 max-w-2xl dark:text-zinc-400">
            Curated links for the INFO 5731 curriculum—Python references, NLP demos, and deployment how-tos
          </p>
        </div>
      </header>

      {error && <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400">{error}</p>}

      <section className="space-y-4">
        {categoryEntries.map(([name, links]) => (
          <article key={name} className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
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

        {categoryEntries.length === 0 && !error && (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading curated resources…</p>
        )}
      </section>

      <section className="rounded-2xl border border-dashed border-zinc-200 bg-zinc-50 p-6 text-sm text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-400">
        <p>
          See something missing?{" "}
          <Link href="/feedback" className="font-semibold text-blue-600 hover:underline dark:text-blue-400">
            Suggest a resource
          </Link>{" "}
          and we'll review it for the next release.
        </p>
      </section>

      {uploads.length > 0 && (
        <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">Knowledge uploads</h2>
            <Link href="/research" className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400">
              Add more sources
            </Link>
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
