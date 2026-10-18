"use client";

import { useState, useCallback } from "react";
import {
  Copy,
  ThumbsUp,
  ThumbsDown,
  Share2,
  Flag,
  BookOpen,
  Check,
  RefreshCw,
} from "lucide-react";
import {
  submitMessageFeedback,
  MessageFeedbackType,
} from "@/lib/api";

interface ResponseActionBarProps {
  messageContent: string;
  sessionId: string;
  messageIndex: number;
  token: string | null;
  courseId?: string;
  hasSources: boolean;
  currentFeedback: MessageFeedbackType | null;
  onFeedbackChange: (feedback: MessageFeedbackType | null) => void;
  onShareClick: () => void;
  onReportClick: () => void;
  onSourcesClick: () => void;
  onRegenerateClick?: () => void;
  isRegenerating?: boolean;
}

export function ResponseActionBar({
  messageContent,
  sessionId,
  messageIndex,
  token,
  courseId,
  hasSources,
  currentFeedback,
  onFeedbackChange,
  onShareClick,
  onReportClick,
  onSourcesClick,
  onRegenerateClick,
  isRegenerating = false,
}: ResponseActionBarProps) {
  const [copied, setCopied] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(messageContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  }, [messageContent]);

  const handleFeedback = useCallback(
    async (feedbackType: MessageFeedbackType) => {
      if (!token || isSubmitting) return;

      setIsSubmitting(true);
      try {
        const response = await submitMessageFeedback({
          token,
          sessionId,
          messageIndex,
          feedbackType,
          courseId,
        });

        // Update local state based on response
        onFeedbackChange(response.feedback_type);
      } catch (err) {
        console.error("Failed to submit feedback:", err);
      } finally {
        setIsSubmitting(false);
      }
    },
    [token, sessionId, messageIndex, courseId, isSubmitting, onFeedbackChange]
  );

  const isLiked = currentFeedback === "thumbs_up";
  const isDisliked = currentFeedback === "thumbs_down";

  return (
    <div className="flex items-center gap-1 mt-3 pt-2 border-t border-zinc-200/50 dark:border-zinc-700/50">
      {/* Copy */}
      <ActionButton
        icon={copied ? Check : Copy}
        label={copied ? "Copied!" : "Copy"}
        onClick={handleCopy}
        active={copied}
        activeColor="text-green-500"
      />

      {/* Thumbs Up */}
      <ActionButton
        icon={ThumbsUp}
        label="Like"
        onClick={() => handleFeedback("thumbs_up")}
        active={isLiked}
        activeColor="text-green-500"
        filled={isLiked}
        disabled={isSubmitting}
      />

      {/* Thumbs Down */}
      <ActionButton
        icon={ThumbsDown}
        label="Dislike"
        onClick={() => handleFeedback("thumbs_down")}
        active={isDisliked}
        activeColor="text-red-500"
        filled={isDisliked}
        disabled={isSubmitting}
      />

      {/* Share */}
      <ActionButton
        icon={Share2}
        label="Share"
        onClick={onShareClick}
      />

      {/* Try Again / Regenerate */}
      {onRegenerateClick && (
        <ActionButton
          icon={RefreshCw}
          label="Try again"
          onClick={onRegenerateClick}
          disabled={isRegenerating}
          spinning={isRegenerating}
        />
      )}

      {/* Report */}
      <ActionButton
        icon={Flag}
        label="Report"
        onClick={onReportClick}
      />

      {/* Sources - only show if there are sources */}
      {hasSources && (
        <ActionButton
          icon={BookOpen}
          label="Sources"
          onClick={onSourcesClick}
        />
      )}
    </div>
  );
}

interface ActionButtonProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  onClick: () => void;
  active?: boolean;
  activeColor?: string;
  filled?: boolean;
  disabled?: boolean;
  spinning?: boolean;
}

function ActionButton({
  icon: Icon,
  label,
  onClick,
  active = false,
  activeColor = "text-indigo-500",
  filled = false,
  disabled = false,
  spinning = false,
}: ActionButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`
        group relative flex items-center justify-center
        p-2 rounded-lg transition-all duration-200
        ${active ? activeColor : "text-zinc-400 dark:text-zinc-500"}
        ${disabled ? "opacity-50 cursor-not-allowed" : "hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-700 dark:hover:text-zinc-300"}
      `}
      title={label}
    >
      <Icon
        className={`h-4 w-4 transition-transform duration-200 ${
          active && filled ? "fill-current" : ""
        } ${!disabled ? "group-hover:scale-110" : ""} ${spinning ? "animate-spin" : ""}`}
      />
      {/* Tooltip */}
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 text-xs font-medium text-white bg-zinc-800 dark:bg-zinc-700 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap">
        {label}
      </span>
    </button>
  );
}
