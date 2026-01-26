"use client";

import { useEffect, useState, useRef } from "react";

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
      setTitle(currentTitle);
      // Focus input after a brief delay to ensure modal is rendered
      setTimeout(() => {
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
      className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
      onClick={isRenaming ? undefined : onClose}
    >
      {/* Modal */}
      <div
        className="bg-zinc-800 rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-fade-in-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6">
          <h2 className="text-xl font-semibold text-white mb-4">
            Rename chat
          </h2>

          <input
            ref={inputRef}
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={isRenaming}
            placeholder="Enter chat name"
            className="w-full px-4 py-3 rounded-xl bg-zinc-700 border border-zinc-600 text-white placeholder-zinc-400 focus:outline-none focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500 disabled:opacity-50 transition-colors"
          />

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 mt-6">
            <button
              type="button"
              onClick={onClose}
              disabled={isRenaming}
              className="px-5 py-2.5 rounded-full bg-zinc-700 text-white font-medium hover:bg-zinc-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isRenaming || !title.trim()}
              className="px-5 py-2.5 rounded-full bg-indigo-600 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              {isRenaming ? (
                <>
                  <span className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Renaming...
                </>
              ) : (
                "Rename"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
