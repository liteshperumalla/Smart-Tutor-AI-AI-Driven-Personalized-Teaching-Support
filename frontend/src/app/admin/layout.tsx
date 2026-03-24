"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useUser } from "@/hooks/useUser";
import {
  LayoutDashboard,
  Users,
  MessageSquare,
  CalendarDays,
  Megaphone,
  BarChart3,
  FolderOpen,
  ShieldAlert,
} from "lucide-react";

const adminNav = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/appointments", label: "Appointments", icon: CalendarDays },
  { href: "/admin/feedback", label: "Feedback & Bugs", icon: MessageSquare },
  { href: "/admin/announcements", label: "Announcements", icon: Megaphone },
  { href: "/admin/resources", label: "Resources", icon: FolderOpen },
  { href: "/admin/evaluation", label: "Evaluation", icon: BarChart3 },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, isAdmin, isLoading } = useUser();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !isAdmin) {
      router.replace("/");
    }
  }, [isLoading, isAdmin, router]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-white" />
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Checking admin access…</p>
        </div>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-4 rounded-2xl border border-red-200 bg-red-50 p-8 dark:border-red-900 dark:bg-red-950/30">
          <ShieldAlert className="h-12 w-12 text-red-500" />
          <h2 className="text-lg font-semibold text-red-700 dark:text-red-400">Access Denied</h2>
          <p className="text-sm text-red-600 dark:text-red-400">You do not have admin privileges.</p>
          <Link
            href="/"
            className="mt-2 rounded-xl bg-zinc-900 px-6 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-200"
          >
            Go Home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Admin Header */}
      <div className="flex items-center gap-3">
        <ShieldAlert className="h-6 w-6 text-zinc-900 dark:text-white" />
        <h1 className="text-xl font-bold text-zinc-900 dark:text-white">Admin Panel</h1>
        <span className="rounded-full bg-zinc-900 px-3 py-0.5 text-xs font-medium text-white dark:bg-white dark:text-zinc-900">
          {user?.username}
        </span>
      </div>

      {/* Admin Navigation Tabs — horizontally scrollable on small screens */}
      <div className="overflow-x-auto rounded-2xl border border-zinc-200 bg-white/70 dark:border-zinc-800 dark:bg-zinc-900/60">
        <nav className="flex gap-1 p-2 min-w-max sm:flex-wrap sm:min-w-0">
          {adminNav.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/admin"
                ? pathname === "/admin"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={[
                  "flex min-h-[40px] items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition whitespace-nowrap sm:px-4",
                  isActive
                    ? "bg-zinc-900 text-white dark:bg-white dark:text-zinc-900"
                    : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white",
                ].join(" ")}
              >
                <Icon className="h-4 w-4 flex-shrink-0" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Admin Page Content */}
      <div>{children}</div>
    </div>
  );
}
