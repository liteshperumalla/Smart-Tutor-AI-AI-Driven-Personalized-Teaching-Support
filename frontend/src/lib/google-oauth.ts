const GOOGLE_CALLBACK_PATH = "/auth/google/callback";
export const GOOGLE_START_PATH = "/auth/google/start";
export const GOOGLE_NONCE_COOKIE = "google_oauth_nonce";

export type GoogleIntent = "login" | "signup";

/**
 * Use the configured production callback, but always return the active local
 * origin during development so the authorization and token-exchange steps use
 * the same redirect URI.
 */
export function getGoogleOAuthRedirectUri(configuredRedirect?: string): string | undefined {
  if (typeof window === "undefined") {
    return configuredRedirect;
  }

  const fallbackRedirect = `${window.location.origin}${GOOGLE_CALLBACK_PATH}`;
  const isLocal = ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);

  return isLocal ? fallbackRedirect : configuredRedirect || fallbackRedirect;
}

function generateNonce(): string {
  if (typeof window !== "undefined" && window.crypto?.getRandomValues) {
    return Array.from(window.crypto.getRandomValues(new Uint8Array(16)))
      .map((value) => value.toString(16).padStart(2, "0"))
      .join("");
  }
  return `${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
}

function originOf(url: string): string | null {
  try {
    return new URL(url).origin;
  } catch {
    return null;
  }
}

/**
 * Where "Sign in with Google" should send the browser, or null when Google
 * sign-in isn't configured.
 *
 * The state nonce lives in a cookie, and cookies belong to one origin. When
 * this page is on another origin than the OAuth callback (a *.vercel.app
 * alias, www vs the bare domain), a nonce saved here is invisible to the
 * callback, which then reports "Invalid or expired OAuth state". So from
 * another origin, go to the start page on the callback's origin first; it
 * saves the nonce there and continues to Google.
 *
 * On the callback's origin this saves a fresh nonce now, at the click, so
 * the cookie always matches the state of the attempt being made.
 */
export function beginGoogleSignIn(intent: GoogleIntent, next: string): string | null {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  const redirectUri = getGoogleOAuthRedirectUri(process.env.NEXT_PUBLIC_GOOGLE_REDIRECT_URI);
  if (!clientId || !redirectUri) return null;

  const callbackOrigin = originOf(redirectUri);
  if (callbackOrigin && callbackOrigin !== window.location.origin) {
    const start = new URL(GOOGLE_START_PATH, callbackOrigin);
    start.search = new URLSearchParams({ intent, next }).toString();
    return start.toString();
  }

  const nonce = generateNonce();
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${GOOGLE_NONCE_COOKIE}=${nonce}; path=/; SameSite=Lax; max-age=600${secure}`;

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: "openid email profile",
    access_type: "offline",
    prompt: "consent",
    state: btoa(JSON.stringify({ intent, nonce, next })),
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
}

export function readGoogleNonceCookie(): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${GOOGLE_NONCE_COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function clearGoogleNonceCookie(): void {
  document.cookie = `${GOOGLE_NONCE_COOKIE}=; path=/; max-age=0`;
}
