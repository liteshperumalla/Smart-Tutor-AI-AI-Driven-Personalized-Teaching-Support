"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AUTH_EXPIRED_EVENT,
  AUTH_TOKEN_CHANGED_EVENT,
  clearAuthToken,
  getAuthToken,
  saveAuthToken,
} from "@/lib/auth";

type Options = {
  redirectTo?: string;
};

export function useAuthToken(options: Options = { redirectTo: "/login" }) {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(() => getAuthToken());

  useEffect(() => {
    if (!token && options.redirectTo) {
      router.replace(options.redirectTo);
    }
  }, [token, options.redirectTo, router]);

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
      setToken(value);
    },
    [options.redirectTo, router]
  );

  useEffect(() => {
    function handleAuthExpired() {
      updateToken(null);
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
    function handleTokenChanged(event: Event) {
      const detail = (event as CustomEvent<string | null>).detail;
      setToken(detail || null);
    }
    window.addEventListener(AUTH_TOKEN_CHANGED_EVENT, handleTokenChanged);
    return () => {
      window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
      window.removeEventListener(AUTH_TOKEN_CHANGED_EVENT, handleTokenChanged);
    };
  }, [updateToken]);

  return { token, setToken: updateToken };
}
