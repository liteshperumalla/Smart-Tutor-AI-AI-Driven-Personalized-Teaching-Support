"use client";

import { useEffect, useRef } from "react";
import { toast } from "sonner";
import { fetchPublicAnnouncements } from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";

const SEEN_KEY = "seen_announcements";

function getSeenIds(): string[] {
  try {
    const raw = localStorage.getItem(SEEN_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function markSeen(ids: string[]) {
  try {
    const existing = getSeenIds();
    const merged = [...new Set([...existing, ...ids])];
    localStorage.setItem(SEEN_KEY, JSON.stringify(merged));
  } catch {
    // localStorage unavailable
  }
}

export function AnnouncementToaster() {
  const { token } = useAuthToken({ redirectTo: undefined });
  const hasRun = useRef(false);

  useEffect(() => {
    if (!token || hasRun.current) return;
    hasRun.current = true;

    (async () => {
      try {
        const announcements = await fetchPublicAnnouncements();
        if (!announcements.length) return;

        const seen = getSeenIds();
        const unseen = announcements.filter((a) => !seen.includes(a.id));
        if (!unseen.length) return;

        // Show each unseen announcement as a toast (staggered slightly)
        unseen.forEach((ann, i) => {
          setTimeout(() => {
            toast.info(ann.title, {
              description: ann.content,
              duration: 8000,
            });
          }, i * 600);
        });

        markSeen(unseen.map((a) => a.id));
      } catch {
        // Don't block the app if announcements fail
      }
    })();
  }, [token]);

  return null;
}
