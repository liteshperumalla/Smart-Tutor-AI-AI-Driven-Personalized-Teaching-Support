/** Prevent open redirects while preserving an in-app destination after sign-in. */
export function getSafeNextPath(value: string | null | undefined, fallback = "/"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return fallback;
  return value;
}

export function getCurrentAppPath(): string {
  if (typeof window === "undefined") return "/";
  return `${window.location.pathname}${window.location.search}`;
}

export function loginPathFor(returnTo?: string): string {
  const destination = getSafeNextPath(returnTo, "/");
  return destination === "/" ? "/login" : `/login?next=${encodeURIComponent(destination)}`;
}
