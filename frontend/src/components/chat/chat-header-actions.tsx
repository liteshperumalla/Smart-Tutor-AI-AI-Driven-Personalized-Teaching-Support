"use client";

import { useState, useRef, useEffect } from "react";
import { Upload, MoreHorizontal, Share2, Trash2, Edit2, Pin, Archive, Flag } from "lucide-react";

interface ChatHeaderActionsProps {
  sessionTitle?: string;
  onShareClick: () => void;
  onDeleteClick?: () => void;
  onRenameClick?: () => void;
  onPinClick?: () => void;
  onArchiveClick?: () => void;
  isPinned?: boolean;
  isArchived?: boolean;
  hasActiveSession: boolean;
}

export function ChatHeaderActions({
  sessionTitle,
  onShareClick,
  onDeleteClick,
  onRenameClick,
  onPinClick,
  onArchiveClick,
  isPinned = false,
  isArchived = false,
  hasActiveSession,
}: ChatHeaderActionsProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    };

    if (isMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isMenuOpen]);

  // Close menu on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isMenuOpen) {
        setIsMenuOpen(false);
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isMenuOpen]);

  if (!hasActiveSession) return null;

  return (
    <div className="flex items-center justify-between w-full">
      {/* Session Title - Left side */}
      <div className="flex-1 min-w-0">
        {sessionTitle && (
          <h1 className="text-base font-medium text-zinc-700 dark:text-zinc-300 truncate">
            {sessionTitle}
          </h1>
        )}
      </div>

      {/* Actions - Right side */}
      <div className="flex items-center gap-1 ml-4">
        {/* Share Button */}
        <button
          onClick={onShareClick}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
        >
          <Upload className="h-4 w-4" />
          <span className="text-sm font-medium">Share</span>
        </button>

        {/* Three-dot Menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            className="p-2 rounded-lg text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            <MoreHorizontal className="h-5 w-5" />
          </button>

          {/* Dropdown Menu */}
          {isMenuOpen && (
            <div className="absolute right-0 top-full mt-2 w-48 py-2 rounded-xl bg-white dark:bg-zinc-800 shadow-xl border border-zinc-200 dark:border-zinc-700 z-50 animate-fade-in-up">
              {/* Share option */}
              <button
                onClick={() => {
                  setIsMenuOpen(false);
                  onShareClick();
                }}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors"
              >
                <Share2 className="h-4 w-4" />
                <span className="text-sm">Share</span>
              </button>

              {/* Rename option */}
              {onRenameClick && (
                <button
                  onClick={() => {
                    setIsMenuOpen(false);
                    onRenameClick();
                  }}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors"
                >
                  <Edit2 className="h-4 w-4" />
                  <span className="text-sm">Rename</span>
                </button>
              )}

              {/* Pin option */}
              {onPinClick && (
                <button
                  onClick={() => {
                    setIsMenuOpen(false);
                    onPinClick();
                  }}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors"
                >
                  <Pin className={`h-4 w-4 ${isPinned ? 'fill-current' : ''}`} />
                  <span className="text-sm">{isPinned ? 'Unpin' : 'Pin chat'}</span>
                </button>
              )}

              {/* Archive option */}
              {onArchiveClick && (
                <button
                  onClick={() => {
                    setIsMenuOpen(false);
                    onArchiveClick();
                  }}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors"
                >
                  <Archive className="h-4 w-4" />
                  <span className="text-sm">{isArchived ? 'Unarchive' : 'Archive'}</span>
                </button>
              )}

              {/* Divider */}
              {onDeleteClick && (
                <>
                  <div className="h-px bg-zinc-200 dark:bg-zinc-700 my-2" />

                  {/* Delete option */}
                  <button
                    onClick={() => {
                      setIsMenuOpen(false);
                      onDeleteClick();
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                    <span className="text-sm">Delete</span>
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
