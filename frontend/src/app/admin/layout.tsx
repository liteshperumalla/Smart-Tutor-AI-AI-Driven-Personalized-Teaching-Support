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
  GraduationCap,
  ShieldAlert,
} from "lucide-react";
import { Skeleton, SkeletonRegion, SkeletonStatGrid } from "@/components/skeleton";

const adminNav = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/courses", label: "Courses", icon: GraduationCap },
  { href: "/admin/appointments", label: "Appointments", icon: CalendarDays },
  { href: "/admin/feedback", label: "Feedback & Bugs", icon: MessageSquare },
  { href: "/admin/announcements", label: "Announcements", icon: Megaphone },
  { href: "/admin/resources", label: "Resources", icon: FolderOpen },
  { href: "/admin/course-quality", label: "Course Quality", icon: GraduationCap },
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
      // Admin shell placeholder while access is checked: header, tab bar, stats.
      <SkeletonRegion label="Checking admin access" className="space-y-6">
        <div className="flex items-center gap-3">
          <Skeleton className="h-6 w-6 rounded-md" />
          <Skeleton className="h-5 w-36" />
        </div>
        <div className="flex gap-1 overflow-hidden rounded-[14px] border border-line bg-surface p-1.5">
          {[24, 16, 28, 20, 28, 24].map((w, i) => (
            <Skeleton key={i} className="h-10 shrink-0 rounded-md" style={{ width: `${w * 4}px` }} />
          ))}
        </div>
        <SkeletonStatGrid />
      </SkeletonRegion>
    );
  }

  if (!isAdmin) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-4 rounded-2xl border border-danger/30 bg-danger-bg p-8">
          <ShieldAlert className="h-12 w-12 text-danger" />
          <h2 className="text-lg font-semibold text-danger">Access Denied</h2>
          <p className="text-sm text-danger">You do not have admin privileges.</p>
          <Link
            href="/"
            className="mt-2 btn-primary btn-sm"
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
        <ShieldAlert className="h-6 w-6 text-foreground" />
        <h1 className="text-xl font-bold text-foreground">Admin Panel</h1>
        <span className="rounded-full bg-primary-solid px-3 py-0.5 text-xs font-medium text-white">
          {user?.username}
        </span>
      </div>

      {/* Admin Navigation Tabs — one row that scrolls sideways instead of
          wrapping into a ragged second line. */}
      <div className="overflow-x-auto rounded-[14px] border border-line bg-surface [scrollbar-width:thin]">
        <nav aria-label="Admin sections" className="flex min-w-max gap-1 p-1.5">
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
                aria-current={isActive ? "page" : undefined}
                className={[
                  "flex min-h-[40px] items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition whitespace-nowrap sm:px-4",
                  isActive
                    ? "bg-primary-solid text-white"
                    : "text-muted hover:bg-surface-2 hover:text-foreground",
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
      {/* Keyed on the route so each admin section gets the page entrance */}
      <div key={pathname} className="animate-fade-in-up">{children}</div>
    </div>
  );
}
