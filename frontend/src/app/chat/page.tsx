"use client";

import { useCallback, useEffect, useMemo, useState, Suspense } from "react";
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
import { Plus, RotateCcw, MessageCircle, User, Bot, Send, Trash2 } from "lucide-react";

function ChatWorkspaceContent() {
  const searchParams = useSearchParams();
  const { token } = useAuthToken();
  const [sessions, setSessions] = useState<ChatSessionDTO[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [composerText, setComposerText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [viewerUrl, setViewerUrl] = useState<string | null>(null);
  const [viewerTitle, setViewerTitle] = useState<string | null>(null);

  const refreshSessions = useCallback(async () => {
    if (!token) {
      return;
    }
    try {
      const data = await listChatSessions(token);
      setSessions(data);
      if (data.length > 0) {
        const querySession = searchParams.get("session");
        const validSessions = data.filter((s): s is ChatSessionDTO => Boolean(s && typeof s === 'object' && 'id' in s));
        const matchFromQuery: ChatSessionDTO | undefined = querySession ? validSessions.find((s) => s.id === querySession) : undefined;
        const firstSession = validSessions[0];
        setSelectedSessionId((current) => current || matchFromQuery?.id || firstSession?.id || null);
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
          },
          credentials: "include", // Use HttpOnly cookies for authentication
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
      <header className="relative overflow-hidden rounded-3xl gradient-mesh p-12 animate-fade-in-down">
        <div className="absolute top-0 right-0 h-64 w-64 bg-indigo-400/20 rounded-full blur-3xl animate-float"></div>
        <div className="absolute bottom-0 left-0 h-48 w-48 bg-purple-400/20 rounded-full blur-3xl" style={{animationDelay: '1s'}}></div>

        <div className="relative z-10">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white/80 px-4 py-2 text-sm font-medium text-indigo-700 backdrop-blur dark:border-indigo-800 dark:bg-zinc-900/80 dark:text-indigo-300 mb-4">
            <div className="h-2 w-2 rounded-full bg-indigo-600 dark:bg-indigo-400"></div>
            Chat Workspace
          </div>
          <h1 className="font-display text-5xl font-bold text-zinc-900 dark:text-white">
            Course-aware assistant
          </h1>
          <p className="mt-4 text-lg text-zinc-600 max-w-2xl dark:text-zinc-400">
            Get instant help with course concepts, homework, and research questions
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleCreateSession}
              disabled={isCreatingSession}
              className="btn-primary disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:scale-100 flex items-center gap-2"
            >
              {isCreatingSession ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Creating…</>
              ) : (
                <><Plus className="h-4 w-4" /> Start new session <span className="transition-transform group-hover:translate-x-1">→</span></>
              )}
            </button>
            <button
              type="button"
              onClick={refreshSessions}
              className="btn-secondary flex items-center gap-2"
            >
              <RotateCcw className="h-4 w-4" /> Refresh
            </button>
          </div>
        </div>
      </header>

      <section className="flex flex-col rounded-3xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900 animate-fade-in-up">
        <div className="flex items-center justify-between border-b border-zinc-100 px-6 py-4 dark:border-zinc-800">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-zinc-500 dark:text-zinc-400">{sessionStatusLabel}</p>
            <h2 className="text-2xl font-semibold text-zinc-900 dark:text-white">
              {activeSession ? activeSession.title : "Create a new session"}
            </h2>
          </div>
          <span
            className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-medium ${
              isStreaming
                ? "badge-success"
                : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
            }`}
          >
            <span className={`h-2 w-2 rounded-full bg-current ${isStreaming ? 'animate-pulse' : ''}`} />
            {isStreaming ? "Streaming" : "Idle"}
          </span>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
          {streamError && (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/30">
              <div className="flex items-start gap-3">
                <svg className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm font-medium text-red-700 dark:text-red-400">Unable to get response</p>
                  <p className="text-sm text-red-600 dark:text-red-400/80 mt-1">{streamError}</p>
                  <button
                    type="button"
                    onClick={() => setStreamError(null)}
                    className="mt-2 text-sm font-medium text-red-700 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          )}
          {!activeSession && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="h-16 w-16 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center mb-4">
                <svg className="h-8 w-8 text-indigo-600 dark:text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-md">
                Start a new chat session to ask questions about course material, get homework help, or explore research topics.
              </p>
            </div>
          )}
          {activeSession && activeSession.messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="h-16 w-16 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-4">
                <svg className="h-8 w-8 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-md">
                Ask anything about INFO 5731 course material. I can explain concepts, help with assignments, or discuss research topics.
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                <button
                  type="button"
                  onClick={() => setComposerText("What is the main topic of this course?")}
                  className="text-xs px-3 py-1.5 rounded-full bg-zinc-100 text-zinc-700 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700 transition-colors"
                >
                  Course overview
                </button>
                <button
                  type="button"
                  onClick={() => setComposerText("Help me understand machine learning basics")}
                  className="text-xs px-3 py-1.5 rounded-full bg-zinc-100 text-zinc-700 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700 transition-colors"
                >
                  ML basics
                </button>
                <button
                  type="button"
                  onClick={() => setComposerText("How do I use the research mode?")}
                  className="text-xs px-3 py-1.5 rounded-full bg-zinc-100 text-zinc-700 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700 transition-colors"
                >
                  Research mode
                </button>
              </div>
            </div>
          )}
          {activeSession &&
            activeSession.messages.map((message, index) => (
              <ChatBubble 
                key={`${message.timestamp}-${index}`} 
                message={message} 
                token={token}
                onOpenViewer={(url, title) => {
                  setViewerUrl(url);
                  setViewerTitle(title);
                }}
              />
            ))}
        </div>

        <form onSubmit={handleSendMessage} className="border-t border-zinc-100 px-6 py-4 dark:border-zinc-800">
          <div className="rounded-2xl border-2 border-zinc-200 bg-zinc-50 p-4 focus-within:border-indigo-300 focus-within:ring-2 focus-within:ring-indigo-100 transition dark:border-zinc-700 dark:bg-zinc-800 dark:focus-within:border-indigo-600 dark:focus-within:ring-indigo-900/30">
            <textarea
              rows={3}
              placeholder={activeSession ? "Ask anything about INFO 5731…" : "Create a session to start chatting"}
              value={composerText}
              disabled={!activeSession || isStreaming}
              onChange={(event) => setComposerText(event.target.value)}
              className="w-full resize-none bg-transparent text-sm text-zinc-900 outline-none placeholder:text-zinc-400 dark:text-white dark:placeholder:text-zinc-500"
            />
            <div className="mt-3 flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
              <span className="flex items-center gap-1">
                <MessageCircle className="h-3.5 w-3.5" />
                {isStreaming ? "Waiting for the tutor…" : "Powered by AWS Bedrock"}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setComposerText("")}
                  className="btn-ghost text-xs flex items-center gap-1"
                  disabled={composerText.length === 0}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Clear
                </button>
                <button
                  type="submit"
                  disabled={!activeSession || composerText.trim().length === 0 || isStreaming}
                  className="rounded-full bg-gradient-to-r from-indigo-600 to-purple-600 px-4 py-2 font-semibold text-white shadow-md shadow-indigo-600/20 transition hover:scale-105 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:scale-100 flex items-center gap-1.5"
                >
                  {isStreaming ? (
                    <><span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Sending…</>
                  ) : (
                    <><Send className="h-3.5 w-3.5" /> Send</>
                  )}
                </button>
              </div>
            </div>
          </div>
        </form>
      </section>

      {/* File Viewer Modal */}
      <FileViewerModal
        url={viewerUrl}
        title={viewerTitle}
        onClose={() => {
          setViewerUrl(null);
          setViewerTitle(null);
        }}
      />
    </PageShell>
  );
}

function ChatBubble({ message, token, onOpenViewer }: { message: ChatMessageDTO; token?: string | null; onOpenViewer?: (url: string, title: string) => void }) {
  const isUser = message.role === "user";
  const formattedTime = message.timestamp
    ? new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} animate-fade-in-up`}>
      <div
        className={`max-w-xl rounded-2xl px-5 py-4 text-sm leading-relaxed shadow-md break-words ${
          isUser
            ? "bg-gradient-to-br from-indigo-600 to-purple-600 text-white shadow-indigo-600/20"
            : "border-2 border-zinc-200 bg-white text-zinc-900 shadow-zinc-200/50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:shadow-zinc-800/50"
        }`}
      >
          <div className="flex items-start gap-3">
            {isUser ? (
              <User className="h-5 w-5 mt-0.5 flex-shrink-0 opacity-80" />
            ) : (
              <Bot className="h-5 w-5 mt-0.5 flex-shrink-0 opacity-80" />
            )}
            <div className="flex-1">
              <p className="whitespace-pre-wrap break-words">{message.content || (isUser ? "" : "…")}</p>
            </div>
          </div>
          {message.sources && message.sources.length > 0 && (
          <div className="mt-4 space-y-2 rounded-xl bg-black/10 p-3 text-xs backdrop-blur dark:bg-white/5">
            <p className="font-semibold flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-current"></div>
              Sources
            </p>
            <ul className="space-y-2 pl-3">
              {message.sources.map((source, index) => {
                // Type guard helper
                const getString = (key: string): string | undefined => {
                  const val = source[key];
                  return typeof val === "string" ? val : undefined;
                };
                const getNumber = (key: string): number | undefined => {
                  const val = source[key];
                  return typeof val === "number" ? val : undefined;
                };

                const label =
                  getString("title") ||
                  getString("name") ||
                  getString("file_name") ||
                  getString("file_path") ||
                  "Reference";
                const locationParts = [
                  getNumber("page") ? `page ${getNumber("page")}` : null,
                  getNumber("slide") ? `slide ${getNumber("slide")}` : null,
                ].filter(Boolean);
                const location = locationParts.length ? `(${locationParts.join(", ")})` : "";
                const chunkText = getString("chunk_text");
                const snippet = chunkText
                  ? `"${chunkText.slice(0, 120)}${chunkText.length > 120 ? "…" : ""}"`
                  : "";
                const externalUrl = getString("external_url") || getString("url") || getString("link") || getString("source_link") || getString("web_url");
                
                const findUrlInSource = (source: Record<string, unknown>): string | undefined => {
                  for (const value of Object.values(source)) {
                    if (typeof value === "string" && (value.startsWith('http://') || value.startsWith('https://'))) {
                      return value;
                    }
                  }
                  return undefined;
                };
                
                const autoDetectedUrl = findUrlInSource(source);
                const effectiveExternalUrl = externalUrl || autoDetectedUrl;
                const sourceUrl = getString("source_url");
                const filePath = getString("file_path");
                const page = getNumber("page");
                const slide = getNumber("slide");
                
                const directUrl = sourceUrl || (filePath ? `${getApiBaseUrl()}/files/view?path=${encodeURIComponent(filePath)}${page ? `&page=${page}` : ""}${slide ? `&slide=${slide}` : ""}${token ? `&token=${encodeURIComponent(token)}` : ""}` : null);
                
                const getFilename = (path: string) => {
                  return path.split('/').pop() || path;
                };
                
                const getFileExt = (filename: string) => {
                  return filename.split('.').pop()?.toLowerCase() || '';
                };
                
                const getViewerType = (filename: string): 'pdf' | 'office' | 'notebook' | 'raw' | null => {
                  const ext = getFileExt(filename);
                  if (ext === 'pdf') return 'pdf';
                  if (['pptx', 'ppt', 'docx', 'doc'].includes(ext)) return 'office';
                  if (ext === 'ipynb') return 'notebook';
                  if (['txt', 'py', 'js', 'html', 'css', 'json', 'md'].includes(ext)) return 'raw';
                  return null;
                };
                
                const isExternalUrl = (url: string | undefined) => {
                  if (!url) return false;
                  return url.startsWith('http://') || url.startsWith('https://');
                };
                
                const handleSourceClick = async (e: React.MouseEvent) => {
                  e.preventDefault();
                  
                  const getFilename = (path: string) => {
                    return path.split('/').pop() || path;
                  };
                  
                  const getFileExt = (filename: string) => {
                    return filename.split('.').pop()?.toLowerCase() || '';
                  };
                  
                  const viewerType = (filename: string): 'pdf' | 'office' | 'notebook' | 'raw' | null => {
                    const ext = getFileExt(filename);
                    if (ext === 'pdf') return 'pdf';
                    if (['pptx', 'ppt', 'docx', 'doc'].includes(ext)) return 'office';
                    if (ext === 'ipynb') return 'notebook';
                    if (['txt', 'py', 'js', 'ts', 'jsx', 'tsx', 'java', 'c', 'cpp', 'h', 'hpp', 'cs', 'go', 'rs', 'rb', 'php', 'pl', 'lua', 'r', 'scala', 'kt', 'swift'].includes(ext)) return 'raw';
                    return null;
                  };
                  
                  const filename = getFilename(sourceUrl || filePath || '');
                  const type = viewerType(filename);
                  
                  // Check for external URL first (web search results)
                  if (isExternalUrl(effectiveExternalUrl)) {
                    window.open(effectiveExternalUrl, '_blank');
                    return;
                  }
                  
                  if (!directUrl) return;
                  
                  if (type === 'pdf') {
                    window.open(directUrl, '_blank');
                  } else if (type === 'office' || type === 'notebook') {
                    try {
                      const response = await fetch(`${getApiBaseUrl()}/files/s3-url?source_file=${encodeURIComponent(filename)}`);
                      if (response.ok) {
                        const data = await response.json();
                        if (onOpenViewer && data.url) {
                          onOpenViewer(data.url, label || filename);
                        }
                      } else if (onOpenViewer) {
                        onOpenViewer(directUrl, label || filename);
                      }
                    } catch (error) {
                      if (onOpenViewer) {
                        onOpenViewer(directUrl, label || filename);
                      }
                    }
                  } else {
                    window.open(directUrl, '_blank');
                  }
                };
                
                const hasClickableUrl = directUrl || isExternalUrl(effectiveExternalUrl);
                return (
                  <li key={index} className="opacity-80">
                    <div className="font-medium">
                      {hasClickableUrl ? (
                        <button
                          onClick={handleSourceClick}
                          className={`${isUser ? "text-blue-200 hover:underline" : "text-blue-600 hover:underline dark:text-blue-400"} cursor-pointer bg-none border-none p-0`}
                        >
                          {label}
                        </button>
                      ) : (
                        <span>{label}</span>
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

// File Viewer Modal Component
function FileViewerModal({ 
  url, 
  title, 
  onClose 
}: { 
  url: string | null; 
  title: string | null; 
  onClose: () => void;
}) {
  if (!url || !title) return null;
  
  const getFileExt = (filename: string) => {
    return filename.split('.').pop()?.toLowerCase() || '';
  };
  
  const ext = getFileExt(title);
  const isPDF = ext === 'pdf';
  const isOffice = ['pptx', 'ppt', 'docx', 'doc'].includes(ext);
  const isNotebook = ext === 'ipynb';
  const isImage = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'].includes(ext);
  const isVideo = ['mp4', 'webm', 'mov', 'avi', 'mkv'].includes(ext);
  const isAudio = ['mp3', 'wav', 'ogg', 'm4a', 'aac'].includes(ext);
  const isHTML = ext === 'html' || ext === 'htm';
  const isCode = ['py', 'js', 'ts', 'jsx', 'tsx', 'java', 'c', 'cpp', 'h', 'hpp', 'cs', 'go', 'rs', 'rb', 'php', 'pl', 'lua', 'r', 'scala', 'kt', 'swift'].includes(ext);
  const isText = ['txt', 'json', 'md', 'css', 'scss', 'yaml', 'yml', 'xml', 'csv', 'sh', 'bash', 'zsh', 'sql'].includes(ext);
  
  const displayUrl = url;
  
  const getGoogleDocsUrl = () => {
    return `https://docs.google.com/gview?embedded=1&url=${encodeURIComponent(displayUrl)}`;
  };
  
  const getColabUrl = () => {
    return `https://colab.research.google.com/notebook#create=true&url=${encodeURIComponent(displayUrl)}`;
  };
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-6xl h-[90vh] bg-white dark:bg-zinc-900 rounded-xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-white truncate">
            {title}
          </h3>
          <button
            onClick={onClose}
            className="p-2 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5 text-zinc-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        {/* Content area */}
        <div className="h-[calc(100%-120px)] w-full overflow-auto">
          {isPDF ? (
            // PDF - embed directly
            <iframe
              src={displayUrl}
              className="w-full h-full border-0"
              title={`PDF: ${title}`}
            />
          ) : isImage ? (
            // Images - display inline
            <div className="flex items-center justify-center h-full p-4">
              <img 
                src={displayUrl} 
                alt={title}
                className="max-w-full max-h-full object-contain rounded-lg shadow-lg"
              />
            </div>
          ) : isVideo ? (
            // Video - embed player
            <div className="flex items-center justify-center h-full p-4">
              <video 
                controls 
                className="max-w-full max-h-full rounded-lg shadow-lg"
                preload="metadata"
              >
                <source src={displayUrl} />
                Your browser does not support video playback.
              </video>
            </div>
          ) : isAudio ? (
            // Audio - embed player
            <div className="flex flex-col items-center justify-center h-full p-4">
              <div className="w-24 h-24 mb-6 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                <svg className="w-12 h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                </svg>
              </div>
              <audio controls className="w-full max-w-lg mt-4">
                <source src={displayUrl} />
                Your browser does not support audio playback.
              </audio>
              <a
                href={displayUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-4 text-sm text-blue-600 dark:text-blue-400 hover:underline"
              >
                Download audio file
              </a>
            </div>
          ) : isHTML ? (
            // HTML - embed directly
            <iframe
              src={displayUrl}
              className="w-full h-full border-0"
              title={`HTML: ${title}`}
              sandbox="allow-scripts"
            />
          ) : isCode ? (
            // Code files - show with download option
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
              <div className="w-20 h-20 mb-6 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
              </div>
              <h4 className="text-xl font-semibold text-zinc-900 dark:text-white mb-2">
                {title}
              </h4>
              <p className="text-zinc-600 dark:text-zinc-400 mb-6 max-w-md">
                Code file detected. Download to view in your editor or IDE.
              </p>
              <a
                href={displayUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
              >
                Download Code
              </a>
            </div>
          ) : isOffice ? (
            // Office files - show info card with multiple options
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
              <div className="w-20 h-20 mb-6 rounded-2xl bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h4 className="text-xl font-semibold text-zinc-900 dark:text-white mb-2">
                {title}
              </h4>
              <p className="text-zinc-600 dark:text-zinc-400 mb-6 max-w-md">
                Office documents require Microsoft Office or Google Docs to view. 
                Download the file and open it with your preferred application.
              </p>
              <div className="flex gap-4">
                <a
                  href={displayUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium flex items-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download & Open
                </a>
              </div>
              <p className="mt-6 text-sm text-zinc-500 dark:text-zinc-400 max-w-md">
                <strong>Tip:</strong> Right-click the download button and choose "Save link as..." to download the file, then open it with Microsoft Office, Google Docs, or any compatible viewer.
              </p>
            </div>
          ) : isNotebook ? (
            // Jupyter notebooks - show info card
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
              <div className="w-20 h-20 mb-6 rounded-2xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
              </div>
              <h4 className="text-xl font-semibold text-zinc-900 dark:text-white mb-2">
                {title}
              </h4>
              <p className="text-zinc-600 dark:text-zinc-400 mb-6 max-w-md">
                Jupyter notebook detected. Download the file to open in Jupyter Lab, 
                VS Code, or upload to Google Colab.
              </p>
              <div className="flex gap-4">
                <a
                  href={displayUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium flex items-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download & Open
                </a>
                <a
                  href={getColabUrl()}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-6 py-3 bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-white rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors font-medium"
                >
                  Open in Colab
                </a>
              </div>
                <p className="mt-6 text-sm text-zinc-500 dark:text-zinc-400 max-w-md">
                  <strong>Tip:</strong> For Colab, you may need to upload the downloaded .ipynb file manually.
                </p>
              </div>
            ) : isText ? (
            // Text files - show with open link
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
              <div className="w-20 h-20 mb-6 rounded-2xl bg-gradient-to-br from-zinc-500 to-zinc-700 flex items-center justify-center">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h4 className="text-xl font-semibold text-zinc-900 dark:text-white mb-2">
                {title}
              </h4>
              <a
                href={displayUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
              >
                Open File
              </a>
            </div>
          ) : (
            // Default - show download link
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
              <div className="w-20 h-20 mb-6 rounded-2xl bg-gradient-to-br from-zinc-400 to-zinc-600 flex items-center justify-center">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h4 className="text-xl font-semibold text-zinc-900 dark:text-white mb-2">
                {title}
              </h4>
              <a
                href={displayUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
              >
                Download File
              </a>
            </div>
          )}
        </div>
        
        {/* Footer */}
        <div className="absolute bottom-0 left-0 right-0 px-4 py-3 bg-zinc-50 dark:bg-zinc-800 border-t border-zinc-200 dark:border-zinc-700">
          <span className="text-xs text-zinc-500 dark:text-zinc-400">
            {isPDF ? 'PDF document' : 
             isImage ? 'Image file' : 
             isVideo ? 'Video file' : 
             isAudio ? 'Audio file' : 
             isHTML ? 'HTML document' : 
             isCode ? 'Code file' : 
             isOffice ? 'Office document' : 
             isNotebook ? 'Jupyter notebook' : 
             isText ? 'Text file' : 
             'File'} • Click the button above to view or download
          </span>
        </div>
      </div>
    </div>
  );
}

export default function ChatWorkspace() {
  return (
    <Suspense fallback={<ChatWorkspaceSkeleton />}>
      <ChatWorkspaceContent />
    </Suspense>
  );
}

function ChatWorkspaceSkeleton() {
  return (
    <PageShell className="max-w-5xl" contentClassName="gap-6">
      {/* Header skeleton */}
      <header className="relative overflow-hidden rounded-3xl gradient-mesh p-12">
        <div className="absolute top-0 right-0 h-64 w-64 bg-indigo-400/20 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-0 left-0 h-48 w-48 bg-purple-400/20 rounded-full blur-3xl" style={{animationDelay: '1s'}}></div>
        <div className="relative z-10 space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white/80 px-4 py-2 text-sm font-medium text-indigo-700 backdrop-blur dark:border-indigo-800 dark:bg-zinc-900/80 dark:text-indigo-300 mb-4">
            <div className="h-2 w-2 rounded-full bg-indigo-600 dark:bg-indigo-400 animate-pulse"></div>
            <div className="h-4 w-24 bg-indigo-200 dark:bg-indigo-800 rounded animate-pulse"></div>
          </div>
          <div className="h-10 w-64 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
          <div className="h-6 w-96 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
          <div className="flex gap-3 mt-8">
            <div className="h-10 w-32 bg-white/20 rounded-full animate-pulse"></div>
            <div className="h-10 w-24 border border-zinc-200 rounded-full animate-pulse"></div>
          </div>
        </div>
      </header>

      {/* Chat section skeleton */}
      <section className="flex flex-col rounded-3xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center justify-between border-b border-zinc-100 px-6 py-4 dark:border-zinc-800">
          <div className="space-y-2">
            <div className="h-3 w-32 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
            <div className="h-6 w-48 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
          </div>
          <div className="h-6 w-16 bg-zinc-100 dark:bg-zinc-800 rounded-full animate-pulse"></div>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
          {/* Chat bubble skeletons */}
          {[1, 2, 3].map((i) => (
            <div key={i} className={`flex ${i % 2 === 0 ? 'justify-end' : 'justify-start'} animate-pulse`}>
              <div className={`max-w-xl rounded-2xl px-5 py-4 ${
                i % 2 === 0
                  ? 'bg-gradient-to-br from-indigo-600 to-purple-600'
                  : 'border-2 border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-800'
              }`}>
                <div className="h-4 w-3/4 bg-white/20 rounded animate-pulse"></div>
                <div className="h-4 w-1/2 mt-2 bg-white/20 rounded animate-pulse"></div>
              </div>
            </div>
          ))}
        </div>

        <div className="border-t border-zinc-100 px-6 py-4 dark:border-zinc-800">
          <div className="rounded-2xl border-2 border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-700 dark:bg-zinc-800">
            <div className="h-20 w-full bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
            <div className="flex items-center justify-between mt-3">
              <div className="h-4 w-32 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
              <div className="h-8 w-20 bg-indigo-600 rounded-full animate-pulse"></div>
            </div>
          </div>
        </div>
      </section>
    </PageShell>
  );
}
