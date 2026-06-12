/**
 * LogoMark — Smart AI Tutor brand mark.
 *
 * A typographic monogram: the letter "S" set in the display font on a rounded
 * square filled with the primary emerald → indigo gradient. No accent spark —
 * the mark is intentionally clean.
 */
export function LogoMark({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    <span
      className={`inline-flex flex-shrink-0 items-center justify-center ${className}`}
      style={{
        height: size,
        width: size,
        borderRadius: size * 0.27,
        background: "linear-gradient(135deg, #059669 0%, #4f46e5 100%)",
        boxShadow: "0 4px 6px -1px rgba(5, 150, 105, 0.30)",
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
