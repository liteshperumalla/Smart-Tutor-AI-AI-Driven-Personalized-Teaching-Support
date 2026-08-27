const GOOGLE_CALLBACK_PATH = "/auth/google/callback";

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
