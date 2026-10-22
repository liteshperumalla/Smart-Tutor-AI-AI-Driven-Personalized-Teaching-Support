/**
 * Chat message timestamps: short label for the thread, full value for the tooltip.
 *   today      -> "3:42 PM"
 *   yesterday  -> "Yesterday, 3:42 PM"
 *   this year  -> "Oct 21, 3:42 PM"
 *   older      -> "Oct 21, 2025, 3:42 PM"
 */
export function formatMessageTime(iso: string | undefined, now: Date = new Date()): { label: string; full: string } | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;

  const time = date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const daysAgo = Math.round((startOfDay(now) - startOfDay(date)) / 86_400_000);

  let label: string;
  if (daysAgo === 0) {
    label = time;
  } else if (daysAgo === 1) {
    label = `Yesterday, ${time}`;
  } else {
    const day = date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      ...(date.getFullYear() === now.getFullYear() ? {} : { year: "numeric" }),
    });
    label = `${day}, ${time}`;
  }

  const full = date.toLocaleString(undefined, { dateStyle: "full", timeStyle: "short" });
  return { label, full };
}
