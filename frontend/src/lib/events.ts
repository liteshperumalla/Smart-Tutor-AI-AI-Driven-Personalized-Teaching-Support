export const CHAT_SESSIONS_UPDATED_EVENT = "sat-chat-sessions-updated";

export function dispatchChatSessionsUpdated() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(CHAT_SESSIONS_UPDATED_EVENT));
}

// The chat page announces which session is open so the sidebar can mark it.
export const CHAT_SESSION_SELECTED_EVENT = "sat-chat-session-selected";

export function dispatchChatSessionSelected(sessionId: string | null) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(CHAT_SESSION_SELECTED_EVENT, { detail: sessionId }));
}
