import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker runs the standalone server, while Vercel packages Next.js output
  // itself. Enabling standalone on Vercel makes its post-build file lookup
  // fail because the expected runtime manifest is not emitted there.
  output: process.env.VERCEL ? undefined : "standalone",
  turbopack: {
    // Keep Turbopack scoped to this app when another lockfile exists above it.
    root: process.cwd(),
  },
  reactStrictMode: true,
  reactCompiler: true,
  poweredByHeader: false,

  // Compiler optimizations
  compiler: {
    removeConsole: process.env.NODE_ENV === "production" ? {
      exclude: ["error", "warn"],
    } : false,
  },

  // Security headers
  async headers() {
    const isProduction = process.env.NODE_ENV === "production";
    // Check if we're running on localhost/development
    const isLocalhost = process.env.NEXT_PUBLIC_APP_BASE_URL?.includes('localhost') ||
                        process.env.HOSTNAME === 'localhost' ||
                        !process.env.NEXT_PUBLIC_APP_BASE_URL?.startsWith('https');
    const developmentConnectSources = isProduction
      ? []
      : [
          "http://localhost:8010",
          "http://localhost:8000",
          "http://backend:8000",
          "https://localhost:8010",
          "https://localhost:8000",
          "https://backend:8000",
        ];

    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://accounts.google.com https://www.googletagmanager.com https://us-assets.i.posthog.com",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com https://api.fontshare.com",
              "img-src 'self' data: https: blob:",
              `connect-src 'self' https://accounts.google.com https://us.i.posthog.com https://us-assets.i.posthog.com ${developmentConnectSources.join(" ")}`.trim(),
              "frame-src 'self' https://accounts.google.com",
              "object-src 'none'",
              "base-uri 'self'",
              "form-action 'self'",
              "frame-ancestors 'none'",
              // Only use upgrade-insecure-requests in production with HTTPS
              ...(isLocalhost ? [] : ["upgrade-insecure-requests"])
            ].join("; ")
          },
          {
            key: "X-DNS-Prefetch-Control",
            value: "on",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
          {
            key: "X-Frame-Options",
            value: "DENY",  // Changed from SAMEORIGIN to DENY for better security
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "X-XSS-Protection",
            value: "1; mode=block",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },

  // Backend proxy is handled by /api/backend/[...path]/route.ts
  // which supports long-running requests (maxDuration=300s).
  // Do NOT add rewrites for /api/backend/* here — they conflict
  // with the route handler and use a shorter proxy timeout.
};

export default nextConfig;
