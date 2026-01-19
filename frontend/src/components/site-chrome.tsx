"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthToken } from "@/hooks/useAuthToken";
import { useTheme } from "@/context/theme-context";
import {
  listChatSessions,
  ChatSessionDTO,
  renameChatSession,
  deleteChatSession,
  fetchChatSession,
  shareChatSession,
} from "@/lib/api";
import { dispatchChatSessionsUpdated } from "@/lib/events";
import { CHAT_SESSIONS_UPDATED_EVENT } from "@/lib/events";
import {
  Home,
  MessageCircle,
  Brain,
  FileSearch,
  BarChart3,
  Calendar,
  FolderOpen,
  Info,
  MessageSquare,
  User,
  LogIn,
  LogOut,
  Sun,
  Moon,
  Clock,
  Plus,
} from "lucide-react";

type NavLink = { href: string; label: string; icon?: React.ComponentType<{ className?: string }> };

const navIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  "/": Home,
  "/chat": MessageCircle,
  "/quiz": Brain,
  "/research": FileSearch,
  "/evaluation": BarChart3,
  "/appointments": Calendar,
  "/resources": FolderOpen,
  "/about": Info,
  "/feedback": MessageSquare,
  "/profile": User,
};

export function SiteChrome({
  navLinks,
  children,
}: {
  navLinks: NavLink[];
  children: React.ReactNode;
}) {
  const { token, setToken } = useAuthToken({ redirectTo: undefined });
  const { theme, setTheme, hasHydrated: themeHasHydrated } = useTheme();
  const [hasHydrated, setHasHydrated] = useState(false);
  const [recentSessions, setRecentSessions] = useState<ChatSessionDTO[]>([]);
  const [menuSessionId, setMenuSessionId] = useState<string | null>(null);
  const [shareStatus, setShareStatus] = useState<{ sharing: boolean; message: string | null }>({ sharing: false, message: null });
  const menuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const year = new Date().getFullYear();

  useEffect(() => {
    setHasHydrated(true);
  }, []);

  const loadSessions = useCallback(async () => {
    if (!token) {
      setRecentSessions([]);
      return;
    }
    try {
      const sessions = await listChatSessions(token);
      setRecentSessions(sessions);
    } catch {
      setRecentSessions([]);
    }
  }, [token]);

  useEffect(() => {
    let cancelled = false;
    const frame = requestAnimationFrame(async () => {
      if (!cancelled) {
        await loadSessions();
      }
    });
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
    };
  }, [loadSessions]);

  // Listen for sessions updated events from chat page
  useEffect(() => {
    function handleSessionsUpdated() {
      loadSessions();
    }
    window.addEventListener(CHAT_SESSIONS_UPDATED_EVENT, handleSessionsUpdated);
    return () => {
      window.removeEventListener(CHAT_SESSIONS_UPDATED_EVENT, handleSessionsUpdated);
    };
  }, [loadSessions]);

  useEffect(() => {
    if (!menuSessionId) return;
    function handleClick(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuSessionId(null);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => {
      document.removeEventListener("mousedown", handleClick);
    };
  }, [menuSessionId]);

  // IMPORTANT: token will be "authenticated" string when logged in (not null/undefined)
  const isLoggedIn = hasHydrated && token === "authenticated";
  // IMPORTANT: Wait for theme to hydrate before determining dark mode to avoid wrong button text
  const isDark = themeHasHydrated && theme === "dark";
  const showThemeToggle = themeHasHydrated;

  const sessionMenuPanelClass = [
    "absolute right-0 top-full z-50 mt-1 w-48 rounded-xl border p-1.5 shadow-lg backdrop-blur animate-fade-in",
    isDark
      ? "border-white/10 bg-zinc-900/95 text-zinc-100"
      : "border-zinc-200/80 bg-white/95 text-zinc-900",
  ].join(" ");

  const sessionMenuItemClass = [
    "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition",
    isDark ? "text-white hover:bg-white/10" : "text-zinc-700 hover:bg-zinc-100",
  ].join(" ");

  const sessionMenuIconClass = [
    "h-4 w-4 flex-shrink-0",
    isDark ? "text-zinc-400" : "text-zinc-500",
  ].join(" ");

  const sessionMenuDeleteClass = [
    "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition",
    isDark ? "text-red-300 hover:bg-red-500/10" : "text-red-600 hover:bg-red-50",
  ].join(" ");

  const sessionMenuDeleteIconClass = "h-4 w-4 flex-shrink-0";

  const handleAuthClick = () => {
    if (!hasHydrated) return;
    if (token) {
      setToken(null);
      router.replace("/login");
    } else {
      router.push("/login");
    }
  };

  const handleToggleTheme = () => {
    setTheme(isDark ? "light" : "dark");
  };

  const handleRenameSession = async (session: ChatSessionDTO) => {
    if (!token) return;
    const nextTitle = window.prompt("Rename chat", session.title || "Session");
    if (!nextTitle || !nextTitle.trim()) return;
    try {
      await renameChatSession(token, session.id, nextTitle.trim());
      await loadSessions();
      dispatchChatSessionsUpdated();
      setMenuSessionId(null);
    } catch (error) {
      console.error(error);
    }
  };

  const handleDeleteSession = async (session: ChatSessionDTO) => {
    if (!token) return;
    if (!window.confirm(`Delete chat "${session.title || session.id}"?`)) return;
    try {
      await deleteChatSession(token, session.id);
      setMenuSessionId(null);
      await loadSessions();
      dispatchChatSessionsUpdated();
    } catch (error) {
      console.error(error);
    }
  };

  const handleShareSession = async (session: ChatSessionDTO) => {
    if (!token) return;
    setShareStatus({ sharing: true, message: null });
    try {
      const data = await shareChatSession(token, session.id, 7);
      const shareUrl = `${window.location.origin}${data.share_url}`;
      
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(shareUrl);
        setShareStatus({ sharing: false, message: "Copied!" });
      } else {
        setShareStatus({ sharing: false, message: "Exported" });
      }
      
      setTimeout(() => setShareStatus({ sharing: false, message: null }), 2000);
      setMenuSessionId(null);
    } catch (error) {
      console.error("Share failed:", error);
      setShareStatus({ sharing: false, message: null });
    }
  };

  const handleSelectSession = (sessionId: string) => {
    router.push(`/chat?session=${sessionId}`);
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Fixed Sidebar */}
      <aside className="hidden w-64 flex-shrink-0 flex-col border-r border-zinc-200 bg-white/90 backdrop-blur transition dark:border-zinc-800 dark:bg-zinc-900/80 lg:flex fixed left-0 top-0 bottom-0 z-30">
        <div className="px-6 py-6">
          <Link href="/" className="text-lg font-semibold text-zinc-900 dark:text-white">
            Smart AI Tutor
          </Link>
          <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">AI-first course companion</p>
        </div>
        <nav className="flex-1 px-4 flex flex-col min-h-0 overflow-visible">
          {isLoggedIn && (
            <div className="mt-6 flex flex-col rounded-2xl border border-zinc-200 bg-white/70 p-4 text-sm dark:border-zinc-800 dark:bg-zinc-900/60 flex-1 min-h-0">
              <div className="flex items-center justify-between flex-shrink-0">
                <p className="text-xs uppercase tracking-[0.3em] text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5" />
                  Recent chats
                </p>
                <Link
                  href="/chat"
                  className="p-1 rounded-lg text-zinc-400 hover:text-zinc-900 hover:bg-zinc-100 dark:text-zinc-500 dark:hover:text-white dark:hover:bg-white/10 transition"
                  title="New chat"
                >
                  <Plus className="h-4 w-4" />
                </Link>
              </div>
              {recentSessions.length === 0 && (
                <p className="mt-2 text-xs text-zinc-500">No sessions yet.</p>
              )}
              <ul className="mt-3 flex-1 space-y-3 overflow-y-auto overflow-x-visible pr-1 min-h-0">
                {recentSessions.map((session) => (
                <li key={session.id}>
                  <div className="flex items-center gap-2 rounded-2xl border border-zinc-200 bg-white/95 px-3 py-2 text-sm shadow-sm transition hover:-translate-y-0.5 dark:border-zinc-800 dark:bg-zinc-900/60">
                    <button
                      type="button"
                      onClick={() => handleSelectSession(session.id)}
                      className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap border-none bg-transparent text-left font-semibold text-zinc-800 outline-none focus-visible:ring-2 focus-visible:ring-zinc-900 dark:text-zinc-100"
                    >
                      {session.title || `Session ${session.id.slice(0, 6)}`}
                    </button>
                    <div className="relative" ref={menuRef}>
                      <button
                        type="button"
                        onClick={() => setMenuSessionId((current) => (current === session.id ? null : session.id))}
                        className={[
                          "flex items-center justify-center rounded-lg p-1.5 transition",
                          isDark
                            ? "text-zinc-400 hover:bg-white/10 hover:text-white"
                            : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700",
                        ].join(" ")}
                        aria-label={`Menu for chat ${session.title || session.id}`}
                      >
                        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                        </svg>
                      </button>
                      {menuSessionId === session.id && (
                        <div className={sessionMenuPanelClass}>
                          <button
                            type="button"
                            onClick={() => handleRenameSession(session)}
                            className={sessionMenuItemClass}
                            aria-label={`Rename chat ${session.title || session.id}`}
                          >
                            <svg className={sessionMenuIconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                            <span>Rename</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => handleShareSession(session)}
                            disabled={shareStatus.sharing}
                            className={sessionMenuItemClass}
                            aria-label={`Download chat ${session.title || session.id}`}
                          >
                            <svg className={sessionMenuIconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                            </svg>
                            <span>{shareStatus.message || "Export"}</span>
                          </button>
                          <div className={["my-1 border-t", isDark ? "border-white/10" : "border-zinc-200"].join(" ")}></div>
                          <button
                            type="button"
                            onClick={() => handleDeleteSession(session)}
                            className={sessionMenuDeleteClass}
                            aria-label={`Delete chat ${session.title || session.id}`}
                          >
                            <svg className={sessionMenuDeleteIconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                            <span>Delete</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
            </div>
          )}
        </nav>

        <div className="border-t border-zinc-200 px-6 pb-3 pt-5 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
          <p>
            Need help?{" "}
            <a href="mailto:support@smartaitutor.com" className="font-semibold text-zinc-900 dark:text-white">
              support@smartaitutor.com
            </a>
          </p>
          <button
            type="button"
            onClick={handleToggleTheme}
            disabled={!showThemeToggle}
            className="mt-3 w-full rounded-full border border-zinc-200 px-4 py-2 text-sm font-semibold text-zinc-900 transition hover:bg-zinc-900 hover:text-white dark:border-zinc-700 dark:text-white dark:hover:bg-white dark:hover:text-zinc-900 disabled:opacity-50 disabled:cursor-wait flex items-center justify-center gap-2"
          >
            {!showThemeToggle ? (
              <span className="flex items-center justify-center gap-2">
                <span className="h-3 w-3 animate-spin rounded-full border border-zinc-400 border-t-transparent"></span>
              </span>
            ) : isDark ? (
              <>
                <Sun className="h-4 w-4" />
                <span>Switch to Light</span>
              </>
            ) : (
              <>
                <Moon className="h-4 w-4" />
                <span>Switch to Dark</span>
              </>
            )}
          </button>
          <button
            type="button"
            onClick={handleAuthClick}
            className="mt-2 w-full rounded-full border border-zinc-200 px-4 py-2 text-sm font-semibold text-zinc-900 transition hover:bg-zinc-900 hover:text-white dark:border-zinc-700 dark:text-white dark:hover:bg-white dark:hover:text-zinc-900 flex items-center justify-center gap-2"
          >
            {isLoggedIn ? (
              <>
                <LogOut className="h-4 w-4" />
                <span>Sign out</span>
              </>
            ) : (
              <>
                <LogIn className="h-4 w-4" />
                <span>Sign in</span>
              </>
            )}
          </button>
          <p className="mt-4 text-center text-[10px] uppercase tracking-[0.35em] text-zinc-400 dark:text-zinc-500">
            © {year} Smart AI Tutor
          </p>
        </div>
      </aside>

      {/* Main content area with fixed footer */}
      <div className="flex flex-1 flex-col bg-zinc-50 text-zinc-900 transition dark:bg-zinc-950 dark:text-white lg:ml-64">
        {/* Scrollable content area */}
        <main className="flex-1 overflow-y-auto px-4 py-5 pb-20 sm:px-8">{children}</main>

        {/* Fixed Footer Nav */}
        <footer className="fixed bottom-0 left-0 right-0 lg:left-64 border-t border-zinc-200 bg-white/95 backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/95 z-20">
          <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-4 text-sm text-zinc-600 dark:text-zinc-400 sm:flex-row sm:items-center sm:justify-center">
            <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-xs uppercase tracking-[0.2em]">
              {navLinks.map((link) => {
                const Icon = navIcons[link.href] || FolderOpen;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className="flex items-center gap-1.5 hover:text-zinc-900 dark:hover:text-white transition"
                  >
                    <Icon className="h-3.5 w-3.5" />
                    <span>{link.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
