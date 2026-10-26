"use client";

import { useEffect } from "react";
import { Trash2 } from "lucide-react";

interface DeleteChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  chatTitle: string;
  isDeleting?: boolean;
}

export function DeleteChatModal({
  isOpen,
  onClose,
  onConfirm,
  chatTitle,
  isDeleting = false,
}: DeleteChatModalProps) {
  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isDeleting) {
        onClose();
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose, isDeleting]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
      onClick={isDeleting ? undefined : onClose}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="delete-chat-title"
        className="w-full max-w-[400px] animate-fade-in-up rounded-lg border border-line bg-surface p-[22px] text-foreground shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Destructive confirms lead with a tinted icon well and name the object. */}
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-md bg-danger-bg text-danger">
            <Trash2 className="h-[18px] w-[18px]" />
          </span>
          <div className="min-w-0">
            <h2 id="delete-chat-title" className="text-base">
              Delete chat?
            </h2>
            <p className="mt-1 text-[13px] text-muted">
              <span className="font-semibold text-foreground">&ldquo;{chatTitle}&rdquo;</span> will be permanently removed.
              Visit settings to delete any memories saved during this chat.
            </p>
          </div>
        </div>

        <div className="mt-[18px] flex items-center justify-end gap-2">
          <button type="button" onClick={onClose} disabled={isDeleting} className="btn-ghost btn-sm">
            Cancel
          </button>
          <button type="button" onClick={onConfirm} disabled={isDeleting} className="btn-danger btn-sm">
            {isDeleting ? (
              <>
                <span className="h-[15px] w-[15px] animate-spin rounded-full border-2 border-white/40 border-t-white" />
                Deleting…
              </>
            ) : (
              "Delete chat"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
