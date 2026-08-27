import { getGoogleOAuthRedirectUri } from "../google-oauth";

describe("getGoogleOAuthRedirectUri", () => {
  it("uses the active local origin instead of a production callback", () => {
    expect(["localhost", "127.0.0.1", "::1"]).toContain(window.location.hostname);

    expect(
      getGoogleOAuthRedirectUri("https://smartaitutor.com/auth/google/callback")
    ).toBe(`${window.location.origin}/auth/google/callback`);
  });
});
