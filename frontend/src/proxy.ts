import { NextRequest, NextResponse } from "next/server";

/**
 * Optimistic auth gate (Next 16 Proxy, formerly middleware).
 *
 * Runs before any page renders: a request for an app page without session
 * cookies is redirected to /login?next=<path>. This only checks that the
 * HttpOnly cookies the backend sets through the /api/backend proxy are
 * present; it does not validate them. The real authorization boundary is
 * still the backend (every API call validates the access_token cookie), and
 * pages still call /auth/me and redirect on 401 for expired or revoked
 * sessions.
 */

// Pages anyone can open without signing in. Everything else requires a session.
const PUBLIC_PATHS = new Set<string>([
  "/",
  "/login",
  "/signup",
  "/about",
  "/verify",
  "/password-setup",
]);
const PUBLIC_PREFIXES = ["/password-reset/", "/auth/", "/shared/"];

const SESSION_COOKIES = ["access_token", "refresh_token"];

export function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATHS.has(pathname)) return true;
  return PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export default function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (isPublicPath(pathname)) return NextResponse.next();

  const hasSession = SESSION_COOKIES.some((name) => Boolean(request.cookies.get(name)?.value));
  if (hasSession) return NextResponse.next();

  const loginUrl = new URL("/login", request.nextUrl);
  loginUrl.searchParams.set("next", `${pathname}${search}`);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  // Skip API routes (the backend proxy enforces auth itself), Next internals
  // and static files.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|gif|svg|ico|webp|txt|xml|json|js|css|woff2?)$).*)"],
};
