/**
 * LogoMark — Smart AI Tutor brand mark.
 *
 * A typographic monogram: the letter "S" set in the display font on a rounded
 * square filled with the Deep Learning Blue → Neural Teal brand gradient. No accent spark —
 * the mark is intentionally clean.
 */
export function LogoMark({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    <span
      className={`inline-flex flex-shrink-0 items-center justify-center ${className}`}
      style={{
        height: size,
        width: size,
        borderRadius: size * 0.26,
        // Fixed brand colors: the mark does not shift with the theme.
        background: "linear-gradient(135deg, #1E3A8A 0%, #0D9488 100%)",
        boxShadow: "var(--shadow-brand)",
      }}
      aria-hidden="true"
    >
      <span
        className="font-display"
        style={{
          fontWeight: 700,
          fontSize: size * 0.62,
          color: "white",
          letterSpacing: "-0.06em",
          lineHeight: 0.85,
        }}
      >
        S
      </span>
    </span>
  );
}
