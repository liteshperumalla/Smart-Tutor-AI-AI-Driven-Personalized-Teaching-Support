import { NextRequest } from "next/server";

// Allow larger body sizes for file uploads
export const config = {
  api: {
    bodyParser: false,
  },
};

// Increase body size limit for file uploads
export const maxDuration = 60;

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
  const targetPath = path?.join("/") ?? "";
  const search = request.nextUrl.search || "";
  const url = `${BACKEND_BASE_URL.replace(/\/$/, "")}/${targetPath}${search}`;

  const headers = new Headers(request.headers);
  headers.delete("host");

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };

  if (request.body) {
    init.body = request.body as any;
    (init as any).duplex = "half";
  }

  const response = await fetch(url, init);
  const proxyHeaders = new Headers(response.headers);
  proxyHeaders.delete("content-security-policy");

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
