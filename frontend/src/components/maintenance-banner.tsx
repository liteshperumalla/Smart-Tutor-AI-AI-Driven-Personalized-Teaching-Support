"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Wrench } from "lucide-react";
import { getMaintenanceState, WINDOW_LABEL } from "@/lib/maintenance";

/** How often to re-check the backend while it answers / while it doesn't. */
const UP_RECHECK_MS = 5 * 60_000;
const DOWN_RECHECK_MS = 60_000;

/** CSS variable other fixed chrome (mobile header, sidebar) offsets by. */
export const BANNER_HEIGHT_VAR = "--banner-h";

type BannerState = { down: false } | { down: true; scheduled: boolean; resumesLabel: string | null };

async function backendIsUp(): Promise<boolean> {
  try {
    const res = await fetch("/api/backend/health", { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Site-wide notice shown only while the backend is actually unreachable.
 *
 * The instance is normally stopped outside its schedule (lib/maintenance), but
 * it can be running then (a deploy or a manual start), so the banner checks
 * /api/backend/health instead of trusting the clock. The clock only picks the
 * wording: "scheduled maintenance" inside the stop window, "temporarily
 * unavailable" otherwise.
 *
 * The banner is fixed to the top and publishes its height as --banner-h on
 * <html>, so the fixed mobile header and sidebar sit below it.
 */
export function MaintenanceBanner() {
  const [state, setState] = useState<BannerState>({ down: false });
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const check = async () => {
      const up = await backendIsUp();
      if (cancelled) return;
      if (up) {
        setState({ down: false });
      } else {
        const { isDown, resumesLabel } = getMaintenanceState();
        setState({ down: true, scheduled: isDown, resumesLabel });
      }
      timer = setTimeout(check, up ? UP_RECHECK_MS : DOWN_RECHECK_MS);
    };

    check();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  useLayoutEffect(() => {
    const root = document.documentElement;
    const el = ref.current;
    if (!el) {
      root.style.setProperty(BANNER_HEIGHT_VAR, "0px");
      return;
    }
    const publish = () => root.style.setProperty(BANNER_HEIGHT_VAR, `${el.offsetHeight}px`);
    publish();
    const observer = new ResizeObserver(publish);
    observer.observe(el);
    return () => {
      observer.disconnect();
      root.style.setProperty(BANNER_HEIGHT_VAR, "0px");
    };
  }, [state.down]);

  if (!state.down) return null;

  return (
    <div
      ref={ref}
      role="status"
      aria-live="polite"
      className="fixed inset-x-0 top-0 z-[60] flex items-center justify-center gap-2 border-b border-warning/40 bg-warning-bg px-4 py-2 text-center text-sm font-medium text-foreground"
    >
      <Wrench className="h-4 w-4 shrink-0" />
      <span>
        {state.scheduled
          ? `Scheduled maintenance — the AI tutor is offline outside ${WINDOW_LABEL}.${
              state.resumesLabel ? ` Service resumes ${state.resumesLabel}.` : ""
            }`
          : "The AI tutor is temporarily unavailable. Please try again shortly."}
      </span>
    </div>
  );
}
