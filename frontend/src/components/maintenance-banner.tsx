"use client";

import { useEffect, useState } from "react";
import { Wrench } from "lucide-react";
import {
  getMaintenanceState,
  WINDOW_LABEL,
  type MaintenanceState,
} from "@/lib/maintenance";

/**
 * Site-wide notice shown while the backend is in its scheduled-down window.
 *
 * The state is computed client-side from the local clock (see lib/maintenance),
 * so it appears immediately without waiting for a backend request to fail.
 * Initial render is empty to avoid a hydration mismatch; the effect fills it in
 * on the client and re-checks every minute so the banner clears itself at 9 AM.
 */
export function MaintenanceBanner() {
  const [state, setState] = useState<MaintenanceState>({
    isDown: false,
    resumesLabel: null,
  });

  useEffect(() => {
    const update = () => setState(getMaintenanceState());
    update();
    const id = setInterval(update, 60_000);
    return () => clearInterval(id);
  }, []);

  if (!state.isDown) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="sticky top-0 z-50 flex items-center justify-center gap-2 border-b border-amber-300/60 bg-amber-50 px-4 py-2 text-center text-sm font-medium text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/60 dark:text-amber-200"
    >
      <Wrench className="h-4 w-4 shrink-0" />
      <span>
        Scheduled maintenance — the AI tutor is offline outside {WINDOW_LABEL}.
        {state.resumesLabel ? ` Service resumes ${state.resumesLabel}.` : ""}
      </span>
    </div>
  );
}
