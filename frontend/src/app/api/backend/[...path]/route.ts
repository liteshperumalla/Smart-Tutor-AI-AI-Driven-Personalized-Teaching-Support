import { NextRequest } from "next/server";

// Allow larger body sizes for file uploads
export const config = {
  api: {
    bodyParser: false,
  },
};

// Increase timeout for long-running operations like initial S3 index download (can take up to 3-4 minutes)
export const maxDuration = 300;

const BACKEND_BASE_URL =
  process.env.BACKEND_API_BASE_URL || "http://localhost:8010";

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
  console.log("[PROXY DEBUG] proxyRequest called with path:", path);
  const targetPath = path?.join("/") ?? "";
  const search = request.nextUrl.search || "";
  const url = `${BACKEND_BASE_URL.replace(/\/$/, "")}/${targetPath}${search}`;
  console.log("[PROXY DEBUG] Proxying to URL:", url);

  const headers = new Headers(request.headers);
  headers.delete("host");

  // IMPORTANT: Forward cookies for authentication
  const cookies = request.headers.get("cookie");
  if (cookies) {
    headers.set("cookie", cookies);
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
  proxyHeaders.delete("content-security-policy");

  // DEBUG: Log original location header
  const originalLocation = proxyHeaders.get("location");
  console.log("[PROXY DEBUG] Original Location:", originalLocation);

  // Rewrite redirect Location headers to go through the proxy
  const location = proxyHeaders.get("location");
  if (location) {
    // If the location is a relative path starting with /files/, rewrite it to go through the proxy
    if (location.startsWith("/files/")) {
      const newLocation = `/api/backend${location}`;
      console.log("[PROXY DEBUG] Rewritten Location:", newLocation);
      proxyHeaders.set("location", newLocation);
    }
    // If it's a redirect to the backend directly, rewrite to go through proxy
    else if (location.startsWith(BACKEND_BASE_URL)) {
      const pathPart = location.replace(BACKEND_BASE_URL, "");
      const newLocation = `/api/backend${pathPart}`;
      console.log("[PROXY DEBUG] Rewritten Location:", newLocation);
      proxyHeaders.set("location", newLocation);
    }
  }

  // DEBUG: Log final headers
  console.log("[PROXY DEBUG] Final Location:", proxyHeaders.get("location"));

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
