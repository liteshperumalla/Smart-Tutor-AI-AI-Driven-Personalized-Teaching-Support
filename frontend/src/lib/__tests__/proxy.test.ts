/**
 * @jest-environment node
 */
import { NextRequest } from "next/server";
import proxy, { isPublicPath } from "../../proxy";

function requestFor(path: string, cookies: Record<string, string> = {}) {
  const request = new NextRequest(new URL(path, "http://localhost:4000"));
  for (const [name, value] of Object.entries(cookies)) request.cookies.set(name, value);
  return request;
}

describe("auth proxy", () => {
  it("keeps public pages open", () => {
    for (const path of ["/", "/login", "/signup", "/about", "/help", "/password-reset/request", "/shared/abc123", "/auth/google/callback"]) {
      expect(isPublicPath(path)).toBe(true);
    }
  });

  it.each(["/profile", "/feedback", "/resources", "/appointments", "/quiz", "/chat", "/code", "/admin", "/admin/users"])(
    "redirects %s to login when signed out, preserving the destination",
    (path) => {
      const response = proxy(requestFor(`${path}?tab=1`));
      expect(response.status).toBe(307);
      const location = new URL(response.headers.get("location") ?? "");
      expect(location.pathname).toBe("/login");
      expect(location.searchParams.get("next")).toBe(`${path}?tab=1`);
    }
  );

  it("lets a request with a session cookie through", () => {
    expect(proxy(requestFor("/profile", { access_token: "x" })).headers.get("location")).toBeNull();
    expect(proxy(requestFor("/chat", { refresh_token: "y" })).headers.get("location")).toBeNull();
  });

  it("does not treat the csrf cookie alone as a session", () => {
    expect(proxy(requestFor("/profile", { csrf_token: "z" })).status).toBe(307);
  });
});
