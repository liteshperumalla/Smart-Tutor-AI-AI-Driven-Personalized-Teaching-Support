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
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        {/* Modal */}
        <div
          className="bg-surface border border-line rounded-lg shadow-lg w-full max-w-md overflow-hidden animate-fade-in-up"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-line">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-danger-bg">
                <Flag className="h-5 w-5 text-danger" />
              </div>
              <h2 className="text-lg font-semibold text-foreground">
                Report Response
              </h2>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-surface-2 rounded-md transition-colors"
            >
              <X className="h-5 w-5 text-muted" />
            </button>
          </div>

          {/* Content */}
          <div className="p-6">
            {isSubmitted ? (
              <div className="text-center py-8">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-success-bg mb-4">
                  <Check className="h-8 w-8 text-success" />
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-2">
                  Report Submitted
                </h3>
                <p className="text-sm text-muted">
                  Thank you for your feedback. We&apos;ll review this response.
                </p>
              </div>
            ) : (
              <>
                {/* Warning */}
                <div className="flex gap-3 p-4 rounded-xl bg-warning-bg border border-warning/40 mb-6">
                  <AlertTriangle className="h-5 w-5 text-warning flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-warning">
                    Please help us improve by reporting any issues with this response.
                  </p>
                </div>

                {/* Reason selection */}
                <div className="space-y-3 mb-6">
                  <label className="block text-sm font-medium text-foreground">
                    What&apos;s the issue?
                  </label>
                  {REPORT_REASONS.map((reason) => (
                    <button
                      key={reason.id}
                      type="button"
                      onClick={() => setSelectedReason(reason.id)}
                      className={`w-full text-left p-4 rounded-md border-2 transition-all ${
                        selectedReason === reason.id
                          ? "border-primary bg-primary-bg"
                          : "border-line hover:border-primary/40"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div
                          className={`w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 mt-0.5 ${
                            selectedReason === reason.id
                              ? "border-primary bg-primary"
                              : "border-line"
                          }`}
                        >
                          {selectedReason === reason.id && (
                            <Check className="h-3 w-3 text-white" />
                          )}
                        </div>
                        <div>
                          <span className="font-medium text-foreground">
                            {reason.label}
                          </span>
                          <p className="text-sm text-muted mt-0.5">
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
                    <label className="block text-sm font-medium text-foreground mb-2">
                      Please describe the issue
                    </label>
                    <textarea
                      value={otherText}
                      onChange={(e) => setOtherText(e.target.value)}
                      placeholder="Describe the problem with this response..."
                      rows={4}
                      className="input resize-none"
                    />
                  </div>
                )}

                {/* Error */}
                {error && (
                  <div className="mb-4 p-4 rounded-xl bg-danger-bg border border-danger/30">
                    <p className="text-sm text-danger">{error}</p>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={onClose}
                    className="btn-ghost flex-1"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={!selectedReason || isSubmitting}
                    className="btn-danger flex-1"
                  >
                    {isSubmitting ? (
                      <span className="flex items-center justify-center gap-2">
                        <div className="h-[15px] w-[15px] border-2 border-white/40 border-t-white rounded-full animate-spin" />
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
