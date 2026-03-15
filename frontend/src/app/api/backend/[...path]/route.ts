import { NextRequest } from "next/server";
import { posix } from "path";

// Increase timeout for long-running operations like initial S3 index download (can take up to 3-4 minutes)
export const maxDuration = 300;

const BACKEND_BASE_URL =
  process.env.BACKEND_API_BASE_URL || "http://localhost:8010";

// Path traversal is blocked above; admin auth is enforced by the backend's
// get_admin_session dependency (role == "Admin"). No need to block here.
const BLOCKED_PATH_PREFIXES: string[] = [];

type RouteParams = { path?: string[] };
type RouteContext = { params: RouteParams } | { params: Promise<RouteParams> };

async function resolvePath(paramsOrPromise: RouteParams | Promise<RouteParams>) {
  const resolved =
    typeof (paramsOrPromise as Promise<RouteParams>).then === "function"
      ? await (paramsOrPromise as Promise<RouteParams>)
      : (paramsOrPromise as RouteParams);
  return resolved?.path ?? [];
}

async function proxyRequest(request: NextRequest, path: string[]) {
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
      return new Response(JSON.stringify({ detail: "Bad Request" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
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
      return new Response(JSON.stringify({ detail: "Forbidden" }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      });
    }
  }

  // Defense in depth: require an auth cookie to be present before forwarding.
  // Public endpoints that power the landing page should remain accessible.
  const hasAuthCookie =
    request.cookies.has("access_token") || request.cookies.has("refresh_token");
  const isAuthPath =
    normalizedWithSlash.startsWith("/auth/") ||
    normalizedWithSlash === "/auth";
  const isPublicPath =
    normalizedWithSlash === "/home/overview" ||
    normalizedWithSlash === "/home/announcements";
  if (!hasAuthCookie && !isAuthPath && !isPublicPath) {
    return new Response(JSON.stringify({ detail: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const search = request.nextUrl.search || "";
  const url = `${BACKEND_BASE_URL.replace(/\/$/, "")}/${normalizedPath}${search}`;

  const headers = new Headers(request.headers);
  headers.delete("host");

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

  const response = await fetch(url, init);
  const proxyHeaders = new Headers(response.headers);
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
      const pathPart = location.replace(BACKEND_BASE_URL, "");
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
