import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { SiteChrome } from "@/components/site-chrome";
import { ThemeProvider } from "@/context/theme-context";
import { ErrorBoundary } from "@/components/error-boundary";
import { ToastProvider } from "@/components/toast-provider";
import { AnnouncementToaster } from "@/components/announcement-toaster";
import { PostHogProvider } from "@/components/posthog-provider";
import { SpeedInsights } from "@vercel/speed-insights/next";

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
  description: "Modern FastAPI + Next.js experience for INFO 5731",
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
    { href: "/evaluation", label: "Evaluation", adminOnly: true },
    { href: "/admin", label: "Admin", adminOnly: true },
  ];

  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <PostHogProvider>
          <ErrorBoundary>
            <ThemeProvider>
              <ToastProvider />
              <AnnouncementToaster />
              <SiteChrome navLinks={navLinks}>{children}</SiteChrome>
            </ThemeProvider>
          </ErrorBoundary>
        </PostHogProvider>
        <SpeedInsights />
      </body>
    </html>
  );
}
