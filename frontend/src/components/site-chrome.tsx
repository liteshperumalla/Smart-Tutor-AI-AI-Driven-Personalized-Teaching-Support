"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useAuthToken } from "@/hooks/useAuthToken";
import { useTheme } from "@/context/theme-context";
import {
  listChatSessions,
  ChatSessionDTO,
  renameChatSession,
  deleteChatSession,
  fetchChatSession,
  shareChatSession,
  createChatSession,
  pinChatSession,
  archiveChatSession,
} from "@/lib/api";
import { dispatchChatSessionsUpdated } from "@/lib/events";
import { CHAT_SESSIONS_UPDATED_EVENT } from "@/lib/events";
import { DeleteChatModal } from "@/components/chat/delete-chat-modal";
import { RenameChatModal } from "@/components/chat/rename-chat-modal";
import { SearchChatsModal } from "@/components/chat/search-chats-modal";
import { useUser } from "@/hooks/useUser";
import {
  Home,
  MessageCircle,
  Brain,
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
  PanelLeftClose,
  PanelLeft,
  Search,
  Pin,
  Archive,
  ShieldAlert,
} from "lucide-react";

type NavLink = { href: string; label: string; icon?: React.ComponentType<{ className?: string }>; adminOnly?: boolean };

const navIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  "/": Home,
  "/chat": MessageCircle,
  "/quiz": Brain,
  "/evaluation": BarChart3,
  "/appointments": Calendar,
  "/resources": FolderOpen,
  "/about": Info,
  "/feedback": MessageSquare,
  "/profile": User,
  "/admin": ShieldAlert,
};

export function SiteChrome({
  navLinks,
  children,
}: {
  navLinks: NavLink[];
  children: React.ReactNode;
}) {
  const { token, setToken } = useAuthToken({ redirectTo: undefined });
  const { user, isAdmin } = useUser();
  const { theme, setTheme, hasHydrated: themeHasHydrated } = useTheme();
  const pathname = usePathname();

  // Routes that need full-height layout (no footer, no padding)
  const isFullHeightRoute = pathname === "/chat" || pathname.startsWith("/chat/");
  const [hasHydrated, setHasHydrated] = useState(false);
  const [recentSessions, setRecentSessions] = useState<ChatSessionDTO[]>([]);
  const [menuSessionId, setMenuSessionId] = useState<string | null>(null);
  const [shareStatus, setShareStatus] = useState<{ sharing: boolean; message: string | null; shareUrl: string | null }>({ sharing: false, message: null, shareUrl: null });
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [deleteModalSession, setDeleteModalSession] = useState<ChatSessionDTO | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [renameModalSession, setRenameModalSession] = useState<ChatSessionDTO | null>(null);
  const [isRenaming, setIsRenaming] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [searchModalOpen, setSearchModalOpen] = useState(false);
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

  const handleCreateSession = useCallback(async () => {
    if (!token || isCreatingSession) return;
    setIsCreatingSession(true);
    try {
      const next = await createChatSession({ token, title: undefined });
      setRecentSessions((prev) => [next, ...prev.filter((s) => s.id !== next.id)]);
      router.push(`/chat?session=${next.id}`);
      dispatchChatSessionsUpdated();
    } catch (error) {
      console.error("Failed to create session:", error);
    } finally {
      setIsCreatingSession(false);
    }
  }, [token, isCreatingSession, router]);

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
      // Use data attribute to find all session menu containers, not a single ref
      const target = event.target as Node;
      const menuContainer = (target as Element).closest?.('[data-session-menu]');
      // If clicked inside a session menu container, don't close
      if (menuContainer) return;
      setMenuSessionId(null);
    }
    document.addEventListener("mousedown", handleClick);
    return () => {
      document.removeEventListener("mousedown", handleClick);
    };
  }, [menuSessionId]);

  // IMPORTANT: token will be "authenticated" string when logged in (not null/undefined)
  const isLoggedIn = hasHydrated && token === "authenticated" && !!user;
  // IMPORTANT: Wait for theme to hydrate before determining dark mode to avoid wrong button text
  const isDark = themeHasHydrated && theme === "dark";
  const showThemeToggle = themeHasHydrated;

  const sessionMenuPanelClass = [
    "absolute right-0 top-full z-[60] mt-1 w-48 rounded-xl border p-1.5 shadow-lg backdrop-blur animate-fade-in",
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

  const handleRenameSession = (session: ChatSessionDTO) => {
    setRenameModalSession(session);
    setMenuSessionId(null);
  };

  const handleConfirmRename = async (newTitle: string) => {
    if (!token || !renameModalSession) return;
    setIsRenaming(true);
    try {
      await renameChatSession(token, renameModalSession.id, newTitle);
      setRenameModalSession(null);
      await loadSessions();
      dispatchChatSessionsUpdated();
    } catch (error) {
      console.error(error);
    } finally {
      setIsRenaming(false);
    }
  };

  const handleDeleteSession = (session: ChatSessionDTO) => {
    setDeleteModalSession(session);
    setMenuSessionId(null);
  };

  const handleConfirmDelete = async () => {
    if (!token || !deleteModalSession) return;
    setIsDeleting(true);
    try {
      await deleteChatSession(token, deleteModalSession.id);
      setDeleteModalSession(null);
      await loadSessions();
      dispatchChatSessionsUpdated();
    } catch (error) {
      console.error(error);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleShareSession = async (session: ChatSessionDTO) => {
    if (!token) return;
    setShareStatus({ sharing: true, message: null, shareUrl: null });
    try {
      const data = await shareChatSession(token, session.id, 7);
      const shareUrl = `${window.location.origin}${data.share_url}`;
      
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(shareUrl);
        setShareStatus({ sharing: false, message: "Link copied!", shareUrl });
      } else {
        setShareStatus({ sharing: false, message: "Link created!", shareUrl });
      }
      
      setTimeout(() => setShareStatus({ sharing: false, message: null, shareUrl: null }), 3000);
    } catch (error) {
      console.error(error);
      setShareStatus({ sharing: false, message: "Failed to share", shareUrl: null });
    }
  };

  const handleSelectSession = (sessionId: string) => {
    router.push(`/chat?session=${sessionId}`);
  };

  const handlePinSession = async (session: ChatSessionDTO) => {
    if (!token) return;
    setMenuSessionId(null);
    try {
      await pinChatSession(token, session.id, !session.is_pinned);
      await loadSessions();
      dispatchChatSessionsUpdated();
    } catch (error) {
      console.error("Failed to pin session:", error);
    }
  };

  const handleArchiveSession = async (session: ChatSessionDTO) => {
    if (!token) return;
    setMenuSessionId(null);
    try {
      await archiveChatSession(token, session.id, !session.is_archived);
      await loadSessions();
      dispatchChatSessionsUpdated();
    } catch (error) {
      console.error("Failed to archive session:", error);
    }
  };

  // Filter sessions: show non-archived, with pinned at top
  const displayedSessions = recentSessions
    .filter(s => !s.is_archived)
    .sort((a, b) => {
      if (a.is_pinned && !b.is_pinned) return -1;
      if (!a.is_pinned && b.is_pinned) return 1;
      return 0;
    });

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar Hover Zone (visible when collapsed) - shows button on hover */}
      {sidebarCollapsed && (
        <div className="fixed left-0 top-0 bottom-0 w-12 z-40 hidden lg:block group cursor-pointer">
          {/* Button appears on hover with smooth transition */}
          <button
            onClick={() => setSidebarCollapsed(false)}
            className="absolute left-3 top-4 p-2.5 rounded-xl bg-zinc-800/90 backdrop-blur-sm border border-zinc-700 text-zinc-300 hover:text-white hover:bg-zinc-700 transition-all duration-300 shadow-xl opacity-0 group-hover:opacity-100 -translate-x-3 group-hover:translate-x-0"
            title="Expand sidebar"
          >
            <PanelLeft className="h-5 w-5" />
          </button>
        </div>
      )}

      {/* Fixed Sidebar */}
      <aside className={`hidden flex-shrink-0 flex-col border-r border-zinc-200 bg-white/90 backdrop-blur transition-all duration-300 dark:border-zinc-800 dark:bg-zinc-900/80 lg:flex fixed left-0 top-0 bottom-0 z-30 overflow-hidden ${sidebarCollapsed ? 'w-0 opacity-0' : 'w-64 opacity-100'}`}>
        <div className="px-6 py-6 flex items-center justify-between gap-2">
          <Link href="/" className="text-lg font-semibold text-zinc-900 dark:text-white whitespace-nowrap">
            Smart AI Tutor
          </Link>
          <button
            onClick={() => setSidebarCollapsed(true)}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-900 hover:bg-zinc-100 dark:text-zinc-500 dark:hover:text-white dark:hover:bg-white/10 transition flex-shrink-0"
            title="Collapse sidebar"
          >
            <PanelLeftClose className="h-5 w-5" />
          </button>
        </div>

        {/* Admin Panel Link */}
        {isLoggedIn && isAdmin && (
          <div className="px-4 mb-3">
            <Link
              href="/admin"
              className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 hover:bg-amber-100 dark:bg-amber-950/30 dark:border-amber-800 dark:text-amber-300 dark:hover:bg-amber-950/50 transition-colors"
            >
              <ShieldAlert className="h-4 w-4" />
              <span className="text-sm font-semibold">Admin Panel</span>
            </Link>
          </div>
        )}

        {/* New Chat and Search Buttons */}
        {isLoggedIn && (
          <div className="px-4 mb-4 space-y-2">
            {/* New Chat Button */}
            <button
              onClick={handleCreateSession}
              disabled={isCreatingSession}
              className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isCreatingSession ? (
                <span className="h-4 w-4 inline-block animate-spin rounded-full border-2 border-zinc-400 border-t-transparent"></span>
              ) : (
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              )}
              <span className="text-sm font-medium">{isCreatingSession ? "Creating..." : "New chat"}</span>
            </button>

            {/* Search Button */}
            <button
              onClick={() => setSearchModalOpen(true)}
              className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors"
            >
              <Search className="h-4 w-4" />
              <span className="text-sm">Search chats</span>
            </button>
          </div>
        )}

        <nav className="flex-1 px-4 flex flex-col min-h-0 overflow-hidden">
          {!isLoggedIn && (
            <div className="rounded-xl border border-dashed border-zinc-200 bg-white/70 p-4 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-300">
              <p className="font-semibold">You are not signed in yet.</p>
              <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                Sign in to view your recent chats and history.
              </p>
              <button
                type="button"
                onClick={() => router.push("/login")}
                className="mt-3 w-full rounded-xl border border-zinc-200 px-3 py-2 text-xs font-semibold text-zinc-900 transition hover:bg-zinc-900 hover:text-white dark:border-zinc-700 dark:text-white dark:hover:bg-white dark:hover:text-zinc-900"
              >
                Sign in
              </button>
            </div>
          )}
          {isLoggedIn && (
            <div className="flex flex-col rounded-xl border border-zinc-200 bg-white/70 p-4 text-sm dark:border-zinc-800 dark:bg-zinc-900/60 flex-1 min-h-0 overflow-hidden">
              <div className="flex items-center justify-between flex-shrink-0">
                <p className="text-xs uppercase tracking-[0.3em] text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5" />
                  Recent chats
                </p>
                <button
                  type="button"
                  onClick={handleCreateSession}
                  disabled={isCreatingSession}
                  className="p-1 rounded-lg text-zinc-400 hover:text-zinc-900 hover:bg-zinc-100 dark:text-zinc-500 dark:hover:text-white dark:hover:bg-white/10 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  title={isCreatingSession ? "Creating..." : "New chat"}
                >
                  {isCreatingSession ? (
                    <span className="h-4 w-4 inline-block animate-spin rounded-full border-2 border-zinc-400 border-t-transparent"></span>
                  ) : (
                    <Plus className="h-4 w-4" />
                  )}
                </button>
              </div>
              {displayedSessions.length === 0 && (
                <p className="mt-2 text-xs text-zinc-500">No sessions yet.</p>
              )}
               <ul className={`mt-3 flex-1 space-y-2 min-h-0 ${menuSessionId ? 'overflow-visible' : 'overflow-y-auto'}`}>
                 {displayedSessions.map((session) => (
                 <li key={session.id} className={menuSessionId === session.id ? 'relative z-10' : 'relative'}>
                   <div className="flex items-center gap-2 rounded-xl border border-zinc-200 bg-white/95 px-3 py-2 text-sm shadow-sm transition hover:-translate-y-0.5 dark:border-zinc-800 dark:bg-zinc-900/60">
                     {session.is_pinned && (
                       <Pin className="h-3 w-3 text-zinc-400 flex-shrink-0" />
                     )}
                 <button
                       type="button"
                       onClick={() => handleSelectSession(session.id)}
                       className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap border-none bg-transparent text-left font-semibold text-zinc-800 outline-none focus-visible:ring-2 focus-visible:ring-zinc-900 dark:text-zinc-100"
                     >
                       {session.title || `Session ${session.id.slice(0, 6)}`}
                     </button>
                     <div className="relative" data-session-menu>
                       <button
                         type="button"
                         onClick={() => setMenuSessionId((current) => (current === session.id ? null : session.id))}
                         className={[
                           "flex items-center justify-center rounded-lg p-1.5 transition",
                           menuSessionId && menuSessionId !== session.id ? "opacity-0 pointer-events-none" : "",
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
                           {/* Pin/Unpin */}
                           <button
                             type="button"
                             onClick={() => handlePinSession(session)}
                             className={sessionMenuItemClass}
                             aria-label={session.is_pinned ? `Unpin chat ${session.title || session.id}` : `Pin chat ${session.title || session.id}`}
                           >
                             <Pin className={sessionMenuIconClass} />
                             <span>{session.is_pinned ? "Unpin" : "Pin chat"}</span>
                           </button>
                           {/* Rename */}
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
                           {/* Archive */}
                           <button
                             type="button"
                             onClick={() => handleArchiveSession(session)}
                             className={sessionMenuItemClass}
                             aria-label={`Archive chat ${session.title || session.id}`}
                           >
                             <Archive className={sessionMenuIconClass} />
                             <span>Archive</span>
                           </button>
                           <div className={["my-1 border-t", isDark ? "border-white/10" : "border-zinc-200"].join(" ")}></div>
                           {/* Delete */}
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
          {/* User Role Badge */}
          {isLoggedIn && user && (
            <div className="flex items-center gap-2 mb-3">
              <User className="h-3.5 w-3.5 text-zinc-400" />
              <span className="text-xs font-medium text-zinc-600 dark:text-zinc-300 truncate">
                {user.username}
              </span>
              {isAdmin && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-700 dark:bg-amber-950/40 dark:text-amber-400">
                  Admin
                </span>
              )}
            </div>
          )}
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
            className="mt-3 w-full rounded-xl border border-zinc-200 px-4 py-2 text-sm font-semibold text-zinc-900 transition hover:bg-zinc-900 hover:text-white dark:border-zinc-700 dark:text-white dark:hover:bg-white dark:hover:text-zinc-900 disabled:opacity-50 disabled:cursor-wait flex items-center justify-center gap-2"
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
            className="mt-2 w-full rounded-xl border border-zinc-200 px-4 py-2 text-sm font-semibold text-zinc-900 transition hover:bg-zinc-900 hover:text-white dark:border-zinc-700 dark:text-white dark:hover:bg-white dark:hover:text-zinc-900 flex items-center justify-center gap-2"
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
      <div className={`flex flex-1 flex-col bg-zinc-50 text-zinc-900 transition-all duration-300 dark:bg-zinc-950 dark:text-white ${sidebarCollapsed ? 'lg:ml-0' : 'lg:ml-64'}`}>
        {/* Scrollable content area — full-height routes get no padding/overflow so they manage their own layout */}
        <main className={isFullHeightRoute ? "flex-1 flex flex-col overflow-hidden" : "flex-1 overflow-y-auto px-4 py-5 pb-20 sm:px-8"}>{children}</main>

        {/* Fixed Footer Nav — hidden on full-height routes like Chat */}
        {!isFullHeightRoute && (
          <footer className={`fixed bottom-0 left-0 right-0 border-t border-zinc-200 bg-white/95 backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/95 z-20 transition-all duration-300 ${sidebarCollapsed ? 'lg:left-0' : 'lg:left-64'}`}>
            <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-4 text-sm text-zinc-600 dark:text-zinc-400 sm:flex-row sm:items-center sm:justify-center">
              <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-xs uppercase tracking-[0.2em]">
                {navLinks
                  .filter((link) => !link.adminOnly || isAdmin)
                  .map((link) => {
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
        )}
      </div>

      {/* Delete Chat Modal */}
      <DeleteChatModal
        isOpen={deleteModalSession !== null}
        onClose={() => setDeleteModalSession(null)}
        onConfirm={handleConfirmDelete}
        chatTitle={deleteModalSession?.title || `Session ${deleteModalSession?.id?.slice(0, 6) || ""}`}
        isDeleting={isDeleting}
      />

      {/* Rename Chat Modal */}
      <RenameChatModal
        isOpen={renameModalSession !== null}
        onClose={() => setRenameModalSession(null)}
        onConfirm={handleConfirmRename}
        currentTitle={renameModalSession?.title || `Session ${renameModalSession?.id?.slice(0, 6) || ""}`}
        isRenaming={isRenaming}
      />

      {/* Search Chats Modal */}
      <SearchChatsModal
        isOpen={searchModalOpen}
        onClose={() => setSearchModalOpen(false)}
        sessions={recentSessions}
        onSelectSession={(sessionId) => {
          handleSelectSession(sessionId);
          setSearchModalOpen(false);
        }}
        onCreateSession={() => {
          handleCreateSession();
          setSearchModalOpen(false);
        }}
        isCreating={isCreatingSession}
      />
    </div>
  );
}
