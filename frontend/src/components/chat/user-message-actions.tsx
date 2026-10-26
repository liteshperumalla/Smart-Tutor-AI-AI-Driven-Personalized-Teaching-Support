"use client";

import { useState } from "react";
import { Copy, Pencil, Check } from "lucide-react";

interface UserMessageActionsProps {
  onCopy: () => void;
  onEdit: () => void;
  visible?: boolean;
}

export function UserMessageActions({ onCopy, onEdit, visible = false }: UserMessageActionsProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    onCopy();
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`flex items-center gap-1 mt-2 transition-opacity duration-200 ${visible ? 'opacity-100' : 'opacity-0'}`}>
      {/* Copy Button */}
      <button
        onClick={handleCopy}
        className="p-1.5 rounded-sm text-muted hover:text-foreground hover:bg-surface-2 transition-colors"
        title="Copy message"
      >
        {copied ? (
          <Check className="h-4 w-4 text-success" />
        ) : (
          <Copy className="h-4 w-4" />
        )}
      </button>

      {/* Edit Button */}
      <button
        onClick={onEdit}
        className="p-1.5 rounded-sm text-muted hover:text-foreground hover:bg-surface-2 transition-colors"
        title="Edit message"
      >
        <Pencil className="h-4 w-4" />
      </button>
    </div>
  );
}

interface EditableUserMessageProps {
  initialContent: string;
  onCancel: () => void;
  onSend: (newContent: string) => void;
  isSending?: boolean;
}

export function EditableUserMessage({
  initialContent,
  onCancel,
  onSend,
  isSending = false,
}: EditableUserMessageProps) {
  const [editedContent, setEditedContent] = useState(initialContent);

  const handleSend = () => {
    if (editedContent.trim() && editedContent.trim() !== initialContent.trim()) {
      onSend(editedContent.trim());
    } else if (editedContent.trim() === initialContent.trim()) {
      // No changes, just cancel
      onCancel();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onCancel();
    }
  };

  return (
    <div className="w-full max-w-2xl">
      <div className="rounded-[18px] border-2 border-primary bg-surface p-4 shadow-[0_0_0_4px_var(--ring)]">
        <textarea
          value={editedContent}
          onChange={(e) => setEditedContent(e.target.value)}
          onKeyDown={handleKeyDown}
          className="w-full bg-transparent text-foreground text-sm leading-relaxed resize-none outline-none min-h-[60px] placeholder:text-muted"
          autoFocus
          rows={Math.max(2, editedContent.split("\n").length)}
        />
        <div className="flex justify-end gap-2 mt-3">
          <button
            onClick={onCancel}
            disabled={isSending}
            className="btn-ghost btn-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleSend}
            disabled={isSending || !editedContent.trim()}
            className="btn-primary btn-sm"
          >
            {isSending ? "Sending..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
