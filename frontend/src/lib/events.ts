export const CHAT_SESSIONS_UPDATED_EVENT = "sat-chat-sessions-updated";

export function dispatchChatSessionsUpdated() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(CHAT_SESSIONS_UPDATED_EVENT));
}
