"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getSharedChatSession, ChatMessageDTO, ChatSessionDTO } from "@/lib/api";
import { PageShell } from "@/components/page-shell";
import { SkeletonRegion } from "@/components/skeleton";

type SharedSessionData = {
  session: ChatSessionDTO;
  expires_at: string;
};

function formatDate(dateStr?: string) {
  if (!dateStr) return "";
  try {
    return new Date(dateStr).toLocaleString([], {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export default function SharedChatPage() {
  const params = useParams();
  const shareId = params.shareId as string;
  const [data, setData] = useState<SharedSessionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!shareId) return;
    let mounted = true;
    getSharedChatSession(shareId)
      .then((result) => {
        if (!mounted) return;
        setData(result);
        setError(null);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Unable to load shared chat");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [shareId]);

  if (loading) {
    return (
      <PageShell className="max-w-4xl" contentClassName="gap-8">
        <SkeletonRegion label="Loading shared chat" className="contents">
        <header className="relative overflow-hidden rounded-3xl p-6 sm:p-8 lg:p-12">
          <div className="relative z-10 space-y-4">
            <div className="skeleton h-6 w-32"></div>
            <div className="skeleton h-10 w-64"></div>
            <div className="skeleton h-6 w-96 max-w-full"></div>
          </div>
        </header>
        <section className="flex flex-col rounded-3xl border border-line bg-surface shadow-sm">
          <div className="flex items-center justify-between border-b border-line px-6 py-4">
            <div className="skeleton h-6 w-48"></div>
          </div>
          <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className={`flex ${i % 2 === 0 ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-xl rounded-2xl px-5 py-4 ${i % 2 === 0 ? "gradient-primary" : "border-2 border-line bg-surface"}`}>
                  <div className={`h-4 w-3/4 rounded ${i % 2 === 0 ? "bg-white/25" : "skeleton"}`}></div>
                </div>
              </div>
            ))}
          </div>
        </section>
        </SkeletonRegion>
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell className="max-w-2xl" contentClassName="gap-8">
        <header className="relative overflow-hidden rounded-3xl gradient-mesh p-12">
          <div className="relative z-10">
            <h1 className="font-display text-2xl sm:text-4xl font-bold text-foreground">
              Shared Chat Unavailable
            </h1>
            <p className="mt-4 text-lg text-muted">{error}</p>
            <div className="mt-8">
              <Link href="/" className="btn-primary">
                Go to Home
              </Link>
            </div>
          </div>
        </header>
      </PageShell>
    );
  }

  if (!data) return null;

  const { session, expires_at } = data;
  const isExpired = new Date(expires_at) < new Date();

  return (
    <PageShell className="max-w-4xl" contentClassName="gap-8">
      <header className="relative overflow-hidden rounded-3xl p-6 sm:p-8 lg:p-12">
        <div className="absolute bottom-0 left-0 h-48 w-48 bg-lavender/20 rounded-full blur-3xl" style={{ animationDelay: "1s" }}></div>
        <div className="relative z-10">
          <h1 className="font-display text-2xl sm:text-4xl font-bold text-foreground">
            {session.title}
          </h1>
          <p className="mt-2 text-sm text-muted">
            {isExpired ? (
              <span className="text-danger">This shared link has expired</span>
            ) : (
              <>
                Shared on {formatDate(session.created_at)} · Expires {formatDate(expires_at)} ·{" "}
                {session.messages.length} messages
              </>
            )}
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Link href="/" className="btn-primary">
              Start Your Own Chat
            </Link>
            <Link href="/chat" className="btn-secondary">
              Go to Chat
            </Link>
          </div>
        </div>
      </header>

      <section className="flex flex-col rounded-3xl border border-line bg-surface shadow-sm">
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-muted">
              {session.messages.length === 0 ? "No messages" : "Conversation"}
            </p>
          </div>
          {!isExpired && (
            <span className="inline-flex items-center gap-2 rounded-full bg-success-bg px-3 py-1 text-xs font-medium text-success">
              <span className="h-2 w-2 rounded-full bg-success-solid"></span>
              Active
            </span>
          )}
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
          {session.messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="h-16 w-16 rounded-full bg-surface-2 flex items-center justify-center mb-4">
                <svg className="h-8 w-8 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <p className="text-sm text-muted max-w-md">
                This chat session has no messages yet.
              </p>
            </div>
          )}

          {session.messages.map((message, index) => {
            const isUser = message.role === "user";
            const formattedTime = message.timestamp
              ? new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
              : "";

            return (
              <div key={index} className={`flex ${isUser ? "justify-end" : "justify-start"} animate-fade-in-up`}>
                <div
                  className={`max-w-xl rounded-2xl px-5 py-4 text-sm leading-relaxed shadow-md break-words ${
                    isUser
                      ? "gradient-primary text-white shadow-brand"
                      : "border-2 border-line bg-surface text-foreground shadow-sm"
                  }`}
                >
                  <p className="whitespace-pre-wrap break-words">{message.content || (isUser ? "" : "…")}</p>
                  {formattedTime && (
                    <p className={`mt-2 text-xs ${isUser ? "text-white/70" : "text-muted"}`}>
                      {formattedTime}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="border-t border-line px-6 py-4">
          <p className="text-center text-xs text-muted">
            Shared via Smart AI Tutor ·{" "}
            <Link href="/" className="hover:text-foreground underline">
              Create your own chat sessions
            </Link>
          </p>
        </div>
      </section>
    </PageShell>
  );
}
