"use client";

import { useState, useRef, useCallback } from "react";
import {
  X,
  Upload,
  Link2,
  Youtube,
  FileText,
  Search,
  Lightbulb,
  Scale,
  GraduationCap,
  GitCompare,
  Loader2,
  CheckCircle,
  AlertCircle,
  FolderOpen,
} from "lucide-react";

/** A file, link or video added in research mode. It stays attached to the
 *  chat, so every question in it is answered with the source as context. */
export type ResearchSource = {
  key: string;
  /** Backend upload id, sent as uploaded_file_ids; set once it is ready. */
  id?: string;
  name: string;
  kind: "file" | "webpage" | "youtube";
  status: "adding" | "ready" | "error";
  error?: string;
};

interface ResearchSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onFilesAdded: (files: File[]) => void;
  onUrlSubmit: (url: string) => void;
  onRemoveSource: (key: string) => void;
  /** Puts a research tool's prompt in the composer. */
  onToolSelect: (prompt: string) => void;
  sources: ResearchSource[];
}

const SOURCE_ICONS = { file: FileText, webpage: Link2, youtube: Youtube } as const;

interface ResearchTool {
  id: string;
  name: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  /** Put in the composer; a prompt ending in ": " waits for the topic. */
  prompt: string;
  /** Works on the chat's sources, so it needs at least one. */
  needsSources: boolean;
}

const RESEARCH_TOOLS: ResearchTool[] = [
  {
    id: "summarize",
    name: "Summarize",
    description: "Key points and main ideas of your sources",
    icon: FileText,
    prompt: "Summarize the key points and main ideas from my sources.",
    needsSources: true,
  },
  {
    id: "fact-check",
    name: "Fact Check",
    description: "Check the claims in your sources",
    icon: Scale,
    prompt:
      "Fact-check the main claims in my sources. For each, say whether it is supported, disputed or unclear, and why.",
    needsSources: true,
  },
  {
    id: "compare",
    name: "Compare",
    description: "Compare your sources and the course material",
    icon: GitCompare,
    prompt: "Compare and contrast the viewpoints in my sources with each other and with the course material.",
    needsSources: true,
  },
  {
    id: "academic",
    name: "Academic",
    description: "Scholarly analysis with citations",
    icon: GraduationCap,
    prompt: "Give an academic analysis, citing my sources and the course material, of: ",
    needsSources: false,
  },
  {
    id: "explain",
    name: "Explain",
    description: "Simple explanation of a complex topic",
    icon: Lightbulb,
    prompt: "Explain in simple terms: ",
    needsSources: false,
  },
  {
    id: "deep-dive",
    name: "Deep Dive",
    description: "Comprehensive research and analysis",
    icon: Search,
    prompt: "Give a comprehensive deep dive, with detailed analysis, into: ",
    needsSources: false,
  },
];

export function ResearchSidebar({
  isOpen,
  onClose,
  onFilesAdded,
  onUrlSubmit,
  onRemoveSource,
  onToolSelect,
  sources,
}: ResearchSidebarProps) {
  const [urlInput, setUrlInput] = useState("");
  const [youtubeInput, setYoutubeInput] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = event.target.files;
      if (files && files.length > 0) {
        onFilesAdded(Array.from(files));
      }
      // Reset input
      if (event.target) {
        event.target.value = "";
      }
    },
    [onFilesAdded]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);

      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        onFilesAdded(Array.from(files));
      }
    },
    [onFilesAdded]
  );

  const handleUrlSubmit = useCallback(() => {
    if (urlInput.trim()) {
      onUrlSubmit(urlInput.trim());
      setUrlInput("");
    }
  }, [urlInput, onUrlSubmit]);

  const handleYoutubeSubmit = useCallback(() => {
    if (youtubeInput.trim()) {
      onUrlSubmit(youtubeInput.trim());
      setYoutubeInput("");
    }
  }, [youtubeInput, onUrlSubmit]);

  const handleToolClick = useCallback(
    (tool: ResearchTool) => onToolSelect(tool.prompt),
    [onToolSelect]
  );

  const readyCount = sources.filter((source) => source.status === "ready").length;
  const addingCount = sources.filter((source) => source.status === "adding").length;

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Sidebar */}
      <div className="fixed right-0 top-0 h-full w-80 bg-surface border-l border-line z-50 shadow-2xl animate-slide-in-right overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-line">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Research Mode</h2>
            <p className="text-xs text-muted">Upload sources and research tools</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-surface-2 transition-colors"
          >
            <X className="h-5 w-5 text-muted" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {/* Upload Section */}
          <div>
            <h3 className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
              <Upload className="h-4 w-4" />
              Upload Sources
            </h3>

            {/* Hidden file input */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              className="hidden"
              multiple
              accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg,.gif,.webp,.csv,.xlsx,.xls,.json,.xml,.yaml,.yml,.md"
            />

            {/* Drop zone */}
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`
                border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all
                ${isDragging
                  ? "border-primary bg-primary-bg"
                  : "border-line hover:border-primary hover:bg-surface-2"
                }
              `}
            >
              <>
                  <FolderOpen className="h-8 w-8 text-muted mx-auto mb-2" />
                  <p className="text-sm text-muted mb-1">
                    Drop files here or click to browse
                  </p>
                  <p className="text-xs text-muted">
                    PDF, DOCX, PPTX, TXT, Images
                  </p>
                </>
            </div>
          </div>

          {/* URL Input */}
          <div>
            <h3 className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
              <Link2 className="h-4 w-4" />
              Add from URL
            </h3>
            <div className="flex gap-2">
              <input
                type="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="https://example.com/article"
                className="flex-1 px-3 py-2 text-sm rounded-lg border border-line bg-surface text-foreground placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                onKeyDown={(e) => e.key === "Enter" && handleUrlSubmit()}
              />
              <button
                onClick={handleUrlSubmit}
                disabled={!urlInput.trim()}
                className="px-3 py-2 rounded-lg bg-primary-solid text-white text-sm font-medium hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Add
              </button>
            </div>
          </div>

          {/* YouTube Input */}
          <div>
            <h3 className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
              <Youtube className="h-4 w-4 text-danger" />
              YouTube Video
            </h3>
            <div className="flex gap-2">
              <input
                type="url"
                value={youtubeInput}
                onChange={(e) => setYoutubeInput(e.target.value)}
                placeholder="https://youtube.com/watch?v=..."
                className="flex-1 px-3 py-2 text-sm rounded-lg border border-line bg-surface text-foreground placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-danger focus:border-transparent"
                onKeyDown={(e) => e.key === "Enter" && handleYoutubeSubmit()}
              />
              <button
                onClick={handleYoutubeSubmit}
                disabled={!youtubeInput.trim()}
                className="px-3 py-2 rounded-lg bg-danger-solid text-white text-sm font-medium hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Add
              </button>
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-line" />

          {/* Research Tools */}
          <div>
            <h3 className="text-sm font-medium text-foreground mb-3">
              Research Tools
            </h3>
            {readyCount === 0 && (
              <p className="mb-2 text-xs text-muted">
                Add a file, link or video to use Summarize, Fact Check and Compare.
              </p>
            )}
            <div className="grid grid-cols-2 gap-2">
              {RESEARCH_TOOLS.map((tool) => {
                const IconComponent = tool.icon;
                const unavailable = tool.needsSources && readyCount === 0;
                return (
                  <button
                    key={tool.id}
                    type="button"
                    onClick={() => handleToolClick(tool)}
                    disabled={unavailable}
                    title={unavailable ? "Add a source first" : tool.description}
                    className="flex flex-col items-center gap-1.5 p-3 rounded-xl border border-line hover:bg-surface-2 hover:border-primary/30 transition-all text-center group disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent disabled:hover:border-line"
                  >
                    <IconComponent className="h-5 w-5 text-muted group-hover:text-primary transition-colors" />
                    <span className="text-xs font-medium text-foreground">{tool.name}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer - this chat's sources */}
        <div className="px-4 py-3 border-t border-line bg-surface-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${readyCount > 0 ? "bg-success" : "bg-line"}`} />
              <span className="text-sm text-muted" aria-live="polite">
                {readyCount} active source{readyCount !== 1 ? "s" : ""}
                {addingCount > 0 ? ` · ${addingCount} adding` : ""}
              </span>
            </div>
            {readyCount > 0 && (
              <span className="text-xs text-primary font-medium">Used for this chat</span>
            )}
          </div>
          {sources.length > 0 && (
            <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto" aria-label="Sources in this chat">
              {sources.map((source) => {
                const Icon = SOURCE_ICONS[source.kind];
                return (
                  <li key={source.key} className="flex items-center gap-2 rounded-md bg-surface px-2 py-1.5 text-xs">
                    <Icon className="h-3.5 w-3.5 shrink-0 text-muted" />
                    <span className="min-w-0 flex-1 truncate text-foreground" title={source.error || source.name}>
                      {source.name}
                    </span>
                    {source.status === "adding" && (
                      <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" aria-label="Adding" />
                    )}
                    {source.status === "ready" && (
                      <CheckCircle className="h-3.5 w-3.5 shrink-0 text-success" aria-label="Ready" />
                    )}
                    {source.status === "error" && (
                      <AlertCircle className="h-3.5 w-3.5 shrink-0 text-danger" aria-label={source.error || "Failed"} />
                    )}
                    <button
                      type="button"
                      onClick={() => onRemoveSource(source.key)}
                      className="shrink-0 rounded p-0.5 text-muted hover:bg-surface-2 hover:text-foreground"
                      aria-label={`Remove ${source.name}`}
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </>
  );
}
