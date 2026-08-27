/** @jest-environment node */

import { NextRequest } from "next/server";

import { GET, POST } from "../[...path]/route";

describe("backend proxy contract", () => {
  let fetchSpy: jest.SpiedFunction<typeof fetch>;

  beforeEach(() => {
    jest.clearAllMocks();
    fetchSpy = jest.spyOn(global, "fetch").mockImplementation(jest.fn());
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it("blocks path traversal attempts", async () => {
    const request = new NextRequest("http://localhost:4000/api/backend/%2e%2e/secrets");

    const response = await GET(request, { params: { path: ["%2e%2e", "secrets"] } });

    expect(response.status).toBe(400);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("rejects unauthenticated non-public requests before proxying", async () => {
    const request = new NextRequest("http://localhost:4000/api/backend/chat");

    const response = await GET(request, { params: { path: ["chat"] } });

    expect(response.status).toBe(401);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("forwards auth cookies and csrf header for mutation requests", async () => {
    fetchSpy.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: {
          "content-type": "application/json",
          "set-cookie": "session=value; Path=/; HttpOnly",
        },
      })
    );

    const request = new NextRequest("http://localhost:4000/api/backend/chat", {
      method: "POST",
      headers: {
        cookie: "access_token=abc; csrf_token=csrf123",
      },
      body: JSON.stringify({ message: "hello" }),
    });

    const response = await POST(request, { params: { path: ["chat"] } });

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);

    const [target, init] = fetchSpy.mock.calls[0] as [
      string,
      RequestInit & { headers: Headers },
    ];

    const expectedBackendBase =
      process.env.BACKEND_API_BASE_URL ?? "http://localhost:8010";

    expect(target).toBe(`${expectedBackendBase}/api/v1/chat`);
    expect(init.method).toBe("POST");
    expect(init.headers.get("cookie")).toContain("access_token=abc");
    expect(init.headers.get("x-csrf-token")).toBe("csrf123");
  });

  it("keeps infrastructure health public and unversioned", async () => {
    fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));

    const response = await GET(
      new NextRequest("http://localhost:4000/api/backend/health"),
      { params: { path: ["health"] } }
    );

    const expectedBackendBase = process.env.BACKEND_API_BASE_URL ?? "http://localhost:8010";
    expect(response.status).toBe(200);
    expect(fetchSpy.mock.calls[0][0]).toBe(`${expectedBackendBase}/health`);
  });

  it("drops client-controlled forwarding headers", async () => {
    fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    const request = new NextRequest("http://localhost:4000/api/backend/auth/me", {
      headers: {
        cookie: "access_token=abc",
        "x-forwarded-for": "203.0.113.1",
        "x-real-ip": "203.0.113.2",
      },
    });

    await GET(request, { params: { path: ["auth", "me"] } });
    const [, init] = fetchSpy.mock.calls[0] as [string, RequestInit & { headers: Headers }];
    expect(init.headers.get("x-forwarded-for")).toBeNull();
    expect(init.headers.get("x-real-ip")).toBeNull();
  });

  it("returns a gateway error when the backend is unavailable", async () => {
    fetchSpy.mockRejectedValueOnce(new TypeError("network down"));
    const response = await GET(
      new NextRequest("http://localhost:4000/api/backend/home/overview"),
      { params: { path: ["home", "overview"] } }
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({ detail: "The backend is temporarily unavailable" });
  });
});
