"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiBaseUrl } from "@/lib/api";
import { AUTH_STATE_CHANGED_EVENT } from "@/lib/auth";

export type UserInfo = {
  username: string;
  email: string;
  role: string;
  full_name?: string;
  display_name?: string;
  last_login?: string;
};

export function useUser() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    try {
      const base = getApiBaseUrl();
      const res = await fetch(`${base}/auth/me`, {
        method: "GET",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        setUser(null);
        return;
      }
      const data = await res.json();
      setUser(data.user ?? null);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  // Re-fetch when authentication state changes (login/logout)
  useEffect(() => {
    function handleAuthChange() {
      fetchUser();
    }
    window.addEventListener(AUTH_STATE_CHANGED_EVENT, handleAuthChange);
    return () => {
      window.removeEventListener(AUTH_STATE_CHANGED_EVENT, handleAuthChange);
    };
  }, [fetchUser]);

  const isAdmin = user?.role === "Admin";

  return { user, isAdmin, isLoading, refetch: fetchUser };
}
