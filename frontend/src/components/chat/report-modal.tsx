"use client";

import { useState, useEffect, useCallback } from "react";
import { X, Flag, AlertTriangle, Check } from "lucide-react";
import { submitMessageFeedback } from "@/lib/api";

const REPORT_REASONS = [
  { id: "inaccurate", label: "Inaccurate information", description: "The response contains factual errors" },
  { id: "harmful", label: "Harmful content", description: "The response is potentially harmful or dangerous" },
  { id: "offensive", label: "Offensive language", description: "The response contains offensive or inappropriate language" },
  { id: "irrelevant", label: "Irrelevant response", description: "The response doesn't address my question" },
  { id: "other", label: "Other", description: "Another issue not listed above" },
];

interface ReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId: string;
  messageIndex: number;
  token: string | null;
  courseId?: string;
}

export function ReportModal({
  isOpen,
  onClose,
  sessionId,
  messageIndex,
  token,
  courseId,
}: ReportModalProps) {
  const [selectedReason, setSelectedReason] = useState<string | null>(null);
  const [otherText, setOtherText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setSelectedReason(null);
      setOtherText("");
      setIsSubmitted(false);
      setError(null);
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

  const handleSubmit = useCallback(async () => {
    if (!token || !selectedReason) return;

    const reasonText =
      selectedReason === "other"
        ? otherText.trim() || "Other (no details provided)"
        : REPORT_REASONS.find((r) => r.id === selectedReason)?.label || selectedReason;

    setIsSubmitting(true);
    setError(null);

    try {
      await submitMessageFeedback({
        token,
        sessionId,
        messageIndex,
        feedbackType: "report",
        reason: reasonText,
        courseId,
      });
      setIsSubmitted(true);
      // Close modal after a brief delay
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit report");
    } finally {
      setIsSubmitting(false);
    }
  }, [token, sessionId, messageIndex, courseId, selectedReason, otherText, onClose]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        {/* Modal */}
        <div
          className="bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-fade-in-up"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 dark:border-zinc-700">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-red-100 dark:bg-red-900/30">
                <Flag className="h-5 w-5 text-red-600 dark:text-red-400" />
              </div>
              <h2 className="text-lg font-semibold text-zinc-900 dark:text-white">
                Report Response
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
            >
              <X className="h-5 w-5 text-zinc-500" />
            </button>
          </div>

          {/* Content */}
          <div className="p-6">
            {isSubmitted ? (
              <div className="text-center py-8">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/30 mb-4">
                  <Check className="h-8 w-8 text-green-600 dark:text-green-400" />
                </div>
                <h3 className="text-lg font-semibold text-zinc-900 dark:text-white mb-2">
                  Report Submitted
                </h3>
                <p className="text-sm text-zinc-600 dark:text-zinc-400">
                  Thank you for your feedback. We&apos;ll review this response.
                </p>
              </div>
            ) : (
              <>
                {/* Warning */}
                <div className="flex gap-3 p-4 rounded-xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 mb-6">
                  <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-amber-800 dark:text-amber-200">
                    Please help us improve by reporting any issues with this response.
                  </p>
                </div>

                {/* Reason selection */}
                <div className="space-y-3 mb-6">
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    What&apos;s the issue?
                  </label>
                  {REPORT_REASONS.map((reason) => (
                    <button
                      key={reason.id}
                      type="button"
                      onClick={() => setSelectedReason(reason.id)}
                      className={`w-full text-left p-4 rounded-xl border transition-all ${
                        selectedReason === reason.id
                          ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20"
                          : "border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div
                          className={`w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 mt-0.5 ${
                            selectedReason === reason.id
                              ? "border-indigo-500 bg-indigo-500"
                              : "border-zinc-300 dark:border-zinc-600"
                          }`}
                        >
                          {selectedReason === reason.id && (
                            <Check className="h-3 w-3 text-white" />
                          )}
                        </div>
                        <div>
                          <span className="font-medium text-zinc-900 dark:text-white">
                            {reason.label}
                          </span>
                          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">
                            {reason.description}
                          </p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>

                {/* Other text area */}
                {selectedReason === "other" && (
                  <div className="mb-6">
                    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                      Please describe the issue
                    </label>
                    <textarea
                      value={otherText}
                      onChange={(e) => setOtherText(e.target.value)}
                      placeholder="Describe the problem with this response..."
                      rows={4}
                      className="w-full px-4 py-3 rounded-xl bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-white border border-zinc-200 dark:border-zinc-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all resize-none"
                    />
                  </div>
                )}

                {/* Error */}
                {error && (
                  <div className="mb-4 p-4 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
                    <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={onClose}
                    className="flex-1 px-4 py-3 rounded-xl bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 font-medium hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={!selectedReason || isSubmitting}
                    className="flex-1 px-4 py-3 rounded-xl bg-red-600 text-white font-medium hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {isSubmitting ? (
                      <span className="flex items-center justify-center gap-2">
                        <div className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Submitting...
                      </span>
                    ) : (
                      "Submit Report"
                    )}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
