import { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

interface PageHeroProps {
  /** Leading text of the title (rendered in the foreground color). */
  title: ReactNode;
  /** Optional trailing word rendered with the green→indigo gradient accent. */
  accent?: ReactNode;
  /** Supporting copy under the title. */
  subtitle?: ReactNode;
  /** Optional Lucide icon shown as a chip above the title. */
  icon?: LucideIcon;
  /** Optional uppercase label rendered as a pill (with `icon`) above the title. */
  eyebrow?: string;
  /** Extra classes for the outer header element. */
  className?: string;
  /** Optional right-aligned slot (e.g. action buttons). */
  actions?: ReactNode;
}

/**
 * Shared "Claude Design Language" page hero: a rounded gradient banner with a
 * dotted texture, two blurred decorative blobs, and a font-display title whose
 * accent word picks up the green→indigo brand gradient. Mirrors the home page
 * header so every page shares one consistent header treatment.
 */
export function PageHero({
  title,
  accent,
  subtitle,
  icon: Icon,
  eyebrow,
  className,
  actions,
}: PageHeroProps) {
  const outerClassName = [
    "relative overflow-hidden rounded-2xl border border-line bg-surface p-6 shadow-sm sm:p-8 lg:p-10",
    "animate-fade-in-up gradient-mesh",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <header className={outerClassName}>
      {/* Dotted texture */}
      <div
        className="pointer-events-none absolute inset-0 opacity-40 dark:opacity-20"
        style={{
          backgroundImage:
            "radial-gradient(rgba(15,23,42,0.06) 1px, transparent 1px)",
          backgroundSize: "22px 22px",
        }}
      />
      {/* Decorative blobs */}
      <div
        className="pointer-events-none absolute -top-20 -right-16 h-60 w-60 rounded-full blur-3xl animate-float"
        style={{ background: "var(--color-success-bg)" }}
      />
      <div
        className="pointer-events-none absolute -bottom-20 -left-10 h-52 w-52 rounded-full blur-3xl"
        style={{ background: "var(--color-primary-bg)", animationDelay: "1s" }}
      />

      <div className="relative z-10 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          {eyebrow ? (
            <span className="mb-4 inline-flex items-center gap-1.5 rounded-full bg-primary-bg px-3 py-1 text-[11px] font-bold uppercase tracking-[0.2em] text-primary">
              {Icon && <Icon className="h-3.5 w-3.5" />}
              {eyebrow}
            </span>
          ) : (
            Icon && (
              <span className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-[14px] bg-primary-bg text-primary">
                <Icon className="h-5 w-5" />
              </span>
            )
          )}
          <h1 className="font-display text-3xl font-bold leading-[1.05] tracking-tight text-foreground sm:text-4xl lg:text-5xl">
            {title}
            {accent != null && (
              <>
                {" "}
                <span className="text-gradient-primary">
                  {accent}
                </span>
              </>
            )}
          </h1>
          {subtitle && (
            <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted sm:text-lg">
              {subtitle}
            </p>
          )}
        </div>
        {actions && <div className="relative z-10 flex-shrink-0">{actions}</div>}
      </div>
    </header>
  );
}
