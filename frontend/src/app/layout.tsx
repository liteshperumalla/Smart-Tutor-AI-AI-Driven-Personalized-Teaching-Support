import type { Metadata } from "next";
import localFont from "next/font/local";
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

// The Inter, Geist Mono and Space Grotesk files live in ./fonts (latin
// subset, variable weight, OFL licensed) instead of coming from
// next/font/google, so builds no longer download them from Google Fonts.

// Body fallback until the self-hosted Cabinet Grotesk files are in
// public/fonts (see the @font-face rules in globals.css).
const inter = localFont({
  src: "./fonts/Inter-Variable-latin.woff2",
  variable: "--font-inter",
  weight: "100 900",
  display: "swap",
});

const geistMono = localFont({
  src: "./fonts/GeistMono-Variable-latin.woff2",
  variable: "--font-geist-mono",
  weight: "100 900",
  display: "swap",
  fallback: ["ui-monospace", "monospace"],
  adjustFontFallback: false,
});

// Heading fallback behind Clash Display.
const spaceGrotesk = localFont({
  src: "./fonts/SpaceGrotesk-Variable-latin.woff2",
  variable: "--font-space-grotesk",
  weight: "300 700",
  display: "swap",
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
    // "main" links sit at the top of the sidebar, "manage" in a labelled
    // group under them, "more" in the footer. Profile is the user card.
    { href: "/", label: "Home", section: "main" as const },
    { href: "/chat", label: "Chat", section: "main" as const },
    { href: "/quiz", label: "Quiz", section: "main" as const },
    { href: "/resources", label: "Resources", section: "main" as const },
    { href: "/appointments", label: "Appointments", section: "main" as const },
    { href: "/instructor", label: "Teaching", section: "manage" as const, instructorOnly: true },
    { href: "/admin", label: "Admin", section: "manage" as const, adminOnly: true },
    { href: "/about", label: "About", section: "more" as const },
    { href: "/feedback", label: "Feedback", section: "more" as const },
  ];

  return (
    // Font variables sit on <html> because globals.css composes them into
    // --font-display / --font-body on :root.
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${geistMono.variable} ${spaceGrotesk.variable}`}>
      <head>
        {/* Self-hosted brand fonts (public/fonts, @font-face in globals.css):
            preload the two faces nearly every page paints with. */}
        <link rel="preload" href="/fonts/ClashDisplay-Bold.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
        <link rel="preload" href="/fonts/CabinetGrotesk-Regular.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
      </head>
      <body className="antialiased">
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
