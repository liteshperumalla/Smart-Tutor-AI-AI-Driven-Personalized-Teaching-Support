"use client";

import { useEffect, useState, useRef } from "react";
import { X } from "lucide-react";

interface RenameChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (newTitle: string) => void;
  currentTitle: string;
  isRenaming?: boolean;
}

export function RenameChatModal({
  isOpen,
  onClose,
  onConfirm,
  currentTitle,
  isRenaming = false,
}: RenameChatModalProps) {
  const [title, setTitle] = useState(currentTitle);
  const inputRef = useRef<HTMLInputElement>(null);

  // Reset title when modal opens with new currentTitle
  useEffect(() => {
    if (isOpen) {
      // Use setTimeout to avoid synchronous setState in effect body
      setTimeout(() => {
        setTitle(currentTitle);
        inputRef.current?.focus();
        inputRef.current?.select();
      }, 50);
    }
  }, [isOpen, currentTitle]);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isRenaming) {
        onClose();
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose, isRenaming]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (title.trim() && !isRenaming) {
      onConfirm(title.trim());
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
      onClick={isRenaming ? undefined : onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="rename-chat-title"
        className="w-full max-w-[400px] animate-fade-in-up rounded-lg border border-line bg-surface p-[22px] text-foreground shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <form onSubmit={handleSubmit}>
          <div className="flex items-center justify-between">
            <h2 id="rename-chat-title" className="text-base">
              Rename chat
            </h2>
            <button
              type="button"
              onClick={onClose}
              disabled={isRenaming}
              className="text-muted transition-colors hover:text-foreground"
              aria-label="Close"
            >
              <X className="h-[18px] w-[18px]" />
            </button>
          </div>

          <input
            ref={inputRef}
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={isRenaming}
            placeholder="Enter chat name"
            aria-label="Chat name"
            className="input mt-3.5 disabled:opacity-50"
          />

          <div className="mt-4 flex items-center justify-end gap-2">
            <button type="button" onClick={onClose} disabled={isRenaming} className="btn-ghost btn-sm">
              Cancel
            </button>
            <button type="submit" disabled={isRenaming || !title.trim()} className="btn-primary btn-sm">
              {isRenaming ? (
                <>
                  <span className="h-[15px] w-[15px] animate-spin rounded-full border-2 border-white/40 border-t-white" />
                  Saving…
                </>
              ) : (
                "Save"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
