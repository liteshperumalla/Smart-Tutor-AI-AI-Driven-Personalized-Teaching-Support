/** @jest-environment node */

import { NextRequest } from "next/server";

import { GET, POST } from "../[...path]/route";

describe("backend proxy contract", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn();
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
    (global.fetch as jest.Mock).mockResolvedValueOnce(
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

    const [target, init] = (global.fetch as jest.Mock).mock.calls[0] as [
      string,
      RequestInit & { headers: Headers },
    ];

    expect(target).toBe("http://localhost:8010/chat");
    expect(init.method).toBe("POST");
    expect(init.headers.get("cookie")).toContain("access_token=abc");
    expect(init.headers.get("x-csrf-token")).toBe("csrf123");
  });
});
