"use client";

import { useState, useEffect } from "react";
import { X, FileText, Image, FileVideo, FileAudio, File, FileCode, FileSpreadsheet } from "lucide-react";

export type UploadedFileItem = {
  id?: string;
  file: File;
  status: "uploading" | "ready" | "error";
  error?: string;
};

interface FilePreviewGridProps {
  files: UploadedFileItem[];
  onRemoveFile: (index: number) => void;
}

// Format file size to human readable
function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

// Get appropriate icon for file type
function getFileIcon(file: File) {
  const type = file.type;
  const name = file.name.toLowerCase();

  if (type.startsWith("image/")) return Image;
  if (type.startsWith("video/")) return FileVideo;
  if (type.startsWith("audio/")) return FileAudio;
  if (type === "application/pdf") return FileText;
  if (name.endsWith(".docx") || name.endsWith(".doc")) return FileText;
  if (name.endsWith(".pptx") || name.endsWith(".ppt")) return FileText;
  if (name.endsWith(".xlsx") || name.endsWith(".xls") || name.endsWith(".csv")) return FileSpreadsheet;
  if (name.endsWith(".py") || name.endsWith(".js") || name.endsWith(".ts") || name.endsWith(".jsx") || name.endsWith(".tsx")) return FileCode;
  if (name.endsWith(".json") || name.endsWith(".xml") || name.endsWith(".yaml") || name.endsWith(".yml")) return FileCode;
  return File;
}

// Get file type color
function getFileTypeColor(file: File): string {
  const type = file.type;
  const name = file.name.toLowerCase();

  if (type.startsWith("image/")) return "bg-pink-500";
  if (type.startsWith("video/")) return "bg-purple-500";
  if (type.startsWith("audio/")) return "bg-green-500";
  if (type === "application/pdf") return "bg-red-500";
  if (name.endsWith(".docx") || name.endsWith(".doc")) return "bg-blue-500";
  if (name.endsWith(".pptx") || name.endsWith(".ppt")) return "bg-orange-500";
  if (name.endsWith(".xlsx") || name.endsWith(".xls") || name.endsWith(".csv")) return "bg-emerald-500";
  if (name.endsWith(".py")) return "bg-yellow-500";
  if (name.endsWith(".js") || name.endsWith(".ts") || name.endsWith(".jsx") || name.endsWith(".tsx")) return "bg-cyan-500";
  return "bg-zinc-500";
}

interface ImagePreviewProps {
  file: File;
  status: UploadedFileItem["status"];
  error?: string;
  onRemove: () => void;
}

function ImagePreview({ file, status, error, onRemove }: ImagePreviewProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  return (
    <div className="relative group w-20 h-20 rounded-xl overflow-hidden shadow-md border border-zinc-200 dark:border-zinc-700 flex-shrink-0">
      {previewUrl && (
        <img
          src={previewUrl}
          alt={file.name}
          className="w-full h-full object-cover"
        />
      )}
      {/* Hover overlay */}
      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
        <button
          type="button"
          onClick={onRemove}
          className="p-1.5 rounded-full bg-white/90 text-zinc-700 hover:bg-white transition-colors"
          title="Remove file"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      {/* File name tooltip on hover */}
      <div className="absolute bottom-0 left-0 right-0 px-1 py-0.5 bg-gradient-to-t from-black/60 to-transparent">
        <p className="text-[10px] text-white truncate">{file.name}</p>
      </div>
      {status === "uploading" && (
        <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
        </div>
      )}
      {status === "error" && (
        <div className="absolute inset-0 bg-red-500/70 flex items-center justify-center">
          <span className="text-[10px] text-white">Upload failed</span>
        </div>
      )}
    </div>
  );
}

interface DocumentPreviewProps {
  file: File;
  status: UploadedFileItem["status"];
  error?: string;
  onRemove: () => void;
}

function DocumentPreview({ file, status, error, onRemove }: DocumentPreviewProps) {
  const IconComponent = getFileIcon(file);
  const colorClass = getFileTypeColor(file);

  return (
    <div className="relative flex items-center gap-2 px-3 py-2 rounded-xl bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 group hover:bg-zinc-150 dark:hover:bg-zinc-750 transition-colors max-w-[200px]">
      {/* Icon */}
      <div className={`flex-shrink-0 w-8 h-8 rounded-lg ${colorClass} flex items-center justify-center`}>
        <IconComponent className="h-4 w-4 text-white" />
      </div>

      {/* File info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-zinc-700 dark:text-zinc-200 truncate">
          {file.name}
        </p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          {formatFileSize(file.size)}
        </p>
        {status === "uploading" && (
          <p className="text-[10px] text-zinc-500 dark:text-zinc-400">Uploading…</p>
        )}
        {status === "error" && (
          <p className="text-[10px] text-red-500">{error || "Upload failed"}</p>
        )}
      </div>

      {/* Remove button */}
      <button
        type="button"
        onClick={onRemove}
        className="flex-shrink-0 p-1 rounded-full text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors opacity-0 group-hover:opacity-100"
        title="Remove file"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export function FilePreviewGrid({ files, onRemoveFile }: FilePreviewGridProps) {
  if (files.length === 0) return null;

  // Separate images from documents
  const imageFiles = files.filter((f) => f.file.type.startsWith("image/"));
  const documentFiles = files.filter((f) => !f.file.type.startsWith("image/"));

  return (
    <div className="px-2 pb-3 space-y-2 animate-fade-in-up">
      {/* Image previews row */}
      {imageFiles.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {imageFiles.map((item, index) => {
            const globalIndex = files.indexOf(item);
            return (
              <ImagePreview
                key={`img-${index}-${item.file.name}`}
                file={item.file}
                status={item.status}
                error={item.error}
                onRemove={() => onRemoveFile(globalIndex)}
              />
            );
          })}
        </div>
      )}

      {/* Document previews row */}
      {documentFiles.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {documentFiles.map((item, index) => {
            const globalIndex = files.indexOf(item);
            return (
              <DocumentPreview
                key={`doc-${index}-${item.file.name}`}
                file={item.file}
                status={item.status}
                error={item.error}
                onRemove={() => onRemoveFile(globalIndex)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
