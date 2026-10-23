"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useAuthToken } from "@/hooks/useAuthToken";
import { useTheme } from "@/context/theme-context";
import { LogoMark } from "@/components/logo-mark";
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
  fetchCourses,
  logout,
} from "@/lib/api";
import { clearAuthToken } from "@/lib/auth";
import { loginPathFor } from "@/lib/safe-next";
import { CHAT_SESSION_SELECTED_EVENT, CHAT_SESSIONS_UPDATED_EVENT, dispatchChatSessionsUpdated } from "@/lib/events";
import { DeleteChatModal } from "@/components/chat/delete-chat-modal";
import { RenameChatModal } from "@/components/chat/rename-chat-modal";
import { SearchChatsModal } from "@/components/chat/search-chats-modal";
import { useUser } from "@/hooks/useUser";
import { toast } from "sonner";
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
  PanelLeftClose,
  PanelLeft,
  Search,
  Pin,
  Archive,
  ShieldAlert,
  GraduationCap,
  Menu,
  X,
  SquarePen,
  MoreHorizontal,
  Pencil,
  Trash2,
} from "lucide-react";

type NavSection = "main" | "manage" | "more";
type NavLink = { href: string; label: string; section?: NavSection; adminOnly?: boolean; instructorOnly?: boolean };

const SIDEBAR_COLLAPSED_KEY = "sat-sidebar-collapsed";

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
  "/instructor": GraduationCap,
};

const STANDALONE_ROUTES = new Set(["/login", "/signup", "/password-setup", "/verify"]);

export function SiteChrome({
  navLinks,
  children,
}: {
  navLinks: NavLink[];
  children: React.ReactNode;
}) {
  const { token } = useAuthToken({ redirectTo: undefined });
  const { user, isAdmin } = useUser();
  const { theme, setTheme, hasHydrated: themeHasHydrated } = useTheme();
  const pathname = usePathname();

  // Routes that need full-height layout (no footer, no padding)
  const isFullHeightRoute = pathname === "/chat" || pathname.startsWith("/chat/");
  // Sign-in flows are full-screen layouts of their own; the app sidebar only
  // offers signed-out visitors links that redirect back to /login.
  const isStandaloneRoute =
    STANDALONE_ROUTES.has(pathname) || pathname.startsWith("/password-reset/");
  const [hasHydrated, setHasHydrated] = useState(false);
  const [recentSessions, setRecentSessions] = useState<ChatSessionDTO[]>([]);
  const [menuSessionId, setMenuSessionId] = useState<string | null>(null);
  const [shareStatus, setShareStatus] = useState<{ sharing: boolean; message: string | null; shareUrl: string | null }>({ sharing: false, message: null, shareUrl: null });
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [deleteModalSession, setDeleteModalSession] = useState<ChatSessionDTO | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [renameModalSession, setRenameModalSession] = useState<ChatSessionDTO | null>(null);
  const [isRenaming, setIsRenaming] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsedState] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [searchModalOpen, setSearchModalOpen] = useState(false);
  const [hasInstructorCourse, setHasInstructorCourse] = useState(false);
  const router = useRouter();

  useEffect(() => {
    setHasHydrated(true);
    try {
      setSidebarCollapsedState(window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1");
    } catch {
      // Storage blocked (private mode): fall back to the expanded sidebar.
    }
  }, []);

  const setSidebarCollapsed = useCallback((collapsed: boolean) => {
    setSidebarCollapsedState(collapsed);
    try {
      window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? "1" : "0");
    } catch {
      // Not persisted; the choice still applies for this page view.
    }
  }, []);

  useEffect(() => {
    function handleSelected(event: Event) {
      setActiveSessionId((event as CustomEvent<string | null>).detail ?? null);
    }
    window.addEventListener(CHAT_SESSION_SELECTED_EVENT, handleSelected);
    return () => window.removeEventListener(CHAT_SESSION_SELECTED_EVENT, handleSelected);
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
    if (!token || isAdmin) {
      setHasInstructorCourse(Boolean(isAdmin));
      return;
    }
    fetchCourses(token)
      .then((courses) => setHasInstructorCourse(courses.some((course) => course.membership_role === "instructor")))
      .catch(() => setHasInstructorCourse(false));
  }, [isAdmin, token]);

  const handleCreateSession = useCallback(async () => {
    if (!token) {
      router.push(loginPathFor("/chat"));
      return;
    }
    if (isCreatingSession) return;
    setIsCreatingSession(true);
    try {
      const next = await createChatSession({ token, title: undefined });
      setRecentSessions((prev) => [next, ...prev.filter((s) => s.id !== next.id)]);
      router.push(`/chat?session=${next.id}`);
      dispatchChatSessionsUpdated();
      toast.success("New chat created");
    } catch (error) {
      console.error("Failed to create session:", error);
      toast.error("Failed to create chat");
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

  const handleAuthClick = async () => {
    if (!hasHydrated) return;
    if (token) {
      // Clearing client state alone left the HttpOnly session cookies in
      // place, so every page still authenticated after "Sign out".
      try {
        await logout();
      } catch {
        // The server didn't confirm (offline or 5xx): the cookies may still
        // be live, so stay signed in rather than fake a sign-out.
        toast.error("Couldn't sign you out. Check your connection and try again.", {
          action: { label: "Retry", onClick: () => void handleAuthClick() },
        });
        return;
      }
      clearAuthToken();
      // Full reload (not router.replace) so no signed-in data survives in
      // React state or the client router cache.
      window.location.replace("/login");
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
      toast.success("Chat renamed");
    } catch (error) {
      console.error(error);
      toast.error("Failed to rename chat");
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
      toast.success("Chat deleted");
    } catch (error) {
      console.error(error);
      toast.error("Failed to delete chat");
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
        toast.success("Share link copied to clipboard");
      } else {
        setShareStatus({ sharing: false, message: "Link created!", shareUrl });
        toast.success("Share link created");
      }

      setTimeout(() => setShareStatus({ sharing: false, message: null, shareUrl: null }), 3000);
    } catch (error) {
      console.error(error);
      setShareStatus({ sharing: false, message: "Failed to share", shareUrl: null });
      toast.error("Failed to create share link");
    }
  };

  const handleSelectSession = (sessionId: string) => {
    setMobileNavOpen(false);
    router.push(`/chat?session=${sessionId}`);
  };

  const handlePinSession = async (session: ChatSessionDTO) => {
    if (!token) return;
    setMenuSessionId(null);
    try {
      await pinChatSession(token, session.id, !session.is_pinned);
      await loadSessions();
      dispatchChatSessionsUpdated();
      toast.success(session.is_pinned ? "Chat unpinned" : "Chat pinned");
    } catch (error) {
      console.error("Failed to pin session:", error);
      toast.error("Failed to pin chat");
    }
  };

  const handleArchiveSession = async (session: ChatSessionDTO) => {
    if (!token) return;
    setMenuSessionId(null);
    try {
      await archiveChatSession(token, session.id, !session.is_archived);
      await loadSessions();
      dispatchChatSessionsUpdated();
      toast.success(session.is_archived ? "Chat unarchived" : "Chat archived");
    } catch (error) {
      console.error("Failed to archive session:", error);
      toast.error("Failed to archive chat");
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
  const visibleNavLinks = navLinks.filter(
    (link) => (!link.adminOnly || isAdmin) && (!link.instructorOnly || hasInstructorCourse)
  );

  const isActive = (href: string) =>
    pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));
  const navSection = (section: NavSection) =>
    visibleNavLinks.filter((link) => (link.section ?? "main") === section);
  const userName = user ? user.display_name || user.full_name || user.username : "";
  // The rail (collapsed) form only exists on desktop; the mobile drawer is always full.
  const rail = sidebarCollapsed;

  const renderNavLink = (link: NavLink) => {
    const Icon = navIcons[link.href] || FolderOpen;
    const active = isActive(link.href);
    return (
      <Link
        key={link.href}
        href={link.href}
        onClick={() => setMobileNavOpen(false)}
        aria-current={active ? "page" : undefined}
        title={rail ? link.label : undefined}
        className={[
          "group flex h-9 items-center gap-3 rounded-lg px-2.5 text-sm font-medium transition-colors",
          rail ? "lg:justify-center lg:px-0" : "",
          active
            ? "bg-zinc-900 text-white dark:bg-white dark:text-zinc-900"
            : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-white",
        ].join(" ")}
      >
        <Icon className="h-4 w-4 flex-shrink-0" />
        <span className={rail ? "lg:sr-only" : ""}>{link.label}</span>
      </Link>
    );
  };

  const iconButtonClass =
    "flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-900 disabled:opacity-50 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white";

  if (isStandaloneRoute) return <>{children}</>;

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Mobile: backdrop overlay ── */}
      {mobileNavOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileNavOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* ── Mobile: top header bar (only on < lg) ── */}
      <header className="fixed top-0 left-0 right-0 z-30 flex h-14 items-center justify-between border-b border-zinc-200 bg-white/95 px-4 backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/95 lg:hidden">
        <button
          onClick={() => setMobileNavOpen(true)}
          className={iconButtonClass}
          aria-label="Open navigation"
          aria-expanded={mobileNavOpen}
        >
          <Menu className="h-5 w-5" />
        </button>
        <Link href="/" className="flex items-center gap-2 text-base font-semibold text-zinc-900 dark:text-white">
          <LogoMark size={26} />
          Smart AI Tutor
        </Link>
        <button
          onClick={handleCreateSession}
          disabled={isCreatingSession}
          className={iconButtonClass}
          aria-label="New chat"
        >
          <SquarePen className="h-5 w-5" />
        </button>
      </header>

      {/* Sidebar — desktop: full (w-64) or icon rail (w-16); mobile: slide-in drawer */}
      <aside
        aria-label="Main navigation"
        className={[
          "fixed left-0 top-0 bottom-0 z-50 flex w-72 flex-col border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900",
          "transition-[transform,width] duration-200",
          mobileNavOpen ? "translate-x-0 shadow-2xl" : "-translate-x-full",
          "lg:translate-x-0 lg:shadow-none",
          rail ? "lg:w-16" : "lg:w-64",
        ].join(" ")}
      >
        {/* Brand + collapse */}
        <div className={["flex h-14 flex-shrink-0 items-center gap-2 px-3", rail ? "lg:justify-center lg:px-0" : "justify-between"].join(" ")}>
          <Link
            href="/"
            onClick={() => setMobileNavOpen(false)}
            className={["flex min-w-0 items-center gap-2.5 px-1 text-base font-semibold text-zinc-900 dark:text-white", rail ? "lg:hidden" : ""].join(" ")}
          >
            <LogoMark size={28} />
            <span className="truncate">Smart AI Tutor</span>
          </Link>
          {/* Mobile: close the drawer */}
          <button onClick={() => setMobileNavOpen(false)} className={`${iconButtonClass} lg:hidden`} aria-label="Close navigation">
            <X className="h-5 w-5" />
          </button>
          {/* Desktop: collapse to / expand from the icon rail */}
          <button
            onClick={() => setSidebarCollapsed(!rail)}
            className={`${iconButtonClass} hidden lg:flex`}
            aria-label={rail ? "Expand sidebar" : "Collapse sidebar"}
            title={rail ? "Expand sidebar" : "Collapse sidebar"}
          >
            {rail ? <PanelLeft className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
          </button>
        </div>

        {/* Primary actions */}
        {isLoggedIn && (
          <div className={["flex flex-shrink-0 gap-1.5 px-3 pb-3", rail ? "lg:flex-col lg:items-center lg:px-0" : ""].join(" ")}>
            <button
              onClick={handleCreateSession}
              disabled={isCreatingSession}
              title={rail ? "New chat" : undefined}
              aria-label="New chat"
              className={[
                "flex h-9 flex-1 items-center gap-2 rounded-lg bg-zinc-900 px-3 text-sm font-medium text-white transition hover:bg-zinc-700 disabled:opacity-60 dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-200",
                rail ? "lg:w-9 lg:flex-none lg:justify-center lg:px-0" : "",
              ].join(" ")}
            >
              {isCreatingSession ? (
                <span className="h-4 w-4 inline-block animate-spin rounded-full border-2 border-current border-t-transparent" />
              ) : (
                <SquarePen className="h-4 w-4 flex-shrink-0" />
              )}
              <span className={rail ? "lg:sr-only" : ""}>New chat</span>
            </button>
            <button
              onClick={() => setSearchModalOpen(true)}
              className={`${iconButtonClass} border border-zinc-200 dark:border-zinc-700`}
              aria-label="Search chats"
              title="Search chats"
            >
              <Search className="h-4 w-4" />
            </button>
          </div>
        )}

        <nav className="flex min-h-0 flex-1 flex-col px-3 lg:overflow-hidden">
          <div className="grid flex-shrink-0 gap-0.5">{navSection("main").map(renderNavLink)}</div>

          {navSection("manage").length > 0 && (
            <div className="mt-4 grid flex-shrink-0 gap-0.5">
              <p className={["px-2.5 pb-1 text-[11px] font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500", rail ? "lg:sr-only" : ""].join(" ")}>
                Manage
              </p>
              {navSection("manage").map(renderNavLink)}
            </div>
          )}

          {!isLoggedIn && !rail && (
            <div className="mt-4 rounded-xl border border-dashed border-zinc-200 p-4 text-sm text-zinc-600 dark:border-zinc-800 dark:text-zinc-300">
              <p className="font-semibold">You are not signed in yet.</p>
              <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">Sign in to see your chats.</p>
            </div>
          )}

          {/* Recent chats take all remaining height and scroll on their own. */}
          {isLoggedIn && (
            <div className={["mt-4 flex min-h-0 flex-1 flex-col", rail ? "lg:hidden" : ""].join(" ")}>
              <p className="flex-shrink-0 px-2.5 pb-1 text-[11px] font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                Recent chats
              </p>
              {displayedSessions.length === 0 ? (
                <p className="px-2.5 py-1 text-xs text-zinc-500">No chats yet. Start one above.</p>
              ) : (
                <ul className={`-mx-1 min-h-0 flex-1 space-y-0.5 px-1 pb-2 ${menuSessionId ? "overflow-visible" : "overflow-y-auto"}`}>
                  {displayedSessions.map((session) => {
                    const title = session.title?.trim() || "New chat";
                    const current = pathname === "/chat" && activeSessionId === session.id;
                    const menuOpen = menuSessionId === session.id;
                    return (
                      <li key={session.id} className="relative" data-session-menu>
                        <div
                          className={[
                            "group flex h-9 items-center rounded-lg pl-2.5 pr-1 text-sm transition-colors",
                            current
                              ? "bg-zinc-100 font-medium text-zinc-900 dark:bg-zinc-800 dark:text-white"
                              : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-white",
                          ].join(" ")}
                        >
                          {session.is_pinned && <Pin className="mr-1.5 h-3 w-3 flex-shrink-0 text-zinc-400" aria-label="Pinned" />}
                          <button
                            type="button"
                            onClick={() => handleSelectSession(session.id)}
                            aria-current={current ? "page" : undefined}
                            className="min-w-0 flex-1 truncate text-left outline-none focus-visible:underline"
                          >
                            {title}
                          </button>
                          <button
                            type="button"
                            onClick={() => setMenuSessionId(menuOpen ? null : session.id)}
                            className={[
                              "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md text-zinc-500 transition hover:bg-zinc-200 hover:text-zinc-900 dark:hover:bg-zinc-700 dark:hover:text-white",
                              // Visible on hover/focus, or always on touch screens.
                              menuOpen ? "opacity-100" : "opacity-100 lg:opacity-0 lg:group-hover:opacity-100 lg:focus-visible:opacity-100",
                            ].join(" ")}
                            aria-label={`Options for ${title}`}
                            aria-expanded={menuOpen}
                          >
                            <MoreHorizontal className="h-4 w-4" />
                          </button>
                        </div>
                        {menuOpen && (
                          <div className={sessionMenuPanelClass} role="menu">
                            <button type="button" role="menuitem" onClick={() => handlePinSession(session)} className={sessionMenuItemClass}>
                              <Pin className={sessionMenuIconClass} />
                              <span>{session.is_pinned ? "Unpin" : "Pin chat"}</span>
                            </button>
                            <button type="button" role="menuitem" onClick={() => handleRenameSession(session)} className={sessionMenuItemClass}>
                              <Pencil className={sessionMenuIconClass} />
                              <span>Rename</span>
                            </button>
                            <button type="button" role="menuitem" onClick={() => handleArchiveSession(session)} className={sessionMenuItemClass}>
                              <Archive className={sessionMenuIconClass} />
                              <span>Archive</span>
                            </button>
                            <div className={["my-1 border-t", isDark ? "border-white/10" : "border-zinc-200"].join(" ")} />
                            <button type="button" role="menuitem" onClick={() => handleDeleteSession(session)} className={sessionMenuDeleteClass}>
                              <Trash2 className={sessionMenuDeleteIconClass} />
                              <span>Delete</span>
                            </button>
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          )}
        </nav>

        {/* Footer: account, theme, sign out, secondary links */}
        <div className={["flex-shrink-0 border-t border-zinc-200 p-3 dark:border-zinc-800", rail ? "lg:px-0" : ""].join(" ")}>
          <div className={["flex items-center gap-1", rail ? "lg:flex-col" : ""].join(" ")}>
            {isLoggedIn && user ? (
              <Link
                href="/profile"
                onClick={() => setMobileNavOpen(false)}
                aria-current={isActive("/profile") ? "page" : undefined}
                title={rail ? `${userName} — profile` : "Your profile"}
                className={[
                  "flex min-w-0 flex-1 items-center gap-2.5 rounded-lg p-1.5 transition hover:bg-zinc-100 dark:hover:bg-zinc-800",
                  isActive("/profile") ? "bg-zinc-100 dark:bg-zinc-800" : "",
                  rail ? "lg:flex-none" : "",
                ].join(" ")}
              >
                <span
                  className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${
                    isAdmin ? "bg-gradient-to-br from-amber-500 to-orange-600" : "bg-gradient-to-br from-indigo-500 to-violet-600"
                  }`}
                >
                  {(userName || "?").charAt(0).toUpperCase()}
                </span>
                <span className={["min-w-0 flex-1 leading-tight", rail ? "lg:sr-only" : ""].join(" ")}>
                  <span className="block truncate text-sm font-semibold text-zinc-900 dark:text-white">{userName}</span>
                  <span className="block truncate text-xs text-zinc-500 dark:text-zinc-400">{isAdmin ? "Admin" : "Student"} · Profile</span>
                </span>
              </Link>
            ) : (
              <span className="flex-1" />
            )}
            <button
              type="button"
              onClick={handleToggleTheme}
              disabled={!showThemeToggle}
              className={iconButtonClass}
              aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
              title={isDark ? "Light theme" : "Dark theme"}
            >
              {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <button
              type="button"
              onClick={handleAuthClick}
              className={iconButtonClass}
              aria-label={isLoggedIn ? "Sign out" : "Sign in"}
              title={isLoggedIn ? "Sign out" : "Sign in"}
            >
              {isLoggedIn ? <LogOut className="h-4 w-4" /> : <LogIn className="h-4 w-4" />}
            </button>
          </div>
          <div className={["mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 px-1.5 text-xs text-zinc-500 dark:text-zinc-400", rail ? "lg:hidden" : ""].join(" ")}>
            {navSection("more").map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileNavOpen(false)}
                aria-current={isActive(link.href) ? "page" : undefined}
                className={isActive(link.href) ? "font-semibold text-zinc-900 dark:text-white" : "hover:text-zinc-900 dark:hover:text-white"}
              >
                {link.label}
              </Link>
            ))}
            <a href="mailto:support@smartaitutor.com" className="hover:text-zinc-900 dark:hover:text-white">
              Help
            </a>
          </div>
        </div>
      </aside>

      {/* Main content area */}
      <div className={`flex min-w-0 flex-1 flex-col bg-zinc-50 text-zinc-900 transition-[margin] duration-200 dark:bg-zinc-950 dark:text-white ${rail ? "lg:ml-16" : "lg:ml-64"}`}>
        {/* Mobile: pt-14 to clear the fixed top header bar; full-height routes manage their own padding */}
        <main className={
          isFullHeightRoute
            ? "flex-1 flex min-w-0 flex-col overflow-hidden pt-14 lg:pt-0"
            : "flex-1 overflow-y-auto px-4 py-5 pt-[4.75rem] pb-8 sm:px-8 lg:pt-5 lg:pb-8"
        }>
          {children}
        </main>
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
