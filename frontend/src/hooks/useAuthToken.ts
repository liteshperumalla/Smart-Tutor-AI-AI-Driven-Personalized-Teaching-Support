"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AUTH_EXPIRED_EVENT,
  AUTH_STATE_CHANGED_EVENT,
  clearAuthToken,
  saveAuthToken,
  checkAuthStatus,
} from "@/lib/auth";
import { getApiBaseUrl } from "@/lib/api";

type Options = {
  redirectTo?: string;
};

/**
 * Hook for managing authentication state with HttpOnly cookies.
 *
 * The returned `token` is NOT a credential — it's a render flag with two
 * possible values:
 *   - "authenticated"  → backend confirmed a valid session via /auth/me
 *   - null             → no session (or expired / disabled)
 *
 * The real auth boundary lives server-side: every authenticated request
 * carries the HttpOnly access_token cookie, which the backend validates and
 * cross-checks against the database (backend/api/dependencies.py:
 * get_current_session). An XSS attacker who managed to flip this state to
 * "authenticated" would only see the admin UI render — every API call still
 * 401s because the attacker can't synthesize the HttpOnly cookie.
 *
 * Treat the value as "should we render gated UI?", never as "is this caller
 * authorized?". For the latter, just make the API call and handle 401.
 */
export function useAuthToken(options: Options = { redirectTo: "/login" }) {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [isChecking, setIsChecking] = useState(true);

  // Check authentication status on mount
  useEffect(() => {
    let cancelled = false;

    async function checkAuth() {
      try {
        const apiBaseUrl = getApiBaseUrl();
        const isAuthenticated = await checkAuthStatus(apiBaseUrl);

        if (!cancelled) {
          setToken(isAuthenticated ? "authenticated" : null);
          setIsChecking(false);

          if (!isAuthenticated && options.redirectTo) {
            router.replace(options.redirectTo);
          }
        }
      } catch {
        if (!cancelled) {
          setToken(null);
          setIsChecking(false);
          if (options.redirectTo) {
            router.replace(options.redirectTo);
          }
        }
      }
    }

    checkAuth();

    return () => {
      cancelled = true;
    };
  }, [options.redirectTo, router]);

  const updateToken = useCallback(
    (value: string | null) => {
      if (!value) {
        clearAuthToken();
        setToken(null);
        if (options.redirectTo) {
          router.replace(options.redirectTo);
        }
        return;
      }
      saveAuthToken(value);
      setToken("authenticated");
    },
    [options.redirectTo, router]
  );

  useEffect(() => {
    function handleAuthExpired() {
      updateToken(null);
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);

    function handleTokenChanged(event: Event) {
      const detail = (event as CustomEvent<string>).detail;
      setToken(detail === "authenticated" ? "authenticated" : null);
    }
    window.addEventListener(AUTH_STATE_CHANGED_EVENT, handleTokenChanged);

    return () => {
      window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
      window.removeEventListener(AUTH_STATE_CHANGED_EVENT, handleTokenChanged);
    };
  }, [updateToken]);

  return { token, setToken: updateToken, isChecking };
}
