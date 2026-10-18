import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { SiteChrome } from "@/components/site-chrome";
import { ThemeProvider } from "@/context/theme-context";
import { ErrorBoundary } from "@/components/error-boundary";
import { ToastProvider } from "@/components/toast-provider";
import { AnnouncementToaster } from "@/components/announcement-toaster";
import { MaintenanceBanner } from "@/components/maintenance-banner";
import { ActiveCourseProvider } from "@/components/active-course-provider";
import { PostHogProvider } from "@/components/posthog-provider";
import { SpeedInsights } from "@vercel/speed-insights/next";
import { Analytics } from "@vercel/analytics/next";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Smart AI Tutor",
  description: "Multi-course AI tutoring, targeted practice, and measurable learning mastery.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const navLinks = [
    { href: "/", label: "Home" },
    { href: "/chat", label: "Chat" },
    { href: "/quiz", label: "Quiz" },
    { href: "/appointments", label: "Appointments" },
    { href: "/resources", label: "Resources" },
    { href: "/about", label: "About" },
    { href: "/feedback", label: "Feedback" },
    { href: "/profile", label: "Profile" },
    { href: "/instructor", label: "Teaching", instructorOnly: true },
    { href: "/evaluation", label: "Evaluation", adminOnly: true },
    { href: "/admin", label: "Admin", adminOnly: true },
  ];

  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        {/* Pre-paint theme: set the .dark/.theme-dark class before first paint so
            an OS-dark or previously-chosen-dark user doesn't flash a light screen.
            Mirrors theme-context.tsx (same storage key + initial logic). */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var k="smart-ai-tutor-theme",s=localStorage.getItem(k);var d=s==="dark"||(s!=="light"&&window.matchMedia("(prefers-color-scheme: dark)").matches);if(d){document.documentElement.classList.add("dark","theme-dark");}}catch(e){}})();`,
          }}
        />
        <PostHogProvider>
          <ErrorBoundary>
            <ThemeProvider>
              <ToastProvider />
              <AnnouncementToaster />
              <MaintenanceBanner />
              <ActiveCourseProvider>
                <MaintenanceBanner />
                <SiteChrome navLinks={navLinks}>{children}</SiteChrome>
              </ActiveCourseProvider>
            </ThemeProvider>
          </ErrorBoundary>
        </PostHogProvider>
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
