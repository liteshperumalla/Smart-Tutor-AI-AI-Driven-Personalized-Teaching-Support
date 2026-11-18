/**
 * A re-run of the callback effect must not report a bad state after the
 * first run has used the nonce.
 */
import { render, screen, waitFor } from "@testing-library/react";
import GoogleCallbackPage from "../page";

const replace = jest.fn();
const state = btoa(JSON.stringify({ intent: "login", next: "/", nonce: "n1" }));
let params = new URLSearchParams({ code: "c", state });

jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => params,
}));

// Stub what the page reads instead of writing real cookies.
let cookieJar = "";

describe("Google callback state check", () => {
  afterAll(() => jest.restoreAllMocks());

  beforeEach(() => {
    params = new URLSearchParams({ code: "c", state });
    cookieJar = "google_oauth_nonce=n1";
    jest.spyOn(document, "cookie", "get").mockImplementation(() => cookieJar);
    jest.spyOn(document, "cookie", "set").mockImplementation(() => {});
    global.fetch = jest.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ user: {} }),
    }) as jest.Mock;
  });

  it("verifies once even when re-rendered with new search params", async () => {
    const { rerender } = render(<GoogleCallbackPage />);
    params = new URLSearchParams({ code: "c", state }); // new object, same values
    rerender(<GoogleCallbackPage />);
    await waitFor(() => expect(screen.getByText(/Signed in successfully/)).toBeInTheDocument());
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/expired/)).not.toBeInTheDocument();
  });

  it("explains how to recover when the nonce is missing", async () => {
    cookieJar = "";
    render(<GoogleCallbackPage />);
    expect(await screen.findByText(/choose Sign in with Google again/)).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
