/**
 * Scheduled-downtime helper.
 *
 * The production EC2 instance is stopped outside Mon–Fri 09:00–17:00
 * America/Chicago (see .github/workflows/ec2-schedule.yml) to cut the
 * always-on compute bill. This module is the single source of truth for that
 * window so both the browser (proactive maintenance banner) and the backend
 * proxy (classifying an unreachable backend) agree on when we're "down".
 *
 * It uses Intl with an explicit timeZone, so it is DST-correct year-round
 * without hardcoding UTC offsets.
 */

export const MAINTENANCE_TZ = "America/Chicago";
export const ON_START_HOUR = 9; // 09:00 CT — instance starts
export const ON_END_HOUR = 17; // 17:00 CT — instance stops
export const WINDOW_LABEL = "Mon–Fri 9 AM–5 PM CT";

const WEEKDAY_TO_NUM: Record<string, number> = {
  Monday: 1,
  Tuesday: 2,
  Wednesday: 3,
  Thursday: 4,
  Friday: 5,
  Saturday: 6,
  Sunday: 7,
};

type ChicagoParts = { dow: number; hour: number };

function chicagoParts(now: Date): ChicagoParts {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: MAINTENANCE_TZ,
    weekday: "long",
    hour: "2-digit",
    hour12: false,
  }).formatToParts(now);

  const get = (type: string) =>
    parts.find((p) => p.type === type)?.value ?? "";

  let hour = parseInt(get("hour"), 10);
  if (Number.isNaN(hour) || hour === 24) hour = 0; // some runtimes emit "24" at midnight
  const dow = WEEKDAY_TO_NUM[get("weekday")] ?? 1;
  return { dow, hour };
}

export type MaintenanceState = {
  /** True when the instance is scheduled to be stopped right now. */
  isDown: boolean;
  /** Human label for when service resumes, e.g. "today at 9:00 AM CT". */
  resumesLabel: string | null;
};

/**
 * Compute whether we're currently inside the scheduled-down window, and a
 * friendly label for when the service comes back.
 */
export function getMaintenanceState(now: Date = new Date()): MaintenanceState {
  const { dow, hour } = chicagoParts(now);
  const isWeekend = dow > 5;
  const beforeOpen = hour < ON_START_HOUR;
  const afterClose = hour >= ON_END_HOUR;
  const isDown = isWeekend || beforeOpen || afterClose;

  if (!isDown) return { isDown: false, resumesLabel: null };

  let resumesLabel: string;
  if (!isWeekend && beforeOpen) {
    // Same weekday, before opening → comes back this morning.
    resumesLabel = "today at 9:00 AM CT";
  } else if (dow === 5 || dow === 6 || dow === 7) {
    // Friday after close, or any time on the weekend → next Monday.
    resumesLabel = "Monday at 9:00 AM CT";
  } else {
    // Mon–Thu after close → next morning.
    resumesLabel = "tomorrow at 9:00 AM CT";
  }
  return { isDown: true, resumesLabel };
}
