"use client";

import { useEffect, useCallback } from "react";
import { X, ExternalLink, FileText, Globe } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api";

interface Source {
  title?: string;
  name?: string;
  file_name?: string;
  file_path?: string;
  chunk_text?: string;
  page?: number;
  slide?: number;
  external_url?: string;
  url?: string;
  link?: string;
  source_link?: string;
  web_url?: string;
  source_url?: string;
  [key: string]: unknown;
}

interface SourcesSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  sources: Source[];
  token?: string | null;
  onOpenViewer?: (url: string, title: string) => void;
}

export function SourcesSidebar({
  isOpen,
  onClose,
  sources,
  token,
  onOpenViewer,
}: SourcesSidebarProps) {
  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  // Prevent body scroll when sidebar is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  const handleSourceClick = useCallback(
    async (source: Source) => {
      const getString = (key: string): string | undefined => {
        const val = source[key];
        return typeof val === "string" ? val : undefined;
      };
      const getNumber = (key: string): number | undefined => {
        const val = source[key];
        return typeof val === "number" ? val : undefined;
      };

      const externalUrl =
        getString("external_url") ||
        getString("url") ||
        getString("link") ||
        getString("source_link") ||
        getString("web_url");

      // Auto-detect URL in source
      const findUrlInSource = (src: Source): string | undefined => {
        for (const value of Object.values(src)) {
          if (
            typeof value === "string" &&
            (value.startsWith("http://") || value.startsWith("https://"))
          ) {
            return value;
          }
        }
        return undefined;
      };

      const autoDetectedUrl = findUrlInSource(source);
      const effectiveExternalUrl = externalUrl || autoDetectedUrl;

      // Check for external URL first (web search results)
      if (effectiveExternalUrl) {
        window.open(effectiveExternalUrl, "_blank");
        return;
      }

      const sourceUrl = getString("source_url");
      const filePath = getString("file_path");
      const page = getNumber("page");
      const slide = getNumber("slide");

      const directUrl =
        sourceUrl ||
        (filePath
          ? `${getApiBaseUrl()}/files/view?path=${encodeURIComponent(filePath)}${
              page ? `&page=${page}` : ""
            }${slide ? `&slide=${slide}` : ""}`
          : null);

      if (!directUrl) return;

      const getFilename = (path: string) => path.split("/").pop() || path;
      const getFileExt = (filename: string) =>
        filename.split(".").pop()?.toLowerCase() || "";

      const filename = getFilename(sourceUrl || filePath || "");
      const ext = getFileExt(filename);

      const label =
        getString("title") ||
        getString("name") ||
        getString("file_name") ||
        getString("file_path") ||
        "Reference";

      if (ext === "pdf") {
        window.open(directUrl, "_blank");
      } else if (["pptx", "ppt", "docx", "doc", "ipynb"].includes(ext)) {
        try {
          const response = await fetch(
            `${getApiBaseUrl()}/files/s3-url?source_file=${encodeURIComponent(filename)}`
          );
          if (response.ok) {
            const data = await response.json();
            if (onOpenViewer && data.url) {
              onOpenViewer(data.url, label || filename);
            }
          } else if (onOpenViewer) {
            onOpenViewer(directUrl, label || filename);
          }
        } catch {
          if (onOpenViewer) {
            onOpenViewer(directUrl, label || filename);
          }
        }
      } else {
        window.open(directUrl, "_blank");
      }
    },
    [token, onOpenViewer]
  );

  const getSourceLabel = (source: Source): string => {
    return (
      (source.title as string) ||
      (source.name as string) ||
      (source.file_name as string) ||
      (source.file_path as string) ||
      "Reference"
    );
  };

  const getSourceLocation = (source: Source): string => {
    const parts: string[] = [];
    if (typeof source.page === "number") {
      parts.push(`Page ${source.page}`);
    }
    if (typeof source.slide === "number") {
      parts.push(`Slide ${source.slide}`);
    }
    return parts.join(", ");
  };

  const getSourceSnippet = (source: Source): string | null => {
    const chunkText = source.chunk_text;
    if (typeof chunkText !== "string") return null;
    if (chunkText.length > 150) {
      return chunkText.slice(0, 150) + "...";
    }
    return chunkText;
  };

  const isExternalSource = (source: Source): boolean => {
    return !!(
      source.external_url ||
      source.url ||
      source.link ||
      source.source_link ||
      source.web_url
    );
  };

  const getExternalUrl = (source: Source): string | null => {
    const url =
      (typeof source.external_url === "string" ? source.external_url : null) ||
      (typeof source.url === "string" ? source.url : null) ||
      (typeof source.link === "string" ? source.link : null) ||
      (typeof source.source_link === "string" ? source.source_link : null) ||
      (typeof source.web_url === "string" ? source.web_url : null);
    return url || null;
  };

  const getDomain = (url: string): string => {
    try {
      return new URL(url).hostname.replace(/^www\./, "");
    } catch {
      return url;
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className={`
          fixed inset-0 bg-black/40 z-40
          transition-opacity duration-300
          ${isOpen ? "opacity-100" : "opacity-0 pointer-events-none"}
        `}
        onClick={onClose}
      />

      {/* Sidebar */}
      <div
        className={`
          fixed right-0 top-0 bottom-0 z-50 w-96 max-w-[90vw]
          bg-white dark:bg-zinc-900
          shadow-2xl border-l border-zinc-200 dark:border-zinc-700
          transform transition-transform duration-300 ease-in-out
          ${isOpen ? "translate-x-0" : "translate-x-full"}
          flex flex-col
        `}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 dark:border-zinc-700">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-900/30">
              <FileText className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-zinc-900 dark:text-white">
                Sources
              </h2>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                {sources.length} reference{sources.length !== 1 ? "s" : ""}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <X className="h-5 w-5 text-zinc-500" />
          </button>
        </div>

        {/* Sources List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {sources.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 dark:text-zinc-400">
              <FileText className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p>No sources available</p>
            </div>
          ) : (
            sources.map((source, index) => {
              const label = getSourceLabel(source);
              const location = getSourceLocation(source);
              const snippet = getSourceSnippet(source);
              const isExternal = isExternalSource(source);
              const externalUrl = isExternal ? getExternalUrl(source) : null;

              return (
                <button
                  key={index}
                  onClick={() => handleSourceClick(source)}
                  className="w-full text-left p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 hover:bg-zinc-100 dark:hover:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 transition-all duration-200 group"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      {isExternal ? (
                        <Globe className="h-4 w-4 text-blue-500 flex-shrink-0" />
                      ) : (
                        <FileText className="h-4 w-4 text-zinc-400 flex-shrink-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <span className="block font-medium text-zinc-900 dark:text-white truncate">
                          {label}
                        </span>
                        {externalUrl && (
                          <span className="block text-xs text-blue-500 dark:text-blue-400 truncate">
                            {getDomain(externalUrl)}
                          </span>
                        )}
                      </div>
                      {location && (
                        <span className="text-xs text-zinc-500 dark:text-zinc-400 flex-shrink-0">
                          • {location}
                        </span>
                      )}
                    </div>
                    <ExternalLink className="h-4 w-4 text-zinc-400 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                  {snippet && (
                    <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400 line-clamp-2">{snippet}</p>
                  )}
                </button>
              );
            })
          )}
        </div>
      </div>
    </>
  );
}
