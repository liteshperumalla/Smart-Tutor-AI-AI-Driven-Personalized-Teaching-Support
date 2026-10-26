/**
 * Skeleton loading placeholders.
 *
 * The design system's loading state is a shimmer sweep (surface-2 → border),
 * shaped like the content that is on its way, so the page doesn't jump when
 * data lands. Spinners stay for in-place actions (buttons, refresh icons).
 * Under prefers-reduced-motion the global rule in globals.css stops the sweep
 * and the blocks render as static placeholders.
 */

type ClassProp = { className?: string };

function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

/** A single shimmer block; size it with utilities (h-*, w-*, rounded-*). */
export function Skeleton({ className, style }: ClassProp & { style?: React.CSSProperties }) {
  return <div aria-hidden="true" className={cx("skeleton", className)} style={style} />;
}

/**
 * Announces the loading state to assistive tech once, around any skeleton
 * layout. Every page-level skeleton should be wrapped in this.
 */
export function SkeletonRegion({
  label = "Loading",
  className,
  children,
}: ClassProp & { label?: string; children: React.ReactNode }) {
  return (
    <div role="status" aria-busy="true" aria-live="polite" className={className}>
      <span className="sr-only">{label}…</span>
      {children}
    </div>
  );
}

const LINE_WIDTHS = ["w-[92%]", "w-[78%]", "w-[64%]", "w-[85%]", "w-[56%]"];

/** Paragraph-like stack of text lines with natural, varied widths. */
export function SkeletonText({ lines = 3, className }: ClassProp & { lines?: number }) {
  return (
    <div className={cx("space-y-2", className)}>
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} aria-hidden="true" className={cx("shimmer-line", LINE_WIDTHS[i % LINE_WIDTHS.length])} />
      ))}
    </div>
  );
}

/** Card: surface + 1px border + radius-xl, with a title and body lines. */
export function SkeletonCard({ lines = 2, className }: ClassProp & { lines?: number }) {
  return (
    <div className={cx("rounded-xl border border-line bg-surface p-5 shadow-sm", className)}>
      <Skeleton className="h-4 w-2/5" />
      <SkeletonText lines={lines} className="mt-4" />
    </div>
  );
}

/** Stat tiles: micro-label + display number, as in the data-display sheet. */
export function SkeletonStatGrid({ count = 4, className }: ClassProp & { count?: number }) {
  return (
    <div className={cx("grid grid-cols-2 gap-4 lg:grid-cols-4", className)}>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="rounded-[14px] border border-line bg-surface p-4">
          <Skeleton className="h-2.5 w-16" />
          <Skeleton className="mt-3 h-7 w-20" />
        </div>
      ))}
    </div>
  );
}

/** Data table: surface-2 header row + body rows, inside the admin table frame. */
export function SkeletonTable({
  rows = 5,
  columns = 4,
  className,
}: ClassProp & { rows?: number; columns?: number }) {
  return (
    <div className={cx("overflow-hidden rounded-[14px] border border-line bg-surface", className)}>
      <div className="flex gap-4 border-b border-line bg-surface-2 px-4 py-3">
        {Array.from({ length: columns }, (_, c) => (
          <div key={c} aria-hidden="true" className="h-2.5 flex-1 rounded-sm bg-line" />
        ))}
      </div>
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} className="flex items-center gap-4 border-b border-line px-4 py-3.5 last:border-b-0">
          {Array.from({ length: columns }, (_, c) => (
            <Skeleton key={c} className={cx("h-3 flex-1", c === 0 && "max-w-40", c === columns - 1 && "max-w-16")} />
          ))}
        </div>
      ))}
    </div>
  );
}

/** List of rows with a leading icon well, e.g. sessions, files, appointments. */
export function SkeletonList({ rows = 4, className }: ClassProp & { rows?: number }) {
  return (
    <div className={cx("space-y-3", className)}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-3 rounded-xl border border-line bg-surface p-4">
          <Skeleton className="h-10 w-10 shrink-0 rounded-md" />
          <div className="min-w-0 flex-1">
            <Skeleton className="h-3.5 w-1/3" />
            <Skeleton className="mt-2 h-3 w-2/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Chart panel: title line + a plot-area block. */
export function SkeletonChart({ className }: ClassProp) {
  return (
    <div className={cx("rounded-xl border border-line bg-surface p-5", className)}>
      <Skeleton className="h-4 w-1/4" />
      <Skeleton className="mt-5 h-48 w-full rounded-md" />
    </div>
  );
}

/** Analytics panel: a stat-tile row over a grid of chart panels. */
export function SkeletonDashboard({ charts = 2, className }: ClassProp & { charts?: number }) {
  return (
    <div className={cx("space-y-6", className)}>
      <SkeletonStatGrid />
      <div className="grid gap-6 lg:grid-cols-2">
        {Array.from({ length: charts }, (_, i) => (
          <SkeletonChart key={i} />
        ))}
      </div>
    </div>
  );
}

/** Full-screen sign-in style form card, for auth route Suspense fallbacks. */
export function SkeletonAuthForm({ label = "Loading", fields = 2 }: { label?: string; fields?: number }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <SkeletonRegion label={label} className="w-full max-w-md">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-3 h-4 w-64 max-w-full" />
        <div className="mt-8 space-y-5 rounded-lg border border-line bg-surface p-6 shadow-sm">
          {Array.from({ length: fields }, (_, i) => (
            <div key={i}>
              <Skeleton className="h-3 w-24" />
              <Skeleton className="mt-2 h-11 w-full rounded-md" />
            </div>
          ))}
          <Skeleton className="h-11 w-full rounded-full" />
        </div>
      </SkeletonRegion>
    </div>
  );
}
