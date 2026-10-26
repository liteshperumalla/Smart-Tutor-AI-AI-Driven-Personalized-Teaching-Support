"use client";

import { useState, useRef, useEffect } from "react";
import { MoreHorizontal, Trash2, Edit2, Pin, Archive, FileDown, Paperclip, X, FileText, Image, Share2 } from "lucide-react";
import { type UploadedFileItem } from "@/components/chat/file-preview-grid";

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
  uploadedFiles?: UploadedFileItem[];
  onRemoveFile?: (index: number) => void;
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
  uploadedFiles = [],
  onRemoveFile,
}: ChatHeaderActionsProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isFilesDropdownOpen, setIsFilesDropdownOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const filesDropdownRef = useRef<HTMLDivElement>(null);

  const hasFiles = uploadedFiles.length > 0;

  // Close files dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (filesDropdownRef.current && !filesDropdownRef.current.contains(event.target as Node)) {
        setIsFilesDropdownOpen(false);
      }
    };

    if (isFilesDropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isFilesDropdownOpen]);

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const getFileIcon = (file: File) => {
    if (file.type.startsWith('image/')) {
      return <Image className="h-4 w-4 text-blue-500" />;
    }
    return <FileText className="h-4 w-4 text-muted" />;
  };

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
      if (e.key === "Escape") {
        setIsMenuOpen(false);
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, []);

  if (!hasActiveSession) return null;

  return (
    <div className="flex items-center justify-between w-full">
      {/* Session Title - Plain text, no dropdown */}
      <div className="flex-1 min-w-0 pl-2">
        <h1 className="text-base font-medium text-foreground truncate max-w-[120px] sm:max-w-xs">
          {sessionTitle || "New chat"}
        </h1>
      </div>

      {/* Actions - Right side */}
      <div className="flex items-center gap-2 ml-auto pr-1">
        {/* Files/Attachments Button - Only show when files are uploaded */}
        {hasFiles && (
          <div className="relative" ref={filesDropdownRef}>
            <button
              onClick={() => setIsFilesDropdownOpen(!isFilesDropdownOpen)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-muted bg-surface-2 hover:bg-line transition-colors"
              title="View attachments"
            >
              <Paperclip className="h-4 w-4" />
              <span className="text-sm font-medium">{uploadedFiles.length}</span>
            </button>

            {/* Files Dropdown */}
            {isFilesDropdownOpen && (
              <div className="absolute right-0 top-full mt-2 w-72 py-2 rounded-xl bg-surface shadow-xl border border-line z-50 animate-fade-in-up">
                <div className="px-4 py-2 border-b border-line">
                  <p className="text-sm font-semibold text-foreground">
                    Attached Files ({uploadedFiles.length})
                  </p>
                </div>
                <div className="max-h-64 overflow-y-auto">
                  {uploadedFiles.map((item, index) => (
                    <div
                      key={item.id ?? index}
                      className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2 transition-colors"
                    >
                      {/* Thumbnail for images */}
                      {item.file.type.startsWith('image/') ? (
                        <div className="w-10 h-10 rounded-lg overflow-hidden bg-surface-2 flex-shrink-0">
                          <img
                            src={URL.createObjectURL(item.file)}
                            alt={item.file.name}
                            className="w-full h-full object-cover"
                          />
                        </div>
                      ) : (
                        <div className="w-10 h-10 rounded-lg bg-surface-2 flex items-center justify-center flex-shrink-0">
                          {getFileIcon(item.file)}
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-foreground truncate">
                          {item.file.name}
                        </p>
                        <p className="text-xs text-muted">
                          {formatFileSize(item.file.size)}
                        </p>
                      </div>
                      {onRemoveFile && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onRemoveFile(index);
                          }}
                          className="p-1.5 rounded-lg hover:bg-line transition-colors"
                          title="Remove file"
                        >
                          <X className="h-4 w-4 text-muted" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Share Button */}
        <button
          onClick={onShareClick}
          className="flex items-center gap-1.5 px-2.5 sm:px-4 py-2 rounded-lg bg-surface-2 text-foreground hover:bg-line transition-colors"
        >
          <Share2 className="h-4 w-4 flex-shrink-0" />
          <span className="hidden sm:inline text-sm font-medium">Share</span>
        </button>

        {/* Three-dot Menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            className="p-2 rounded-lg text-muted hover:bg-surface-2 transition-colors"
          >
            <MoreHorizontal className="h-5 w-5" />
          </button>

          {/* Dropdown Menu */}
          {isMenuOpen && (
            <div className="absolute right-0 top-full mt-2 w-48 py-2 rounded-xl bg-surface shadow-xl border border-line z-50 animate-fade-in-up">
              {/* Rename option */}
              {onRenameClick && (
                <button
                  onClick={() => {
                    setIsMenuOpen(false);
                    onRenameClick();
                  }}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-foreground hover:bg-surface-2 transition-colors"
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
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-foreground hover:bg-surface-2 transition-colors"
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
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-foreground hover:bg-surface-2 transition-colors"
                >
                  <Archive className="h-4 w-4" />
                  <span className="text-sm">{isArchived ? 'Unarchive' : 'Archive'}</span>
                </button>
              )}

              {/* Divider */}
              {onDeleteClick && (
                <>
                  <div className="h-px bg-line my-2" />

                  {/* Delete option */}
                  <button
                    onClick={() => {
                      setIsMenuOpen(false);
                      onDeleteClick();
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-danger hover:bg-danger-bg transition-colors"
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
