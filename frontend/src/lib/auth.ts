"use client";

/**
 * Authentication utilities for Smart AI Tutor
 *
 * SECURITY: This application uses HttpOnly cookies for authentication.
 * - Tokens are stored in secure HttpOnly cookies by the backend
 * - JavaScript CANNOT access these cookies (XSS protection)
 * - Cookies are automatically sent with API requests
 * - Frontend does NOT store tokens in localStorage or regular cookies
 */

export const AUTH_EXPIRED_EVENT = "smart-ai-tutor-auth-expired";
export const AUTH_STATE_CHANGED_EVENT = "smart-ai-tutor-auth-changed";

/**
 * SECURITY: This function is now a no-op.
 * Tokens are managed by HttpOnly cookies set by the backend.
 * Frontend should NOT attempt to store tokens.
 *
 * @deprecated Use backend HttpOnly cookies instead
 */
export function saveAuthToken(_token: string) {
  if (typeof window === "undefined") return;

  // SECURITY: Do NOT store tokens in localStorage or cookies
  // Backend sets HttpOnly cookies automatically on login

  // Dispatch event to notify components that authentication state changed
  window.dispatchEvent(
    new CustomEvent(AUTH_STATE_CHANGED_EVENT, { detail: "authenticated" })
  );
}

/**
 * SECURITY: Cannot access HttpOnly cookies from JavaScript.
 * Authentication state is determined by making API calls.
 *
 * @deprecated HttpOnly cookies are not accessible to JavaScript
 * @returns null (always, since we can't read HttpOnly cookies)
 */
export function getAuthToken(): string | null {
  // SECURITY: HttpOnly cookies cannot be accessed by JavaScript
  // This is intentional for XSS protection
  return null;
}

/**
 * Clear authentication state.
 * The actual logout must be done via API call to clear HttpOnly cookies.
 */
export function clearAuthToken() {
  if (typeof window === "undefined") return;

  // Dispatch event to notify components that user logged out
  window.dispatchEvent(
    new CustomEvent(AUTH_STATE_CHANGED_EVENT, { detail: "unauthenticated" })
  );
}

/**
 * Check if user is authenticated by making an API call.
 * Since we can't read HttpOnly cookies, we need to call the backend.
 *
 * @param apiBaseUrl - Base URL of the API
 * @returns Promise<boolean> - true if authenticated, false otherwise
 */
export async function checkAuthStatus(apiBaseUrl: string): Promise<boolean> {
  try {
    const response = await fetch(`${apiBaseUrl}/auth/me`, {
      method: "GET",
      credentials: "include", // IMPORTANT: Send HttpOnly cookies
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      return false;
    }

    const payload = (await response.json().catch(() => ({}))) as {
      user?: Record<string, unknown> | null;
    };

    return Boolean(payload.user);
  } catch {
    return false;
  }
}
