"use client";

import { useState, useEffect, useCallback } from "react";
import { X, Copy, Check, Info, Link2 } from "lucide-react";
import { shareChatSession, ChatMessageDTO } from "@/lib/api";

// Social media icons
function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

function LinkedInIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  );
}

function RedditIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z" />
    </svg>
  );
}

interface ShareChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId: string;
  sessionTitle: string;
  messages: ChatMessageDTO[];
  token: string | null;
}

export function ShareChatModal({
  isOpen,
  onClose,
  sessionId,
  sessionTitle,
  messages,
  token,
}: ShareChatModalProps) {
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Generate share link when modal opens
  useEffect(() => {
    if (!isOpen || !token || shareUrl) return;

    const generateShareLink = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await shareChatSession(token, sessionId);
        setShareUrl(response.share_url);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to generate share link");
      } finally {
        setIsLoading(false);
      }
    };

    generateShareLink();
  }, [isOpen, token, sessionId, shareUrl]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setShareUrl(null);
      setCopied(false);
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

  const handleCopyLink = useCallback(async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  }, [shareUrl]);

  const handleShareX = useCallback(() => {
    if (!shareUrl) return;
    const text = `Check out this conversation on Smart AI Tutor: "${sessionTitle}"`;
    const url = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(shareUrl)}`;
    window.open(url, "_blank", "width=550,height=420");
  }, [shareUrl, sessionTitle]);

  const handleShareLinkedIn = useCallback(() => {
    if (!shareUrl) return;
    const url = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`;
    window.open(url, "_blank", "width=550,height=420");
  }, [shareUrl]);

  const handleShareReddit = useCallback(() => {
    if (!shareUrl) return;
    const title = `Smart AI Tutor Chat: ${sessionTitle}`;
    const url = `https://reddit.com/submit?url=${encodeURIComponent(shareUrl)}&title=${encodeURIComponent(title)}`;
    window.open(url, "_blank", "width=550,height=420");
  }, [shareUrl, sessionTitle]);

  // Get preview messages (first user message and first assistant response)
  const getPreviewMessages = () => {
    const previewMessages: ChatMessageDTO[] = [];
    let foundUser = false;
    let foundAssistant = false;

    for (const msg of messages) {
      if (!foundUser && msg.role === "user") {
        previewMessages.push(msg);
        foundUser = true;
      } else if (foundUser && !foundAssistant && msg.role === "assistant") {
        previewMessages.push(msg);
        foundAssistant = true;
        break;
      }
    }
    return previewMessages;
  };

  const previewMessages = getPreviewMessages();

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Modal */}
      <div
        className="bg-zinc-900 rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden animate-fade-in-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5">
          <h2 className="text-2xl font-bold text-white">
            {sessionTitle || "Chat Conversation"}
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <X className="h-5 w-5 text-zinc-400" />
          </button>
        </div>

        {/* Divider */}
        <div className="h-px bg-zinc-700 mx-6" />

        {/* Content */}
        <div className="p-6">
          {/* Privacy Warning */}
          <div className="flex items-start gap-3 p-4 rounded-xl bg-zinc-800 mb-6">
            <Info className="h-5 w-5 text-zinc-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-white text-sm">
                This conversation may include personal information.
              </p>
              <p className="text-zinc-400 text-sm">
                Take a moment to check the content before sharing the link.
              </p>
            </div>
          </div>

          {/* Chat Preview */}
          <div className="rounded-xl bg-zinc-800/50 p-4 mb-6 max-h-64 overflow-y-auto">
            {previewMessages.map((msg, index) => (
              <div key={index} className="mb-4 last:mb-0">
                {msg.role === "user" ? (
                  <div className="flex justify-end">
                    <div className="max-w-[80%] rounded-2xl bg-blue-600 px-4 py-3 text-white">
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">
                        {msg.content.length > 200
                          ? msg.content.slice(0, 200) + "..."
                          : msg.content}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="text-zinc-300 text-sm leading-relaxed">
                    <p className="whitespace-pre-wrap">
                      {msg.content.length > 300
                        ? msg.content.slice(0, 300) + "..."
                        : msg.content}
                    </p>
                  </div>
                )}
              </div>
            ))}

            {/* Branding */}
            <div className="flex justify-end mt-4 pt-4 border-t border-zinc-700">
              <span className="text-lg font-bold text-white">Smart AI Tutor</span>
            </div>
          </div>

          {/* Loading state */}
          {isLoading && (
            <div className="flex items-center justify-center py-4">
              <div className="h-6 w-6 border-2 border-white border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {/* Error state */}
          {error && (
            <div className="mb-4 p-4 rounded-xl bg-red-900/30 border border-red-800">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          {/* Share Buttons */}
          {shareUrl && !isLoading && (
            <div className="flex items-center justify-center gap-8 pt-4">
              {/* Copy Link */}
              <button
                onClick={handleCopyLink}
                className="flex flex-col items-center gap-2 group"
              >
                <div className={`p-4 rounded-full transition-colors ${
                  copied
                    ? "bg-green-600"
                    : "bg-zinc-800 group-hover:bg-zinc-700"
                }`}>
                  {copied ? (
                    <Check className="h-6 w-6 text-white" />
                  ) : (
                    <Link2 className="h-6 w-6 text-white" />
                  )}
                </div>
                <span className="text-sm text-zinc-400">
                  {copied ? "Copied!" : "Copy link"}
                </span>
              </button>

              {/* X (Twitter) */}
              <button
                onClick={handleShareX}
                className="flex flex-col items-center gap-2 group"
              >
                <div className="p-4 rounded-full bg-zinc-800 group-hover:bg-zinc-700 transition-colors">
                  <XIcon className="h-6 w-6 text-white" />
                </div>
                <span className="text-sm text-zinc-400">X</span>
              </button>

              {/* LinkedIn */}
              <button
                onClick={handleShareLinkedIn}
                className="flex flex-col items-center gap-2 group"
              >
                <div className="p-4 rounded-full bg-zinc-800 group-hover:bg-zinc-700 transition-colors">
                  <LinkedInIcon className="h-6 w-6 text-white" />
                </div>
                <span className="text-sm text-zinc-400">LinkedIn</span>
              </button>

              {/* Reddit */}
              <button
                onClick={handleShareReddit}
                className="flex flex-col items-center gap-2 group"
              >
                <div className="p-4 rounded-full bg-zinc-800 group-hover:bg-zinc-700 transition-colors">
                  <RedditIcon className="h-6 w-6 text-white" />
                </div>
                <span className="text-sm text-zinc-400">Reddit</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
