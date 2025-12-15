"use client";

import { useCallback, useEffect, useState } from "react";
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
} from "@/lib/api";
import { dispatchChatSessionsUpdated } from "@/lib/events";

type NavLink = { href: string; label: string };

export function SiteChrome({
  navLinks,
  children,
}: {
  navLinks: NavLink[];
  children: React.ReactNode;
}) {
  const { token, setToken } = useAuthToken({ redirectTo: undefined });
  const { theme, setTheme } = useTheme();
  const [hasHydrated, setHasHydrated] = useState(false);
  const [recentSessions, setRecentSessions] = useState<ChatSessionDTO[]>([]);
  const [menuSessionId, setMenuSessionId] = useState<string | null>(null);
  const router = useRouter();
  const year = new Date().getFullYear();

  useEffect(() => {
    const frame = requestAnimationFrame(() => setHasHydrated(true));
    return () => cancelAnimationFrame(frame);
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

  useEffect(() => {
    if (!menuSessionId) return;
    function handleClick(event: MouseEvent) {
      const target = event.target as HTMLElement;
      if (!target.closest('[data-recent-menu]')) {
        setMenuSessionId(null);
      }
    }
    window.addEventListener("click", handleClick);
    return () => {
      window.removeEventListener("click", handleClick);
    };
  }, [menuSessionId]);

  const isLoggedIn = hasHydrated && Boolean(token);
  const isDark = theme === "dark";

  const sessionMenuPanelClass = [
    "absolute right-0 z-20 mt-3 w-60 rounded-3xl border p-3 text-xs shadow-[0_20px_60px_rgba(0,0,0,0.55)] backdrop-blur",
    isDark
      ? "border-white/10 bg-zinc-900/95 text-zinc-100"
      : "border-zinc-200/80 bg-white/95 text-zinc-900",
  ].join(" ");

  const sessionMenuButtonClass = [
    "flex w-full items-center justify-between rounded-2xl px-4 py-2 text-left font-medium transition",
    isDark ? "text-white hover:bg-white/10" : "text-zinc-800 hover:bg-zinc-100",
  ].join(" ");

  const sessionMenuShortcutClass = [
    "text-[10px] uppercase tracking-[0.3em]",
    isDark ? "text-white/40" : "text-zinc-500",
  ].join(" ");

  const sessionMenuDeleteClass = [
    "flex w-full items-center justify-between rounded-2xl px-4 py-2 text-left font-medium transition",
    isDark ? "text-red-300 hover:bg-red-500/10" : "text-red-600 hover:bg-red-50",
  ].join(" ");

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
    try {
      const data = await fetchChatSession(token, session.id);
      const blob = new Blob([JSON.stringify(data.session, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${session.title || session.id}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      setMenuSessionId(null);
    } catch (error) {
      console.error(error);
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
        <nav className="flex-1 px-4 overflow-hidden flex flex-col min-h-0">
          <div className="mt-6 flex flex-col rounded-2xl border border-zinc-200 bg-white/70 p-4 text-sm dark:border-zinc-800 dark:bg-zinc-900/60 flex-1 min-h-0">
            <p className="text-xs uppercase tracking-[0.3em] text-zinc-500 dark:text-zinc-400 flex-shrink-0">Recent chats</p>
            {recentSessions.length === 0 && (
              <p className="mt-2 text-xs text-zinc-500">No sessions yet.</p>
            )}
            <ul className="mt-3 flex-1 space-y-3 overflow-y-auto pr-1 min-h-0">
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
                    <div className="relative" data-recent-menu>
                      <button
                        type="button"
                        onClick={() => setMenuSessionId((current) => (current === session.id ? null : session.id))}
                        className="rounded-full border border-zinc-200 px-2 py-1 text-xs text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300"
                      >
                        ⋮
                      </button>
                      {menuSessionId === session.id && (
                        <div
                          className={sessionMenuPanelClass}
                          data-recent-menu-panel
                        >
                          <p className="px-2 pb-2 text-[10px] font-semibold uppercase tracking-[0.35em] opacity-70">
                            Session actions
                          </p>
                          <div className="space-y-1">
                            <button
                              type="button"
                              onClick={() => handleRenameSession(session)}
                              className={sessionMenuButtonClass}
                            >
                              <span className="inline-flex items-center gap-2">Rename chat</span>
                              <span className={sessionMenuShortcutClass}>⌘R</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => handleShareSession(session)}
                              className={sessionMenuButtonClass}
                            >
                              <span className="inline-flex items-center gap-2">Share JSON</span>
                              <span className={sessionMenuShortcutClass}>⇧S</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteSession(session)}
                              className={sessionMenuDeleteClass}
                            >
                              <span className="inline-flex items-center gap-2">Delete chat</span>
                              <span
                                className={`${sessionMenuShortcutClass} ${
                                  isDark ? "text-red-300/80" : "text-red-400/80"
                                }`}
                              >
                                ⌘⌫
                              </span>
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
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
            className="mt-3 w-full rounded-full border border-zinc-200 px-4 py-2 text-sm font-semibold text-zinc-900 transition hover:bg-zinc-900 hover:text-white dark:border-zinc-700 dark:text-white dark:hover:bg-white dark:hover:text-zinc-900"
          >
            {isDark ? "Switch to Light" : "Switch to Dark"}
          </button>
          <button
            type="button"
            onClick={handleAuthClick}
            className="mt-2 w-full rounded-full border border-zinc-200 px-4 py-2 text-sm font-semibold text-zinc-900 transition hover:bg-zinc-900 hover:text-white dark:border-zinc-700 dark:text-white dark:hover:bg-white dark:hover:text-zinc-900"
          >
            {isLoggedIn ? "Sign out" : "Sign in"}
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
            <div className="flex flex-wrap justify-center gap-4 text-xs uppercase tracking-[0.3em]">
              {navLinks.map((link) => (
                <Link key={link.href} href={link.href} className="hover:text-zinc-900 dark:hover:text-white transition">
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
