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

    expect(target).toBe(`${expectedBackendBase}/chat`);
    expect(init.method).toBe("POST");
    expect(init.headers.get("cookie")).toContain("access_token=abc");
    expect(init.headers.get("x-csrf-token")).toBe("csrf123");
  });
});
