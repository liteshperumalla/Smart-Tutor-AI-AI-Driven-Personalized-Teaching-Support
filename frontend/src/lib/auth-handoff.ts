"use client";

/**
 * Hand identity fields (username, email, setup token) from one auth page to
 * the next without putting them in the URL. Query strings end up in browser
 * history, analytics pageviews, server/CDN access logs and Referer headers.
 *
 * Values live in sessionStorage, scoped to this tab.
 */

const PREFIX = "auth_handoff:";

export type AuthHandoff = {
  username?: string;
  email?: string;
  token?: string;
};

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

export function stashAuthHandoff(page: string, values: AuthHandoff): void {
  const store = storage();
  if (!store) return;
  try {
    store.setItem(PREFIX + page, JSON.stringify(values));
  } catch {
    // Storage full or blocked: the next page simply asks the user again.
  }
}

/**
 * Read what the previous page handed over. It is not cleared on read, so a
 * refresh of the receiving page keeps working; the tab-scoped storage goes
 * away with the tab. Values still arriving in the query string (older links,
 * bookmarks) are accepted too; the caller should then replace the URL to drop
 * them.
 */
export function readAuthHandoff(
  page: string,
  searchParams: URLSearchParams | { get(name: string): string | null }
): AuthHandoff & { fromUrl: boolean } {
  const store = storage();
  let stored: AuthHandoff = {};
  try {
    const raw = store?.getItem(PREFIX + page);
    if (raw) stored = JSON.parse(raw) as AuthHandoff;
  } catch {
    stored = {};
  }
  const fromQuery: AuthHandoff = {
    username: searchParams.get("username") ?? undefined,
    email: searchParams.get("email") ?? undefined,
    token: searchParams.get("token") ?? undefined,
  };
  return {
    username: fromQuery.username ?? stored.username,
    email: fromQuery.email ?? stored.email,
    token: fromQuery.token ?? stored.token,
    fromUrl: Boolean(fromQuery.username || fromQuery.email || fromQuery.token),
  };
}
