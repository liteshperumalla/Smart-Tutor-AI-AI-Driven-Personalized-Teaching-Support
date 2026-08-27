import { NextRequest } from "next/server";
import { posix } from "path";
import { getMaintenanceState } from "@/lib/maintenance";

// Increase timeout for long-running operations like initial S3 index download (can take up to 3-4 minutes)
export const maxDuration = 300;

const BACKEND_BASE_URL =
  process.env.BACKEND_API_BASE_URL ||
  (process.env.NODE_ENV === "production" ? "" : "http://localhost:8010");

const BACKEND_TIMEOUT_MS = 120_000;
const VERSIONED_API_PREFIX = "/api/v1";
const INFRASTRUCTURE_PATHS = new Set(["/health", "/ready", "/metrics", "/csrf-token"]);
const PUBLIC_PATHS = new Set(["/health", "/home/overview", "/home/announcements"]);

// Only forward headers that the backend needs to serve the request. In
// particular, never forward client-provided X-Forwarded-* or X-Real-IP values:
// Vercel/Next is the trusted proxy boundary and accepting those values lets a
// browser spoof security logs and IP-based controls.
const REQUEST_HEADER_ALLOWLIST = new Set([
  "accept",
  "accept-language",
  "authorization",
  "content-type",
  "cookie",
  "if-modified-since",
  "if-none-match",
  "range",
  "user-agent",
  "x-request-id",
]);

// Exclude hop-by-hop headers and backend transport details. Set-Cookie is
// copied separately because it can occur more than once.
const RESPONSE_HEADER_ALLOWLIST = new Set([
  "cache-control",
  "content-disposition",
  "content-encoding",
  "content-language",
  "content-length",
  "content-range",
  "content-security-policy",
  "content-type",
  "etag",
  "last-modified",
  "location",
  "referrer-policy",
  "retry-after",
  "vary",
  "www-authenticate",
  "x-content-type-options",
  "x-frame-options",
]);

// Path traversal is blocked above; admin auth is enforced by the backend's
// get_admin_session dependency (role == "Admin"). No need to block here.
const BLOCKED_PATH_PREFIXES: string[] = [];

type RouteParams = { path?: string[] };
type RouteContext = { params: RouteParams } | { params: Promise<RouteParams> };

function splitSetCookieHeader(headerValue: string): string[] {
  const cookies: string[] = [];
  let current = "";
  let inExpires = false;

  for (let index = 0; index < headerValue.length; index += 1) {
    const char = headerValue[index];
    const next = headerValue.slice(index, index + 8).toLowerCase();

    if (!inExpires && next === "expires=") {
      inExpires = true;
    }

    if (char === "," && !inExpires) {
      if (current.trim()) {
        cookies.push(current.trim());
      }
      current = "";
      continue;
    }

    if (char === ";" && inExpires) {
      inExpires = false;
    }

    current += char;
  }

  if (current.trim()) {
    cookies.push(current.trim());
  }

  return cookies;
}

function appendResponseHeaders(target: Headers, source: Headers) {
  for (const [key, value] of source.entries()) {
    const normalizedKey = key.toLowerCase();
    if (normalizedKey === "set-cookie" || !RESPONSE_HEADER_ALLOWLIST.has(normalizedKey)) {
      continue;
    }
    target.append(key, value);
  }

  const headersWithSetCookie = source as Headers & {
    getSetCookie?: () => string[];
  };
  const setCookies =
    typeof headersWithSetCookie.getSetCookie === "function"
      ? headersWithSetCookie.getSetCookie()
      : splitSetCookieHeader(source.get("set-cookie") ?? "");

  for (const cookie of setCookies) {
    target.append("set-cookie", cookie);
  }
}

function jsonError(status: number, detail: string) {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

function backendPathFor(clientPath: string): string {
  return INFRASTRUCTURE_PATHS.has(clientPath)
    ? clientPath
    : `${VERSIONED_API_PREFIX}${clientPath}`;
}

function clientPathForBackendLocation(path: string): string {
  return path.startsWith(VERSIONED_API_PREFIX)
    ? path.slice(VERSIONED_API_PREFIX.length) || "/"
    : path;
}

async function resolvePath(paramsOrPromise: RouteParams | Promise<RouteParams>) {
  const resolved =
    typeof (paramsOrPromise as Promise<RouteParams>).then === "function"
      ? await (paramsOrPromise as Promise<RouteParams>)
      : (paramsOrPromise as RouteParams);
  return resolved?.path ?? [];
}

async function proxyRequest(request: NextRequest, path: string[]) {
  if (!BACKEND_BASE_URL) {
    return jsonError(503, "Backend API is not configured");
  }
  // Reject any path segment containing traversal sequences, encoded dots, or null bytes.
  const segments = path ?? [];
  for (const segment of segments) {
    const decoded = decodeURIComponent(segment);
    if (
      decoded.includes("..") ||
      decoded.includes("\0") ||
      /%2e/i.test(segment) ||
      /%00/i.test(segment)
    ) {
      return jsonError(400, "Bad Request");
    }
  }

  // Normalize the path using posix.normalize to collapse any ".." traversal segments,
  // then ensure it never escapes the root ("/").
  const rawPath = "/" + (segments.join("/") ?? "");
  const normalizedPath = posix.normalize(rawPath).replace(/^\/+/, "");

  // Belt-and-suspenders: block requests that target admin routes directly
  const normalizedWithSlash = "/" + normalizedPath;
  for (const prefix of BLOCKED_PATH_PREFIXES) {
    if (
      normalizedWithSlash === prefix ||
      normalizedWithSlash.startsWith(prefix + "/")
    ) {
      return jsonError(403, "Forbidden");
    }
  }

  // Defense in depth: require an auth cookie to be present before forwarding.
  // Public endpoints that power the landing page should remain accessible.
  const hasAuthCookie =
    request.cookies.has("access_token") || request.cookies.has("refresh_token");
  const isAuthPath =
    normalizedWithSlash.startsWith("/auth/") ||
    normalizedWithSlash === "/auth";
  const isPublicPath = PUBLIC_PATHS.has(normalizedWithSlash);
  if (!hasAuthCookie && !isAuthPath && !isPublicPath) {
    return jsonError(401, "Unauthorized");
  }

  const search = request.nextUrl.search || "";
  const backendPath = backendPathFor(normalizedWithSlash);
  const url = `${BACKEND_BASE_URL.replace(/\/$/, "")}${backendPath}${search}`;

  const headers = new Headers();
  for (const [key, value] of request.headers.entries()) {
    if (REQUEST_HEADER_ALLOWLIST.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  }

  // IMPORTANT: Forward cookies for authentication
  const cookies = request.headers.get("cookie");
  if (cookies) {
    headers.set("cookie", cookies);
  }

  // CSRF double-submit: for state-changing methods, read the csrf_token cookie
  // and forward it as X-CSRF-Token so the backend can validate it.
  const MUTATION_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
  if (MUTATION_METHODS.has(request.method)) {
    const csrfToken = request.cookies.get("csrf_token")?.value;
    if (csrfToken) {
      headers.set("X-CSRF-Token", csrfToken);
    }
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };

  if (request.body) {
    init.body = request.body as ReadableStream;
    (init as Record<string, unknown>).duplex = "half";
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return jsonError(504, "The backend took too long to respond");
    }
    // The backend is unreachable. This is expected during the scheduled
    // stop window (see lib/maintenance + .github/workflows/ec2-schedule.yml),
    // and otherwise indicates a real outage. Either way, return a clean 503
    // with a classified reason instead of letting the error surface as a 500.
    const { isDown, resumesLabel } = getMaintenanceState();
    return new Response(
      JSON.stringify({
        detail: isDown
          ? `Scheduled maintenance — the AI tutor is offline outside Mon–Fri 9 AM–5 PM CT.${resumesLabel ? ` Service resumes ${resumesLabel}.` : ""}`
          : "Backend temporarily unavailable. Please try again shortly.",
        reason: isDown ? "scheduled_maintenance" : "backend_unavailable",
        resumes: isDown ? resumesLabel : null,
      }),
      {
        status: 503,
        headers: {
          "Content-Type": "application/json",
          "Retry-After": "300",
        },
      }
    );
  } finally {
    clearTimeout(timeout);
  }
  const proxyHeaders = new Headers();
  appendResponseHeaders(proxyHeaders, response.headers);
  // NOTE: Do NOT delete the Content-Security-Policy header — removing it would
  // strip the backend's security directives from every proxied response.

  // Rewrite redirect Location headers to go through the proxy
  const location = proxyHeaders.get("location");
  if (location) {
    // If the location is a relative path starting with /files/, rewrite it to go through the proxy
    if (location.startsWith("/files/")) {
      const newLocation = `/api/backend${location}`;
      proxyHeaders.set("location", newLocation);
    }
    // If it's a redirect to the backend directly, rewrite to go through proxy
    else if (location.startsWith(BACKEND_BASE_URL)) {
      const pathPart = clientPathForBackendLocation(location.replace(BACKEND_BASE_URL, ""));
      const newLocation = `/api/backend${pathPart}`;
      proxyHeaders.set("location", newLocation);
    }
  }

  return new Response(response.body, {
    status: response.status,
    headers: proxyHeaders,
  });
}

export async function GET(request: NextRequest, context: RouteContext) {
  const path = await resolvePath(context.params);
  return proxyRequest(request, path);
}

export async function POST(request: NextRequest, context: RouteContext) {
  const path = await resolvePath(context.params);
  return proxyRequest(request, path);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  const path = await resolvePath(context.params);
  return proxyRequest(request, path);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  const path = await resolvePath(context.params);
  return proxyRequest(request, path);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  const path = await resolvePath(context.params);
  return proxyRequest(request, path);
}

export async function HEAD(request: NextRequest, context: RouteContext) {
  const path = await resolvePath(context.params);
  return proxyRequest(request, path);
}

export async function OPTIONS(request: NextRequest, context: RouteContext) {
  const path = await resolvePath(context.params);
  return proxyRequest(request, path);
}
