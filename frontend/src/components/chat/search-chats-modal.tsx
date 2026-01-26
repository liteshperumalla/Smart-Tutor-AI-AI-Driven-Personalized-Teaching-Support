"use client";

import { useEffect, useState, useRef, useMemo } from "react";
import { X, Search, MessageCircle, Edit3, Pin } from "lucide-react";
import { ChatSessionDTO } from "@/lib/api";

interface SearchChatsModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessions: ChatSessionDTO[];
  onSelectSession: (sessionId: string) => void;
  onCreateSession: () => void;
  isCreating?: boolean;
}

// Helper to group sessions by time period
function groupSessionsByTime(sessions: ChatSessionDTO[]) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const sevenDaysAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
  const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

  const pinned: ChatSessionDTO[] = [];
  const todayItems: ChatSessionDTO[] = [];
  const last7Days: ChatSessionDTO[] = [];
  const last30Days: ChatSessionDTO[] = [];
  const older: ChatSessionDTO[] = [];

  for (const session of sessions) {
    // Skip archived sessions
    if (session.is_archived) continue;

    const sessionDate = new Date(session.updated_at || session.created_at || new Date().toISOString());

    if (session.is_pinned) {
      pinned.push(session);
    } else if (sessionDate >= today) {
      todayItems.push(session);
    } else if (sessionDate >= sevenDaysAgo) {
      last7Days.push(session);
    } else if (sessionDate >= thirtyDaysAgo) {
      last30Days.push(session);
    } else {
      older.push(session);
    }
  }

  return { pinned, todayItems, last7Days, last30Days, older };
}

export function SearchChatsModal({
  isOpen,
  onClose,
  sessions,
  onSelectSession,
  onCreateSession,
  isCreating = false,
}: SearchChatsModalProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen) {
      setSearchQuery("");
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  // Filter sessions based on search query
  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions.filter(s => !s.is_archived);
    const query = searchQuery.toLowerCase();
    return sessions.filter(
      (s) => !s.is_archived && (s.title?.toLowerCase().includes(query) || s.id.toLowerCase().includes(query))
    );
  }, [sessions, searchQuery]);

  // Group filtered sessions by time
  const groupedSessions = useMemo(() => {
    return groupSessionsByTime(filteredSessions);
  }, [filteredSessions]);

  const handleSelectSession = (sessionId: string) => {
    onSelectSession(sessionId);
    onClose();
  };

  const handleCreateSession = () => {
    onCreateSession();
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/70 z-50 flex items-start justify-center pt-20 p-4"
      onClick={onClose}
    >
      {/* Modal */}
      <div
        className="bg-zinc-800 rounded-2xl shadow-2xl w-full max-w-xl overflow-hidden animate-fade-in-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-zinc-700">
          <Search className="h-5 w-5 text-zinc-400 flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search chats..."
            className="flex-1 bg-transparent text-white placeholder-zinc-400 outline-none text-lg"
          />
          <button
            onClick={onClose}
            className="p-1 hover:bg-zinc-700 rounded-lg transition-colors"
          >
            <X className="h-5 w-5 text-zinc-400" />
          </button>
        </div>

        {/* Content */}
        <div className="max-h-[60vh] overflow-y-auto">
          {/* New Chat Button */}
          <button
            onClick={handleCreateSession}
            disabled={isCreating}
            className="w-full flex items-center gap-3 px-5 py-3 bg-zinc-700 hover:bg-zinc-600 transition-colors disabled:opacity-50"
          >
            <Edit3 className="h-5 w-5 text-white" />
            <span className="text-white font-medium">
              {isCreating ? "Creating..." : "New chat"}
            </span>
          </button>

          {/* Pinned Section */}
          {groupedSessions.pinned.length > 0 && (
            <div className="px-5 pt-4">
              <p className="text-xs text-zinc-500 mb-2 flex items-center gap-1">
                <Pin className="h-3 w-3" />
                Pinned
              </p>
              {groupedSessions.pinned.map((session) => (
                <SessionItem
                  key={session.id}
                  session={session}
                  onClick={() => handleSelectSession(session.id)}
                />
              ))}
            </div>
          )}

          {/* Today Section */}
          {groupedSessions.todayItems.length > 0 && (
            <div className="px-5 pt-4">
              <p className="text-xs text-zinc-500 mb-2">Today</p>
              {groupedSessions.todayItems.map((session) => (
                <SessionItem
                  key={session.id}
                  session={session}
                  onClick={() => handleSelectSession(session.id)}
                />
              ))}
            </div>
          )}

          {/* Previous 7 Days Section */}
          {groupedSessions.last7Days.length > 0 && (
            <div className="px-5 pt-4">
              <p className="text-xs text-zinc-500 mb-2">Previous 7 Days</p>
              {groupedSessions.last7Days.map((session) => (
                <SessionItem
                  key={session.id}
                  session={session}
                  onClick={() => handleSelectSession(session.id)}
                />
              ))}
            </div>
          )}

          {/* Previous 30 Days Section */}
          {groupedSessions.last30Days.length > 0 && (
            <div className="px-5 pt-4">
              <p className="text-xs text-zinc-500 mb-2">Previous 30 Days</p>
              {groupedSessions.last30Days.map((session) => (
                <SessionItem
                  key={session.id}
                  session={session}
                  onClick={() => handleSelectSession(session.id)}
                />
              ))}
            </div>
          )}

          {/* Older Section */}
          {groupedSessions.older.length > 0 && (
            <div className="px-5 pt-4 pb-4">
              <p className="text-xs text-zinc-500 mb-2">Older</p>
              {groupedSessions.older.map((session) => (
                <SessionItem
                  key={session.id}
                  session={session}
                  onClick={() => handleSelectSession(session.id)}
                />
              ))}
            </div>
          )}

          {/* No results */}
          {filteredSessions.length === 0 && searchQuery && (
            <div className="px-5 py-8 text-center">
              <p className="text-zinc-400">No chats found for "{searchQuery}"</p>
            </div>
          )}

          {/* Empty state */}
          {filteredSessions.length === 0 && !searchQuery && (
            <div className="px-5 py-8 text-center">
              <p className="text-zinc-400">No chats yet. Start a new conversation!</p>
            </div>
          )}

          {/* Bottom padding */}
          <div className="h-4" />
        </div>
      </div>
    </div>
  );
}

function SessionItem({
  session,
  onClick,
}: {
  session: ChatSessionDTO;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-zinc-700 transition-colors text-left mb-1"
    >
      <MessageCircle className="h-4 w-4 text-zinc-400 flex-shrink-0" />
      <span className="text-white truncate">
        {session.title || `Session ${session.id.slice(0, 6)}`}
      </span>
      {session.is_pinned && (
        <Pin className="h-3 w-3 text-zinc-500 flex-shrink-0 ml-auto" />
      )}
    </button>
  );
}
