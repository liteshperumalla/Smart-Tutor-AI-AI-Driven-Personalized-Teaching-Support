"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ChatMessageDTO,
  ChatSessionDTO,
  createChatSession,
  getApiBaseUrl,
  listChatSessions,
} from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { CHAT_SESSIONS_UPDATED_EVENT, dispatchChatSessionsUpdated } from "@/lib/events";
import { PageShell } from "@/components/page-shell";

export default function ChatWorkspace() {
  const searchParams = useSearchParams();
  const { token } = useAuthToken();
  const [sessions, setSessions] = useState<ChatSessionDTO[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [composerText, setComposerText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [isCreatingSession, setIsCreatingSession] = useState(false);

  const refreshSessions = useCallback(async () => {
    if (!token) {
      return;
    }
    try {
      const data = await listChatSessions(token);
      setSessions(data);
      if (data.length > 0) {
        const querySession = searchParams.get("session");
        const matchFromQuery = querySession && data.find((s) => s.id === querySession);
        setSelectedSessionId((current) => current || matchFromQuery?.id || data[0].id);
      }
    } catch (error) {
      setStreamError(error instanceof Error ? error.message : "Unable to load sessions");
      setSessions([]);
    }
  }, [token, searchParams]);

  useEffect(() => {
    refreshSessions();
    function handleUpdate() {
      refreshSessions();
    }
    window.addEventListener(CHAT_SESSIONS_UPDATED_EVENT, handleUpdate);
    return () => {
      window.removeEventListener(CHAT_SESSIONS_UPDATED_EVENT, handleUpdate);
    };
  }, [refreshSessions]);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId) || null,
    [sessions, selectedSessionId]
  );
  const sessionStatusLabel = !activeSession
    ? "No session selected"
    : activeSession.messages.length === 0
    ? "Start a conversation"
    : "Current conversation";

  async function handleCreateSession() {
    if (!token) return;
    setIsCreatingSession(true);
    try {
      const next = await createChatSession({ token, title: undefined });
      setSessions((prev) => [next, ...prev.filter((s) => s.id !== next.id)]);
      setSelectedSessionId(next.id);
      dispatchChatSessionsUpdated();
    } catch (error) {
      setStreamError(error instanceof Error ? error.message : "Failed to create session");
    } finally {
      setIsCreatingSession(false);
    }
  }

  function updateActiveSessionMessages(updater: (messages: ChatMessageDTO[]) => ChatMessageDTO[]) {
    setSessions((prev) =>
      prev.map((session) =>
        session.id === selectedSessionId
          ? {
              ...session,
              messages: updater(session.messages || []),
              updated_at: new Date().toISOString(),
            }
          : session
      )
    );
  }

  async function handleSendMessage(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !selectedSessionId || !composerText.trim() || isStreaming) {
      return;
    }

    const content = composerText.trim();
    setComposerText("");
    setStreamError(null);

    const userMessage: ChatMessageDTO = {
      role: "user",
      content,
      timestamp: new Date().toISOString(),
    };

    const assistantMessage: ChatMessageDTO = {
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
    };

    updateActiveSessionMessages((messages) => [...messages, userMessage, assistantMessage]);
    setIsStreaming(true);

    try {
      const apiBaseUrl = getApiBaseUrl();
      const response = await fetch(
        `${apiBaseUrl}/chat/sessions/${selectedSessionId}/messages`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ query: content }),
        }
      );

      if (!response.ok || !response.body) {
        throw new Error("Chat endpoint unavailable");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantText = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        assistantText += decoder.decode(value, { stream: true });
        const latestText = assistantText;
        setSessions((prev) =>
          prev.map((session) =>
            session.id === selectedSessionId
              ? {
                  ...session,
                  messages: session.messages.map((message, index, arr) =>
                    index === arr.length - 1 ? { ...message, content: latestText } : message
                  ),
                }
              : session
          )
        );
      }

      await refreshSessions();
      dispatchChatSessionsUpdated();
    } catch (error) {
      const errMessage =
        error instanceof Error ? error.message : "Unable to stream a response";
      setStreamError(errMessage);
      setSessions((prev) =>
        prev.map((session) =>
          session.id === selectedSessionId
            ? {
                ...session,
                messages: session.messages.map((message, index, arr) =>
                  index === arr.length - 1
                    ? { ...message, content: `Error: ${errMessage}` }
                    : message
                ),
              }
            : session
        )
      );
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <PageShell className="max-w-5xl" contentClassName="gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-400">Chat Workspace</p>
          <h1 className="text-3xl font-semibold text-zinc-950 dark:text-white">Course-aware assistant</h1>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <button
            type="button"
            onClick={handleCreateSession}
            disabled={isCreatingSession}
            className="rounded-full bg-zinc-900 px-4 py-2 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-zinc-900"
          >
            {isCreatingSession ? "Creating…" : "Start new session"}
          </button>
          <button
            type="button"
            onClick={refreshSessions}
            className="rounded-full border border-zinc-200 px-4 py-2 font-semibold text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
          >
            Refresh
          </button>
          <Link href="/" className="font-semibold text-blue-600 dark:text-blue-400">
            ← Home
          </Link>
        </div>
      </header>

      <section className="flex flex-col rounded-3xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center justify-between border-b border-zinc-100 px-6 py-4 dark:border-zinc-800">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-zinc-500 dark:text-zinc-400">{sessionStatusLabel}</p>
            <h2 className="text-2xl font-semibold text-zinc-900 dark:text-white">
              {activeSession ? activeSession.title : "Create a new session"}
            </h2>
          </div>
          <span
            className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${
              isStreaming ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
            }`}
          >
            <span className="h-2 w-2 rounded-full bg-current" />
            {isStreaming ? "Streaming" : "Idle"}
          </span>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
          {streamError && (
            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400">
              {streamError}
            </div>
          )}
          {!activeSession && (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Use the button above or the "Recent chats" card in the sidebar to start a conversation.
            </p>
          )}
          {activeSession && activeSession.messages.length === 0 && (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">No messages yet. Say hello to get started.</p>
          )}
          {activeSession &&
            activeSession.messages.map((message, index) => (
              <ChatBubble key={`${message.timestamp}-${index}`} message={message} token={token} />
            ))}
        </div>

        <form onSubmit={handleSendMessage} className="border-t border-zinc-100 px-6 py-4 dark:border-zinc-800">
          <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-700 dark:bg-zinc-800">
            <textarea
              rows={3}
              placeholder={activeSession ? "Ask anything about INFO 5731…" : "Create a session to start chatting"}
              value={composerText}
              disabled={!activeSession || isStreaming}
              onChange={(event) => setComposerText(event.target.value)}
              className="w-full resize-none bg-transparent text-sm text-zinc-900 outline-none placeholder:text-zinc-400 dark:text-white dark:placeholder:text-zinc-500"
            />
            <div className="mt-3 flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
              <span>{isStreaming ? "Waiting for the tutor…" : "Powered by FastAPI"}</span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setComposerText("")}
                  className="rounded-full border border-zinc-200 px-3 py-1 text-zinc-700 dark:border-zinc-600 dark:text-zinc-300"
                  disabled={composerText.length === 0}
                >
                  Clear
                </button>
                <button
                  type="submit"
                  disabled={!activeSession || composerText.trim().length === 0 || isStreaming}
                  className="rounded-full bg-zinc-900 px-4 py-2 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-zinc-900"
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        </form>
      </section>
    </PageShell>
  );
}

function ChatBubble({ message, token }: { message: ChatMessageDTO; token?: string | null }) {
  const isUser = message.role === "user";
  const formattedTime = message.timestamp
    ? new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-xl rounded-2xl border px-4 py-3 text-sm leading-relaxed shadow-sm break-words ${
          isUser
            ? "border-blue-600 bg-blue-600 text-white dark:border-blue-500 dark:bg-blue-600"
            : "border-zinc-200 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        }`}
      >
        <p className="whitespace-pre-wrap break-words">{message.content || (isUser ? "" : "…")}</p>
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 space-y-1 text-xs">
            <p className="font-semibold">Sources</p>
            <ul className="list-disc space-y-2 pl-4">
              {message.sources.map((source, index) => {
                const label =
                  source["title"] ||
                  source["name"] ||
                  source["file_name"] ||
                  source["file_path"] ||
                  "Reference";
                const locationParts = [
                  source["page"] ? `page ${source["page"]}` : null,
                  source["slide"] ? `slide ${source["slide"]}` : null,
                ].filter(Boolean);
                const location = locationParts.length ? `(${locationParts.join(", ")})` : "";
                const snippet = source["chunk_text"]
                  ? `"${String(source["chunk_text"]).slice(0, 120)}${source["chunk_text"].length > 120 ? "…" : ""}"`
                  : "";
                const externalUrl =
                  typeof source["external_url"] === "string" && source["external_url"].length > 0
                    ? String(source["external_url"])
                    : undefined;
                const folderUrl = externalUrl
                  ? externalUrl
                  : source["file_path"]
                  ? `${getApiBaseUrl()}/files/view?path=${encodeURIComponent(source["file_path"])}${
                      source["page"] ? `&page=${source["page"]}` : ""
                    }${source["slide"] ? `&slide=${source["slide"]}` : ""}${
                      token ? `&token=${encodeURIComponent(token)}` : ""
                    }`
                  : undefined;
                return (
                  <li key={index} className="opacity-80">
                    <div className="font-medium">
                      {folderUrl ? (
                        <a
                          href={folderUrl}
                          target="_blank"
                          rel="noreferrer"
                          className={isUser ? "text-blue-200 hover:underline" : "text-blue-600 hover:underline dark:text-blue-400"}
                        >
                          {label}
                        </a>
                      ) : (
                        label
                      )}{" "}
                      {location}
                    </div>
                    {snippet && <div className={`text-[11px] ${isUser ? "text-white/70" : "text-zinc-500 dark:text-zinc-400"}`}>{snippet}</div>}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
        {formattedTime && (
          <p className={`mt-2 text-xs ${isUser ? "text-white/70" : "text-zinc-500 dark:text-zinc-400"}`}>{formattedTime}</p>
        )}
      </div>
    </div>
  );
}
