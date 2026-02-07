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

interface ResearchSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onFilesAdded: (files: File[]) => void;
  onUrlSubmit: (url: string) => void;
  activeSourceCount: number;
}

interface ResearchTool {
  id: string;
  name: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  prompt: string;
}

const RESEARCH_TOOLS: ResearchTool[] = [
  {
    id: "summarize",
    name: "Summarize",
    description: "Get key points and main ideas",
    icon: FileText,
    prompt: "Please summarize the key points and main ideas from the sources provided.",
  },
  {
    id: "fact-check",
    name: "Fact Check",
    description: "Verify claims and find evidence",
    icon: Scale,
    prompt: "Please fact-check the claims made and provide supporting evidence or corrections.",
  },
  {
    id: "academic",
    name: "Academic",
    description: "Scholarly analysis and citations",
    icon: GraduationCap,
    prompt: "Please provide an academic analysis with proper citations and scholarly perspective.",
  },
  {
    id: "compare",
    name: "Compare",
    description: "Compare different sources or viewpoints",
    icon: GitCompare,
    prompt: "Please compare and contrast the different sources and viewpoints on this topic.",
  },
  {
    id: "explain",
    name: "Explain",
    description: "Simple explanation of complex topics",
    icon: Lightbulb,
    prompt: "Please explain this topic in simple terms that are easy to understand.",
  },
  {
    id: "deep-dive",
    name: "Deep Dive",
    description: "Comprehensive research and analysis",
    icon: Search,
    prompt: "Please conduct a comprehensive deep dive into this topic with detailed analysis.",
  },
];

type UploadStatus = "idle" | "uploading" | "success" | "error";

interface UploadState {
  status: UploadStatus;
  message: string;
}

export function ResearchSidebar({
  isOpen,
  onClose,
  onFilesAdded,
  onUrlSubmit,
  activeSourceCount,
}: ResearchSidebarProps) {
  const [urlInput, setUrlInput] = useState("");
  const [youtubeInput, setYoutubeInput] = useState("");
  const [uploadState, setUploadState] = useState<UploadState>({ status: "idle", message: "" });
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = event.target.files;
      if (files && files.length > 0) {
        setUploadState({ status: "uploading", message: "Processing files..." });

        // Simulate processing delay
        setTimeout(() => {
          onFilesAdded(Array.from(files));
          setUploadState({ status: "success", message: `${files.length} file(s) added` });

          // Reset after showing success
          setTimeout(() => {
            setUploadState({ status: "idle", message: "" });
          }, 2000);
        }, 500);
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
        setUploadState({ status: "uploading", message: "Processing files..." });

        setTimeout(() => {
          onFilesAdded(Array.from(files));
          setUploadState({ status: "success", message: `${files.length} file(s) added` });

          setTimeout(() => {
            setUploadState({ status: "idle", message: "" });
          }, 2000);
        }, 500);
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

  const handleToolClick = useCallback((tool: ResearchTool) => {
    // For now, just close the sidebar - the tool's prompt could be used later
    onClose();
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Sidebar */}
      <div className="fixed right-0 top-0 h-full w-80 bg-white dark:bg-zinc-900 border-l border-zinc-200 dark:border-zinc-700 z-50 shadow-2xl animate-slide-in-right overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-zinc-200 dark:border-zinc-700">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-white">Research Mode</h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">Upload sources and research tools</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            <X className="h-5 w-5 text-zinc-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {/* Upload Section */}
          <div>
            <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3 flex items-center gap-2">
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
                  ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20"
                  : "border-zinc-300 dark:border-zinc-600 hover:border-indigo-400 hover:bg-zinc-50 dark:hover:bg-zinc-800"
                }
              `}
            >
              {uploadState.status === "uploading" ? (
                <div className="flex flex-col items-center gap-2">
                  <Loader2 className="h-8 w-8 text-indigo-500 animate-spin" />
                  <p className="text-sm text-zinc-600 dark:text-zinc-400">{uploadState.message}</p>
                </div>
              ) : uploadState.status === "success" ? (
                <div className="flex flex-col items-center gap-2">
                  <CheckCircle className="h-8 w-8 text-green-500" />
                  <p className="text-sm text-green-600 dark:text-green-400">{uploadState.message}</p>
                </div>
              ) : uploadState.status === "error" ? (
                <div className="flex flex-col items-center gap-2">
                  <AlertCircle className="h-8 w-8 text-red-500" />
                  <p className="text-sm text-red-600 dark:text-red-400">{uploadState.message}</p>
                </div>
              ) : (
                <>
                  <FolderOpen className="h-8 w-8 text-zinc-400 mx-auto mb-2" />
                  <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-1">
                    Drop files here or click to browse
                  </p>
                  <p className="text-xs text-zinc-400 dark:text-zinc-500">
                    PDF, DOCX, PPTX, TXT, Images
                  </p>
                </>
              )}
            </div>
          </div>

          {/* URL Input */}
          <div>
            <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3 flex items-center gap-2">
              <Link2 className="h-4 w-4" />
              Add from URL
            </h3>
            <div className="flex gap-2">
              <input
                type="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="https://example.com/article"
                className="flex-1 px-3 py-2 text-sm rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-white placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                onKeyDown={(e) => e.key === "Enter" && handleUrlSubmit()}
              />
              <button
                onClick={handleUrlSubmit}
                disabled={!urlInput.trim()}
                className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Add
              </button>
            </div>
          </div>

          {/* YouTube Input */}
          <div>
            <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3 flex items-center gap-2">
              <Youtube className="h-4 w-4 text-red-500" />
              YouTube Video
            </h3>
            <div className="flex gap-2">
              <input
                type="url"
                value={youtubeInput}
                onChange={(e) => setYoutubeInput(e.target.value)}
                placeholder="https://youtube.com/watch?v=..."
                className="flex-1 px-3 py-2 text-sm rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-white placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
                onKeyDown={(e) => e.key === "Enter" && handleYoutubeSubmit()}
              />
              <button
                onClick={handleYoutubeSubmit}
                disabled={!youtubeInput.trim()}
                className="px-3 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Add
              </button>
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-zinc-200 dark:border-zinc-700" />

          {/* Research Tools */}
          <div>
            <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3">
              Research Tools
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {RESEARCH_TOOLS.map((tool) => {
                const IconComponent = tool.icon;
                return (
                  <button
                    key={tool.id}
                    onClick={() => handleToolClick(tool)}
                    className="flex flex-col items-center gap-1.5 p-3 rounded-xl border border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800 hover:border-indigo-300 dark:hover:border-indigo-700 transition-all text-center group"
                  >
                    <IconComponent className="h-5 w-5 text-zinc-500 group-hover:text-indigo-500 transition-colors" />
                    <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300">{tool.name}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer - Active Sources */}
        <div className="px-4 py-3 border-t border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-sm text-zinc-600 dark:text-zinc-400">
                {activeSourceCount} active source{activeSourceCount !== 1 ? "s" : ""}
              </span>
            </div>
            {activeSourceCount > 0 && (
              <span className="text-xs text-indigo-600 dark:text-indigo-400 font-medium">
                Ready for research
              </span>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
