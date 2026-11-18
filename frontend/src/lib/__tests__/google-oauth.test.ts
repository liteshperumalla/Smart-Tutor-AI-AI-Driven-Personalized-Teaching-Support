/**
 * The Google state nonce must be readable on the callback's origin.
 * @jest-environment jsdom
 */
import { beginGoogleSignIn, readGoogleNonceCookie } from "@/lib/google-oauth";

const ENV = process.env;

function clearCookie() {
  document.cookie = "google_oauth_nonce=; path=/; max-age=0";
}

describe("beginGoogleSignIn", () => {
  beforeEach(() => {
    clearCookie();
    process.env = { ...ENV, NEXT_PUBLIC_GOOGLE_CLIENT_ID: "client-1" };
  });
  afterAll(() => {
    process.env = ENV;
  });

  it("returns null when Google sign-in isn't configured", () => {
    delete process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    expect(beginGoogleSignIn("login", "/")).toBeNull();
  });

  it("on the callback's origin, saves a nonce and puts the same one in the state", () => {
    // jsdom runs on http://localhost, which always uses its own callback.
    const url = new URL(beginGoogleSignIn("signup", "/chat") as string);
    expect(url.origin).toBe("https://accounts.google.com");
    expect(url.searchParams.get("redirect_uri")).toBe("http://localhost/auth/google/callback");
    const state = JSON.parse(atob(url.searchParams.get("state") as string));
    expect(state).toMatchObject({ intent: "signup", next: "/chat" });
    expect(state.nonce).toBe(readGoogleNonceCookie());
  });

  it("each attempt gets a fresh nonce", () => {
    const first = JSON.parse(atob(new URL(beginGoogleSignIn("login", "/") as string).searchParams.get("state")!));
    const second = JSON.parse(atob(new URL(beginGoogleSignIn("login", "/") as string).searchParams.get("state")!));
    expect(first.nonce).not.toBe(second.nonce);
    expect(readGoogleNonceCookie()).toBe(second.nonce);
  });
});
