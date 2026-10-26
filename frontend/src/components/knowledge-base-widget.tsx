"use client";

import Link from "next/link";
import { Upload } from "lucide-react";
import { useUser } from "@/hooks/useUser";

interface KnowledgeBaseStats {
  ready?: boolean;
  document_count?: number;
  source_count?: number;
  last_updated_display?: string | null;
}

interface KnowledgeBaseWidgetProps {
  knowledge_base?: KnowledgeBaseStats;
  vector_store_ready?: boolean;
}

/**
 * Renders the Knowledge Base status card.
 * Visible only to users with the Admin role — returns null for regular users.
 */
export function KnowledgeBaseWidget({
  knowledge_base,
  vector_store_ready,
}: KnowledgeBaseWidgetProps) {
  const { isAdmin, isLoading } = useUser();

  // Hide entirely from non-admins (and while loading to avoid flash)
  if (isLoading || !isAdmin) return null;

  return (
    <article className="rounded-3xl border border-line bg-surface p-6 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs uppercase tracking-[0.35em] text-muted">
          Knowledge Base
        </p>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
            knowledge_base?.ready
              ? "bg-success-bg text-success"
              : "bg-warning-bg text-warning"
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              knowledge_base?.ready ? "bg-success animate-pulse" : "bg-warning"
            }`}
          />
          {knowledge_base?.ready ? "Active" : "Loading"}
        </span>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-muted">Source files</span>
          <span className="font-medium text-foreground">
            {knowledge_base?.source_count?.toLocaleString() ?? 0}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted">Vector chunks</span>
          <span className="font-medium text-foreground">
            {knowledge_base?.document_count?.toLocaleString() ?? 0}
          </span>
        </div>
        {knowledge_base?.last_updated_display && (
          <div className="flex justify-between">
            <span className="text-muted">Last updated</span>
            <span className="font-medium text-foreground text-xs">
              {knowledge_base.last_updated_display}
            </span>
          </div>
        )}
      </div>

      <div className="mt-4 pt-4 border-t border-line">
        <Link
          href="/admin/resources"
          className="text-sm text-primary hover:text-primary font-medium flex items-center gap-1"
        >
          <Upload className="h-4 w-4" />
          Upload sources →
        </Link>
      </div>
    </article>
  );
}
