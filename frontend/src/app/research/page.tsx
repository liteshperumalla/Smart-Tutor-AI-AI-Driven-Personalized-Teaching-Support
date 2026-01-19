"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";

import {
  ResearchFolder,
  ResearchDocument,
  ResearchAnswer,
  ResearchPreview,
  KnowledgeBaseStats,
  AcademicPaper,
  AcademicSearchResponse,
  ComparisonResult,
  CitationResult,
  SummaryResult,
  QuestionsResult,
  StudyQuestion,
  FactCheckResult,
  fetchResearchFolders,
  fetchResearchDocuments,
  fetchKnowledgeBaseStats,
  runResearchQuery,
  uploadResearchFile,
  uploadResearchUrl,
  uploadResearchYoutube,
  clearResearchUploads,
  searchAcademicPapers,
  compareSources,
  extractCitations,
  generateSummary,
  generateStudyQuestions,
  factCheck,
} from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { PageShell } from "@/components/page-shell";
import {
  FileText, Upload, Globe, Youtube, Search, BookOpen, GitCompare, Quote,
  AlignLeft, HelpCircle, ShieldCheck, Send, Trash2, Download, FolderOpen
} from "lucide-react";

type ResearchChatMessage = {
  role: "user" | "assistant";
  content: string;
  sources?: Array<{
    title?: string;
    file_path?: string;
    excerpt?: string;
  }>;
  timestamp: string;
};

// File type SVG icons (no emojis)
function FileIcon({ type, className = "h-6 w-6" }: { type: string; className?: string }) {
  const iconType = type?.toLowerCase() || "default";

  switch (iconType) {
    case "pdf":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 13h6m-6 4h6m-6-8h2" />
        </svg>
      );
    case "docx":
    case "doc":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      );
    case "pptx":
    case "ppt":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9l-5-5H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 9h6v6H9z" />
        </svg>
      );
    case "txt":
    case "md":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6M7 21h10a2 2 0 002-2V9l-5-5H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        </svg>
      );
    case "csv":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      );
    case "png":
    case "jpg":
    case "jpeg":
    case "image":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      );
    case "webpage":
    case "url":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
        </svg>
      );
    case "youtube":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    default:
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9l-5-5H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        </svg>
      );
  }
}

function getFileIconType(previewType: string, title?: string): string {
  const type = previewType?.toLowerCase() || "";
  const validTypes = ["pdf", "docx", "doc", "pptx", "ppt", "txt", "md", "csv", "png", "jpg", "jpeg", "image", "webpage", "youtube", "url"];

  if (validTypes.includes(type)) return type;

  // Try to get extension from title
  if (title) {
    const ext = title.split(".").pop()?.toLowerCase();
    if (ext && validTypes.includes(ext)) return ext;
  }

  return "default";
}

function getFileTypeLabel(previewType: string): string {
  const labels: Record<string, string> = {
    pdf: "PDF Document",
    docx: "Word Document",
    doc: "Word Document",
    pptx: "PowerPoint",
    ppt: "PowerPoint",
    txt: "Text File",
    md: "Markdown",
    csv: "CSV Data",
    png: "Image",
    jpg: "Image",
    jpeg: "Image",
    image: "Image",
    webpage: "Web Page",
    youtube: "YouTube Video",
    url: "Web Content",
  };
  return labels[previewType?.toLowerCase()] || previewType?.toUpperCase() || "Document";
}

export default function ResearchPage() {
  const { token } = useAuthToken();
  const [folders, setFolders] = useState<ResearchFolder[]>([]);
  const [documents, setDocuments] = useState<ResearchDocument[]>([]);
  const [selectedFolders, setSelectedFolders] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<ResearchAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previews, setPreviews] = useState<ResearchPreview[]>([]);
  const [fileToUpload, setFileToUpload] = useState<File | null>(null);
  const [urlInput, setUrlInput] = useState("");
  const [youtubeInput, setYoutubeInput] = useState("");
  const [uploadingFile, setUploadingFile] = useState(false);
  const [submittingUrl, setSubmittingUrl] = useState(false);
  const [submittingYoutube, setSubmittingYoutube] = useState(false);
  const [kbStats, setKbStats] = useState<KnowledgeBaseStats | null>(null);
  const [kbError, setKbError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  // Research Chat State
  const [researchChatHistory, setResearchChatHistory] = useState<ResearchChatMessage[]>([]);
  const [showResearchChat, setShowResearchChat] = useState(false);

  // Toggle for querying uploaded sources vs course materials
  const [queryUploadedOnly, setQueryUploadedOnly] = useState(false);

  // Research Tools State
  type ResearchToolType = "academic" | "compare" | "citations" | "summary" | "questions" | "factcheck" | null;
  const [activeResearchTool, setActiveResearchTool] = useState<ResearchToolType>(null);
  const [toolLoading, setToolLoading] = useState(false);
  const [toolError, setToolError] = useState<string | null>(null);

  // Tool-specific state
  const [academicResults, setAcademicResults] = useState<AcademicPaper[]>([]);
  const [comparisonResult, setComparisonResult] = useState<ComparisonResult | null>(null);
  const [citationResult, setCitationResult] = useState<CitationResult | null>(null);
  const [summaryResult, setSummaryResult] = useState<SummaryResult | null>(null);
  const [questionsResult, setQuestionsResult] = useState<StudyQuestion[]>([]);
  const [factCheckResult, setFactCheckResult] = useState<FactCheckResult | null>(null);

  const uploadedDocuments = useMemo(
    () => documents.filter((doc) => (doc.file_path || "").includes("knowledge_uploads")),
    [documents]
  );
  const uploadedCount = Math.max(uploadedDocuments.length, previews.length);

  // Tool input state
  const [academicQuery, setAcademicQuery] = useState("");
  const [academicSources, setAcademicSources] = useState<string[]>(["arxiv", "pubmed", "scholar"]);
  const [compareTopic, setCompareTopic] = useState("");
  const [citationFormat, setCitationFormat] = useState("apa");
  const [summaryMode, setSummaryMode] = useState("executive");
  const [questionDifficulty, setQuestionDifficulty] = useState("medium");
  const [questionTypes, setQuestionTypes] = useState<string[]>(["mcq", "short_answer"]);
  const [questionCount, setQuestionCount] = useState(5);
  const [factCheckClaim, setFactCheckClaim] = useState("");
  const [factCheckIncludeWeb, setFactCheckIncludeWeb] = useState(false);

  type Channel = "file" | "url" | "youtube";
  type StatusRecord = {
    state: "idle" | "processing" | "success" | "error";
    message?: string;
    timestamp?: string;
  };
  const [ingestionStatus, setIngestionStatus] = useState<Record<Channel, StatusRecord>>({
    file: { state: "idle" },
    url: { state: "idle" },
    youtube: { state: "idle" },
  });
  const [statusLog, setStatusLog] = useState<
    Array<{ id: string; channel: Channel; state: StatusRecord["state"]; message: string; timestamp: string }>
  >([]);

  useEffect(() => {
    if (!token) return;
    let mounted = true;
    fetchResearchFolders(token)
      .then((res) => {
        if (!mounted) return;
        // Filter out knowledge_uploads folder from main display
        const filteredFolders = (res.folders || []).filter(
          (folder) => !folder.label.toLowerCase().includes("knowledge_uploads")
        );
        setFolders(filteredFolders);
        if (filteredFolders?.length) {
          setSelectedFolders([filteredFolders[0].path]);
        }
      })
      .catch(() => mounted && setError("Unable to load folders"));

    fetchResearchDocuments(token)
      .then((res) => mounted && setDocuments(res.documents || []))
      .catch(() => {});

    fetchKnowledgeBaseStats(token)
      .then((stats) => {
        if (!mounted) return;
        setKbStats(stats);
        setKbError(null);
      })
      .catch((err) => {
        if (!mounted) return;
        setKbError(err instanceof Error ? err.message : "Unable to load knowledge base stats");
      });

    return () => {
      mounted = false;
    };
  }, [token]);

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [researchChatHistory]);

  const folderLookup = useMemo(() => new Map(folders.map((f) => [f.path, f.label])), [folders]);
  const activeFolderLabels = useMemo(
    () => selectedFolders.map((path) => folderLookup.get(path) || path),
    [folderLookup, selectedFolders]
  );

  function toggleFolder(path: string) {
    setSelectedFolders((prev) =>
      prev.includes(path) ? prev.filter((item) => item !== path) : [...prev, path]
    );
  }

  const addPreview = (entry: ResearchPreview) => {
    setPreviews((prev) => [entry, ...prev].slice(0, 6));
  };

  const generateId = () => {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return Math.random().toString(36).slice(2);
  };

  const updateStatus = (channel: Channel, state: StatusRecord["state"], message?: string) => {
    const entry: StatusRecord = { state, message, timestamp: new Date().toISOString() };
    setIngestionStatus((prev) => ({ ...prev, [channel]: entry }));
    if (state === "success" || state === "error") {
      setStatusLog((prev) =>
        [{ id: generateId(), channel, state, message: message || "", timestamp: entry.timestamp || "" }, ...prev].slice(
          0,
          6
        )
      );
    }
  };

  const renderStatus = (channel: Channel) => {
    const record = ingestionStatus[channel];
    if (!record || record.state === "idle") return null;
    const styles =
      record.state === "processing"
        ? "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800"
        : record.state === "success"
        ? "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800"
        : "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800";
    const text =
      record.message ||
      (record.state === "processing"
        ? "Processing..."
        : record.state === "success"
        ? "Ingestion completed."
        : "Unable to ingest.");
    return (
      <p className={`rounded-full border px-3 py-1 text-xs font-medium ${styles}`}>
        {text}
      </p>
    );
  };

  async function handleFileUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    console.log("handleFileUpload called", { token: !!token, fileToUpload: fileToUpload?.name });
    if (!token) {
      updateStatus("file", "error", "Please log in to upload files.");
      return;
    }
    if (!fileToUpload) {
      updateStatus("file", "error", "Select a file to upload.");
      return;
    }
    setUploadingFile(true);
    updateStatus("file", "processing", `Uploading ${fileToUpload.name}...`);
    try {
      console.log("Calling uploadResearchFile...");
      const preview = await uploadResearchFile({ token, file: fileToUpload });
      console.log("Upload success:", preview);
      addPreview(preview);
      setFileToUpload(null);
      updateStatus("file", "success", `Indexed ${fileToUpload.name}`);
      // Auto-enable query uploaded sources when file is uploaded
      setQueryUploadedOnly(true);
    } catch (err) {
      console.error("Upload error:", err);
      updateStatus("file", "error", err instanceof Error ? err.message : "File upload failed");
    } finally {
      setUploadingFile(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function handleUrlSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !urlInput.trim()) {
      updateStatus("url", "error", "Enter a valid URL.");
      return;
    }
    setSubmittingUrl(true);
    updateStatus("url", "processing", "Fetching URL preview...");
    try {
      const preview = await uploadResearchUrl({ token, url: urlInput.trim() });
      addPreview(preview);
      setUrlInput("");
      updateStatus("url", "success", "URL ingested.");
      setQueryUploadedOnly(true);
    } catch (err) {
      updateStatus("url", "error", err instanceof Error ? err.message : "Unable to ingest URL");
    } finally {
      setSubmittingUrl(false);
    }
  }

  async function handleYoutubeSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !youtubeInput.trim()) {
      updateStatus("youtube", "error", "Enter a YouTube URL.");
      return;
    }
    setSubmittingYoutube(true);
    updateStatus("youtube", "processing", "Retrieving transcript...");
    try {
      const preview = await uploadResearchYoutube({ token, url: youtubeInput.trim() });
      addPreview(preview);
      setYoutubeInput("");
      updateStatus("youtube", "success", "Transcript added.");
      setQueryUploadedOnly(true);
    } catch (err) {
      updateStatus("youtube", "error", err instanceof Error ? err.message : "Unable to ingest YouTube video");
    } finally {
      setSubmittingYoutube(false);
    }
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !query.trim()) {
      setError("Enter a research question");
      return;
    }
    setLoading(true);
    setError(null);

    // Add user message to chat history
    const userMessage: ResearchChatMessage = {
      role: "user",
      content: query,
      timestamp: new Date().toISOString(),
    };
    setResearchChatHistory((prev) => [...prev, userMessage]);
    setShowResearchChat(true);

    try {
      // If querying uploaded sources only, use knowledge_uploads folder
      const foldersToQuery = queryUploadedOnly
        ? undefined // The backend will handle this with knowledge_uploads
        : (selectedFolders.length ? selectedFolders : undefined);

      const response = await runResearchQuery({
        token,
        query,
        folders: foldersToQuery,
        // Pass flag to indicate uploaded sources query
        ...(queryUploadedOnly && { uploaded_only: true }),
      });
      setResult(response);

      // Add assistant message to chat history
      const assistantMessage: ResearchChatMessage = {
        role: "assistant",
        content: response.answer,
        sources: response.sources,
        timestamp: new Date().toISOString(),
      };
      setResearchChatHistory((prev) => [...prev, assistantMessage]);
      setQuery(""); // Clear input after successful query
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Query failed";
      setError(errorMsg);
      // Add error message to chat history
      const errorMessage: ResearchChatMessage = {
        role: "assistant",
        content: `Error: ${errorMsg}`,
        timestamp: new Date().toISOString(),
      };
      setResearchChatHistory((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  }

  // Export Research Chat History
  const handleExportChat = () => {
    if (researchChatHistory.length === 0) return;

    const exportContent = researchChatHistory
      .map((msg) => {
        const timestamp = new Date(msg.timestamp).toLocaleString();
        let content = `[${timestamp}] ${msg.role.toUpperCase()}:\n${msg.content}`;
        if (msg.sources && msg.sources.length > 0) {
          content += "\n\nSources:";
          msg.sources.forEach((source, idx) => {
            content += `\n  ${idx + 1}. ${source.title || source.file_path || "Unknown source"}`;
            if (source.excerpt) {
              content += `\n     "${source.excerpt.slice(0, 100)}..."`;
            }
          });
        }
        return content;
      })
      .join("\n\n" + "=".repeat(60) + "\n\n");

    const header = `Research Chat Export\nExported: ${new Date().toLocaleString()}\nSource: ${queryUploadedOnly ? "Uploaded Documents" : activeFolderLabels.join(", ") || "All"}\n${"=".repeat(60)}\n\n`;
    const fullContent = header + exportContent;

    const blob = new Blob([fullContent], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `research_chat_${new Date().toISOString().slice(0, 10)}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  // Clear Research Chat and uploaded documents
  const handleClearChat = async () => {
    setResearchChatHistory([]);
    setResult(null);
    setShowResearchChat(false);
    setPreviews([]);
    setStatusLog([]);

    // Clear uploaded documents from backend
    if (token) {
      try {
        await clearResearchUploads(token);
      } catch (err) {
        console.error("Failed to clear uploads:", err);
      }
    }
  };

  // Clear uploads when page is closed/navigated away
  useEffect(() => {
    const handleBeforeUnload = () => {
      // Use sendBeacon for reliable cleanup on page unload
      if (token) {
        const baseUrl =
          typeof window !== "undefined"
            ? `${window.location.protocol}//${window.location.hostname}:${process.env.NEXT_PUBLIC_BACKEND_PORT || "8010"}`
            : "";
        const clearUrl = `${baseUrl}/research/uploads/clear?token=${encodeURIComponent(token)}`;
        navigator.sendBeacon(clearUrl);
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [token]);

  // ==================== RESEARCH TOOLS HANDLERS ====================

  const handleAcademicSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (!token || !academicQuery.trim()) return;

    setToolLoading(true);
    setToolError(null);
    setAcademicResults([]);

    try {
      const response = await searchAcademicPapers({
        token,
        query: academicQuery,
        sources: academicSources,
        max_results: 10,
      });
      setAcademicResults(response.papers);
    } catch (err) {
      setToolError(err instanceof Error ? err.message : "Academic search failed");
    } finally {
      setToolLoading(false);
    }
  };

  const handleCompare = async (e: FormEvent) => {
    e.preventDefault();
    if (!token || !compareTopic.trim()) return;

    setToolLoading(true);
    setToolError(null);
    setComparisonResult(null);

    try {
      const response = await compareSources({
        token,
        topic: compareTopic,
        uploaded_only: true,
      });
      setComparisonResult(response);
    } catch (err) {
      setToolError(err instanceof Error ? err.message : "Comparison failed");
    } finally {
      setToolLoading(false);
    }
  };

  const handleExtractCitations = async () => {
    if (!token) return;

    setToolLoading(true);
    setToolError(null);
    setCitationResult(null);

    try {
      const response = await extractCitations({
        token,
        format_style: citationFormat,
      });
      setCitationResult(response);
    } catch (err) {
      setToolError(err instanceof Error ? err.message : "Citation extraction failed");
    } finally {
      setToolLoading(false);
    }
  };

  const handleGenerateSummary = async () => {
    if (!token) return;

    setToolLoading(true);
    setToolError(null);
    setSummaryResult(null);

    try {
      const response = await generateSummary({
        token,
        mode: summaryMode,
      });
      setSummaryResult(response);
    } catch (err) {
      setToolError(err instanceof Error ? err.message : "Summary generation failed");
    } finally {
      setToolLoading(false);
    }
  };

  const handleGenerateQuestions = async () => {
    if (!token) return;

    setToolLoading(true);
    setToolError(null);
    setQuestionsResult([]);

    try {
      const response = await generateStudyQuestions({
        token,
        difficulty: questionDifficulty,
        question_types: questionTypes,
        count: questionCount,
      });
      setQuestionsResult(response.questions);
    } catch (err) {
      setToolError(err instanceof Error ? err.message : "Question generation failed");
    } finally {
      setToolLoading(false);
    }
  };

  const handleFactCheck = async (e: FormEvent) => {
    e.preventDefault();
    if (!token || !factCheckClaim.trim()) return;

    setToolLoading(true);
    setToolError(null);
    setFactCheckResult(null);

    try {
      const response = await factCheck({
        token,
        claim: factCheckClaim,
        uploaded_only: true,
        include_web: factCheckIncludeWeb,
      });
      setFactCheckResult(response);
    } catch (err) {
      setToolError(err instanceof Error ? err.message : "Fact check failed");
    } finally {
      setToolLoading(false);
    }
  };

  const researchTools = [
    { id: "academic" as const, label: "Academic Search", description: "Search arXiv, PubMed, Scholar" },
    { id: "compare" as const, label: "Compare Sources", description: "Compare across documents" },
    { id: "citations" as const, label: "Extract Citations", description: "Find and format references" },
    { id: "summary" as const, label: "Summarize", description: "Generate document summaries" },
    { id: "questions" as const, label: "Generate Questions", description: "Create study questions" },
    { id: "factcheck" as const, label: "Fact Check", description: "Verify claims with sources" },
  ];

  // ==================== END RESEARCH TOOLS HANDLERS ====================

  // Render source link - handles both URLs and local files
  const renderSourceLink = (source: string | undefined, previewType: string) => {
    if (!source) return null;

    // If it's a URL (web page or YouTube), show as clickable link
    if (source.startsWith("http://") || source.startsWith("https://")) {
      return (
        <a
          href={source}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
        >
          <span>Open source</span>
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </a>
      );
    }

    // For local files, just show the filename
    const filename = source.split("/").pop() || source;
    return (
      <span className="text-zinc-500 dark:text-zinc-400">
        Source: {filename}
      </span>
    );
  };

  return (
    <PageShell contentClassName="gap-8">
        <header className="relative overflow-hidden rounded-3xl gradient-mesh p-12 animate-fade-in-down">
          <div className="absolute top-0 right-0 h-64 w-64 bg-emerald-400/20 rounded-full blur-3xl animate-float"></div>
          <div className="absolute bottom-0 left-0 h-48 w-48 bg-blue-400/20 rounded-full blur-3xl" style={{animationDelay: '1s'}}></div>

          <div className="relative z-10">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-white/80 px-4 py-2 text-sm font-medium text-emerald-700 backdrop-blur dark:border-emerald-800 dark:bg-zinc-900/80 dark:text-emerald-300 mb-4">
              <Search className="h-4 w-4" />
              Research Mode
            </div>
            <h1 className="font-display text-5xl font-bold text-zinc-900 dark:text-white">
              Investigate any topic
            </h1>
            <p className="mt-4 text-lg text-zinc-600 max-w-2xl dark:text-zinc-400">
              Upload documents, web pages, or YouTube videos and ask questions about them
            </p>
          </div>
        </header>

        {/* Upload Sources Section */}
        <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex flex-col gap-2 pb-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-400">Add sources</p>
              <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">Upload files, URLs, or transcripts</h2>
            </div>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">Documents are indexed for querying.</p>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <form onSubmit={handleFileUpload} className="rounded-2xl border border-zinc-100 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-800/50">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
                  <FileIcon type="docx" className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Upload document</p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">PDF, DOCX, PPTX, TXT, PNG, JPG</p>
                </div>
              </div>
              <input
                type="file"
                ref={fileInputRef}
                accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg,.md,.csv"
                className="mt-3 w-full text-xs text-zinc-600 dark:text-zinc-400 file:mr-3 file:rounded-full file:border-0 file:bg-zinc-200 file:px-4 file:py-2 file:text-sm file:font-medium file:text-zinc-700 hover:file:bg-zinc-300 dark:file:bg-zinc-700 dark:file:text-zinc-200"
                onChange={(event) => {
                  const file = event.target.files?.[0] || null;
                  setFileToUpload(file);
                }}
              />
              <button
                type="submit"
                disabled={uploadingFile || !fileToUpload}
                className="mt-4 w-full btn-primary disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:scale-100"
              >
                {uploadingFile ? (
                  <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Analyzing...</>
                ) : (
                  fileToUpload ? `Add ${fileToUpload.name}` : "Add file"
                )}
              </button>
              <div className="mt-3">{renderStatus("file")}</div>
            </form>

            <form onSubmit={handleUrlSubmit} className="rounded-2xl border border-zinc-100 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-800/50">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400">
                  <FileIcon type="webpage" className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Capture a web page</p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">Extract content from any URL</p>
                </div>
              </div>
              <input
                type="url"
                value={urlInput}
                onChange={(event) => setUrlInput(event.target.value)}
                placeholder="https://example.com/article"
                className="mt-3 w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-900 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white"
              />
              <button
                type="submit"
                disabled={submittingUrl || !urlInput.trim()}
                className="mt-4 w-full btn-primary disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:scale-100"
              >
                {submittingUrl ? (
                  <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Fetching...</>
                ) : (
                  "Add URL"
                )}
              </button>
              <div className="mt-3">{renderStatus("url")}</div>
            </form>

            <form onSubmit={handleYoutubeSubmit} className="rounded-2xl border border-zinc-100 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-800/50">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400">
                  <FileIcon type="youtube" className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">YouTube transcript</p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">Extract video captions</p>
                </div>
              </div>
              <input
                type="text"
                value={youtubeInput}
                onChange={(event) => setYoutubeInput(event.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                className="mt-3 w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-900 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white"
              />
              <button
                type="submit"
                disabled={submittingYoutube || !youtubeInput.trim()}
                className="mt-4 w-full btn-primary disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:scale-100"
              >
                {submittingYoutube ? (
                  <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Transcribing...</>
                ) : (
                  "Add YouTube"
                )}
              </button>
              <div className="mt-3">{renderStatus("youtube")}</div>
            </form>
          </div>
        </section>

        {/* Previews Section - Improved */}
        {previews.length > 0 && (
          <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6 shadow-sm dark:border-emerald-800 dark:bg-emerald-900/20">
            <div className="flex items-center justify-between pb-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 dark:bg-emerald-900/50 dark:text-emerald-400">
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-emerald-900 dark:text-emerald-100">Indexed Sources</h3>
                  <p className="text-sm text-emerald-700 dark:text-emerald-300">{uploadedCount} document(s) ready for querying</p>
                </div>
              </div>
              <button
                type="button"
                onClick={async () => {
                  setPreviews([]);
                  setStatusLog([]);
                  if (token) {
                    try {
                      await clearResearchUploads(token);
                    } catch (err) {
                      console.error("Failed to clear uploads:", err);
                    }
                  }
                }}
                className="text-xs text-emerald-600 hover:text-emerald-800 dark:text-emerald-400 dark:hover:text-emerald-200"
              >
                Clear all
              </button>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {previews.map((preview, index) => (
                <div
                  key={`${preview.title}-${index}`}
                  className="rounded-xl border border-emerald-200 bg-white p-4 shadow-sm dark:border-emerald-700 dark:bg-zinc-800"
                >
                  <div className="flex items-start gap-3">
                    <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-zinc-100 text-zinc-600 dark:bg-zinc-700 dark:text-zinc-300">
                      <FileIcon type={getFileIconType(preview.preview_type, preview.title)} className="h-5 w-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
                        {getFileTypeLabel(preview.preview_type)}
                      </p>
                      <h4 className="mt-1 text-sm font-semibold text-zinc-900 dark:text-white truncate" title={preview.title}>
                        {preview.title}
                      </h4>
                    </div>
                  </div>
                  {preview.thumbnail && (
                    <div className="mt-3 overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-700">
                      <Image
                        src={preview.thumbnail}
                        alt={preview.title}
                        width={300}
                        height={150}
                        className="h-24 w-full object-cover"
                      />
                    </div>
                  )}
                  <p className="mt-3 text-xs text-zinc-600 dark:text-zinc-400 line-clamp-3">
                    {preview.excerpt || "Content extracted and indexed."}
                  </p>
                  <div className="mt-3 text-xs">
                    {renderSourceLink(preview.source, preview.preview_type)}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Research Chat Section */}
        {(showResearchChat && researchChatHistory.length > 0) || loading ? (
          <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex flex-col gap-2 pb-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-400">Research Chat</p>
                <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">Conversation History</h2>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleExportChat}
                  disabled={researchChatHistory.length === 0}
                  className="rounded-full border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800"
                >
                  Export Chat
                </button>
                <button
                  type="button"
                  onClick={handleClearChat}
                  disabled={researchChatHistory.length === 0}
                  className="rounded-full border border-red-300 px-4 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50 disabled:opacity-50 dark:border-red-700 dark:text-red-400 dark:hover:bg-red-900/30"
                >
                  Clear Chat
                </button>
              </div>
            </div>

            <div className="max-h-96 overflow-y-auto rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-700 dark:bg-zinc-800/50">
              {researchChatHistory.map((msg, index) => (
                <div
                  key={index}
                  className={`mb-4 ${msg.role === "user" ? "text-right" : "text-left"}`}
                >
                  <div
                    className={`inline-block max-w-[85%] rounded-2xl p-4 ${
                      msg.role === "user"
                        ? "bg-blue-600 text-white dark:bg-blue-600 dark:text-white"
                        : "bg-white text-zinc-900 shadow-sm border border-zinc-200 dark:bg-zinc-700 dark:text-zinc-100 dark:border-zinc-600"
                    }`}
                  >
                    <p className={`mb-1 text-xs font-semibold ${msg.role === "user" ? "text-blue-100" : "text-zinc-500 dark:text-zinc-400"}`}>
                      {msg.role === "user" ? "You" : "Research Assistant"}
                    </p>
                    <p className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content}</p>
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-3 border-t border-zinc-200 pt-3 dark:border-zinc-600">
                        <p className="mb-2 text-xs font-semibold text-zinc-500 dark:text-zinc-400">Sources:</p>
                        {msg.sources.map((source, idx) => (
                          <div key={idx} className="mb-2 rounded-lg bg-zinc-100 p-2 text-xs dark:bg-zinc-600">
                            <p className="font-medium text-zinc-800 dark:text-zinc-200">
                              {source.title || source.file_path?.split("/").pop() || `Source ${idx + 1}`}
                            </p>
                            {source.excerpt && (
                              <p className="mt-1 text-zinc-600 dark:text-zinc-300 line-clamp-2">{source.excerpt}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    <p className={`mt-2 text-xs ${msg.role === "user" ? "text-blue-200" : "text-zinc-400 dark:text-zinc-500"}`}>
                      {new Date(msg.timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}

              {/* Loading Animation */}
              {loading && (
                <div className="mb-4 text-left">
                  <div className="inline-block max-w-[85%] rounded-2xl bg-white p-4 shadow-sm border border-zinc-200 dark:bg-zinc-700 dark:border-zinc-600">
                    <p className="mb-2 text-xs font-semibold text-zinc-500 dark:text-zinc-400">Research Assistant</p>
                    <div className="flex items-center gap-2">
                      <div className="flex gap-1">
                        <span className="h-2 w-2 rounded-full bg-zinc-400 animate-bounce dark:bg-zinc-500" style={{ animationDelay: "0ms" }}></span>
                        <span className="h-2 w-2 rounded-full bg-zinc-400 animate-bounce dark:bg-zinc-500" style={{ animationDelay: "150ms" }}></span>
                        <span className="h-2 w-2 rounded-full bg-zinc-400 animate-bounce dark:bg-zinc-500" style={{ animationDelay: "300ms" }}></span>
                      </div>
                      <span className="text-sm text-zinc-500 dark:text-zinc-400">Searching documents...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>
          </section>
        ) : null}

        {/* Query Section */}
        <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <form onSubmit={handleSearch} className="space-y-6">
            <div className="space-y-2">
              <label htmlFor="query" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Research question
              </label>
              <textarea
                id="query"
                rows={3}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="w-full rounded-2xl border border-zinc-200 px-4 py-3 text-sm text-zinc-900 outline-none focus:border-zinc-900 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:focus:border-zinc-500"
                placeholder={queryUploadedOnly ? "Ask questions about your uploaded documents..." : "Ask about INFO 5731 materials, assignments, grading, etc."}
              />
            </div>

            {/* Source Selection Toggle */}
            <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-700">
              <p className="mb-3 text-sm font-medium text-zinc-700 dark:text-zinc-300">Query source:</p>
              <div className="flex flex-wrap gap-3">
                <label
                  className={`flex cursor-pointer items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition ${
                    queryUploadedOnly
                      ? "bg-emerald-600 text-white border border-emerald-600 dark:bg-emerald-600 dark:text-white dark:border-emerald-600"
                      : "bg-zinc-100 text-zinc-700 border border-zinc-300 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:border-zinc-600 dark:hover:bg-zinc-700"
                  }`}
                >
                  <input
                    type="radio"
                    name="querySource"
                    checked={queryUploadedOnly}
                    onChange={() => setQueryUploadedOnly(true)}
                    className="hidden"
                  />
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <span>Uploaded sources {previews.length > 0 && `(${previews.length})`}</span>
                </label>
                <label
                  className={`flex cursor-pointer items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition ${
                    !queryUploadedOnly
                      ? "bg-blue-600 text-white border border-blue-600 dark:bg-blue-600 dark:text-white dark:border-blue-600"
                      : "bg-zinc-100 text-zinc-700 border border-zinc-300 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:border-zinc-600 dark:hover:bg-zinc-700"
                  }`}
                >
                  <input
                    type="radio"
                    name="querySource"
                    checked={!queryUploadedOnly}
                    onChange={() => setQueryUploadedOnly(false)}
                    className="hidden"
                  />
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                  <span>Course materials</span>
                </label>
              </div>
            </div>

            {/* Folder Filter - Only show when querying course materials */}
            {!queryUploadedOnly && (
              <div className="space-y-2">
                <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Filter by module:</p>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {folders.map((folder) => (
                    <label
                      key={folder.path}
                      className={`flex cursor-pointer flex-col rounded-2xl border px-4 py-3 text-sm transition ${
                        selectedFolders.includes(folder.path)
                          ? "border-zinc-900 bg-zinc-900/5 dark:border-white dark:bg-white/5"
                          : "border-zinc-200 hover:border-zinc-300 dark:border-zinc-700 dark:hover:border-zinc-600"
                      }`}
                    >
                      <input
                        type="checkbox"
                        className="hidden"
                        checked={selectedFolders.includes(folder.path)}
                        onChange={() => toggleFolder(folder.path)}
                      />
                      <span className="font-semibold text-zinc-900 dark:text-white">{folder.label}</span>
                      <span className="text-xs text-zinc-500 dark:text-zinc-400">{folder.file_count} files</span>
                    </label>
                  ))}
                  {folders.length === 0 && (
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">No folders detected.</p>
                  )}
                </div>
              </div>
            )}

            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || (queryUploadedOnly && previews.length === 0)}
              className="w-full btn-primary disabled:cursor-not-allowed disabled:opacity-70 disabled:hover:scale-100"
            >
              {loading ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Searching...</>
              ) : (
                <>{queryUploadedOnly ? "Ask about uploaded documents" : "Search course materials"} <span className="transition-transform group-hover:translate-x-1">→</span></>
              )}
            </button>

            {queryUploadedOnly && previews.length === 0 && (
              <p className="text-center text-xs text-zinc-500 dark:text-zinc-400">
                Upload a document, URL, or YouTube video first to ask questions about it.
              </p>
            )}
          </form>
        </section>

        {/* ==================== RESEARCH TOOLS SECTION ==================== */}
        <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex flex-col gap-2 pb-4">
            <p className="text-xs uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-400">Advanced Tools</p>
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">Research Capabilities</h2>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">Powerful tools to analyze your uploaded documents</p>
          </div>

          {/* Tool Selector */}
          <div className="flex flex-wrap gap-2 mb-6">
            {researchTools.map((tool) => (
              <button
                key={tool.id}
                type="button"
                onClick={() => setActiveResearchTool(activeResearchTool === tool.id ? null : tool.id)}
                className={`px-4 py-2 rounded-full text-sm font-medium transition ${
                  activeResearchTool === tool.id
                    ? "bg-blue-600 text-white"
                    : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
                }`}
              >
                {tool.label}
              </button>
            ))}
          </div>

          {/* Tool Error Display */}
          {toolError && (
            <div className="mb-4 rounded-xl bg-red-50 p-4 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
              {toolError}
            </div>
          )}

          {/* Academic Search Panel */}
          {activeResearchTool === "academic" && (
            <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-700">
              <h3 className="text-lg font-semibold mb-3 text-zinc-900 dark:text-white">Academic Paper Search</h3>
              <form onSubmit={handleAcademicSearch} className="space-y-4">
                <input
                  type="text"
                  value={academicQuery}
                  onChange={(e) => setAcademicQuery(e.target.value)}
                  placeholder="Search for academic papers..."
                  className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-white"
                />
                <div className="flex flex-wrap gap-2">
                  {["arxiv", "pubmed", "scholar"].map((source) => (
                    <label key={source} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={academicSources.includes(source)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setAcademicSources([...academicSources, source]);
                          } else {
                            setAcademicSources(academicSources.filter((s) => s !== source));
                          }
                        }}
                        className="rounded"
                      />
                      <span className="text-sm text-zinc-700 dark:text-zinc-300 capitalize">{source}</span>
                    </label>
                  ))}
                </div>
                <button
                  type="submit"
                  disabled={toolLoading || !academicQuery.trim()}
                  className="rounded-xl bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {toolLoading ? "Searching..." : "Search Papers"}
                </button>
              </form>

              {academicResults.length > 0 && (
                <div className="mt-4 space-y-3">
                  <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Found {academicResults.length} papers:</p>
                  {academicResults.map((paper, idx) => (
                    <div key={idx} className="rounded-lg bg-zinc-50 p-4 dark:bg-zinc-800">
                      <a href={paper.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline font-medium">
                        {paper.title}
                      </a>
                      <p className="text-xs text-zinc-500 mt-1">{paper.authors?.join(", ")} • {paper.source} • {paper.published_date}</p>
                      <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-2 line-clamp-3">{paper.abstract}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Compare Sources Panel */}
          {activeResearchTool === "compare" && (
            <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-700">
              <h3 className="text-lg font-semibold mb-3 text-zinc-900 dark:text-white">Compare Sources</h3>
              <form onSubmit={handleCompare} className="space-y-4">
                <input
                  type="text"
                  value={compareTopic}
                  onChange={(e) => setCompareTopic(e.target.value)}
                  placeholder="Enter a topic to compare across documents..."
                  className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-white"
                />
                <button
                  type="submit"
                  disabled={toolLoading || !compareTopic.trim() || uploadedCount < 1}
                  className="rounded-xl bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {toolLoading ? "Comparing..." : "Compare Documents"}
                </button>
                {uploadedCount < 1 && (
                  <p className="text-xs text-amber-600">Upload at least one document to compare</p>
                )}
              </form>

              {comparisonResult && (
                <div className="mt-4 space-y-4">
                  <p className="text-sm text-zinc-600 dark:text-zinc-400">Analyzed {comparisonResult.documents_analyzed} documents</p>
                  {comparisonResult.agreements.length > 0 && (
                    <div className="rounded-lg bg-emerald-50 p-4 dark:bg-emerald-900/20">
                      <p className="font-semibold text-emerald-800 dark:text-emerald-300 mb-2">Agreements</p>
                      <ul className="list-disc pl-5 text-sm text-emerald-700 dark:text-emerald-400 space-y-1">
                        {comparisonResult.agreements.map((a, i) => <li key={i}>{a}</li>)}
                      </ul>
                    </div>
                  )}
                  {comparisonResult.contradictions.length > 0 && (
                    <div className="rounded-lg bg-red-50 p-4 dark:bg-red-900/20">
                      <p className="font-semibold text-red-800 dark:text-red-300 mb-2">Contradictions</p>
                      <ul className="list-disc pl-5 text-sm text-red-700 dark:text-red-400 space-y-1">
                        {comparisonResult.contradictions.map((c, i) => <li key={i}>{c}</li>)}
                      </ul>
                    </div>
                  )}
                  {comparisonResult.summary && (
                    <div className="rounded-lg bg-zinc-100 p-4 dark:bg-zinc-800">
                      <p className="font-semibold text-zinc-800 dark:text-zinc-200 mb-2">Summary</p>
                      <p className="text-sm text-zinc-600 dark:text-zinc-400">{comparisonResult.summary}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Citations Panel */}
          {activeResearchTool === "citations" && (
            <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-700">
              <h3 className="text-lg font-semibold mb-3 text-zinc-900 dark:text-white">Extract Citations</h3>
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <label className="text-sm text-zinc-700 dark:text-zinc-300">Format:</label>
                  <select
                    value={citationFormat}
                    onChange={(e) => setCitationFormat(e.target.value)}
                    className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-white"
                  >
                    <option value="apa">APA</option>
                    <option value="mla">MLA</option>
                    <option value="chicago">Chicago</option>
                    <option value="ieee">IEEE</option>
                  </select>
                  <button
                    type="button"
                    onClick={handleExtractCitations}
                    disabled={toolLoading || uploadedCount < 1}
                    className="rounded-xl bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {toolLoading ? "Extracting..." : "Extract Citations"}
                  </button>
                </div>
                {uploadedCount < 1 && (
                  <p className="text-xs text-amber-600">Upload a document to extract citations</p>
                )}

                {citationResult && citationResult.citations.length > 0 && (
                  <div className="mt-4">
                    <div className="flex items-center justify-between mb-3">
                      <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                        Found {citationResult.count} citations ({citationResult.format.toUpperCase()})
                      </p>
                      <button
                        type="button"
                        onClick={() => {
                          const blob = new Blob([citationResult.exportable_bibliography], { type: "text/plain" });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = `bibliography_${citationFormat}.txt`;
                          a.click();
                        }}
                        className="text-sm text-blue-600 hover:underline"
                      >
                        Export Bibliography
                      </button>
                    </div>
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {citationResult.citations.map((c, i) => (
                        <div key={i} className="rounded-lg bg-zinc-50 p-3 text-sm dark:bg-zinc-800">
                          <p className="text-zinc-800 dark:text-zinc-200">{c.formatted}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Summary Panel */}
          {activeResearchTool === "summary" && (
            <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-700">
              <h3 className="text-lg font-semibold mb-3 text-zinc-900 dark:text-white">Generate Summary</h3>
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-4">
                  <label className="text-sm text-zinc-700 dark:text-zinc-300">Mode:</label>
                  {[
                    { value: "executive", label: "Executive" },
                    { value: "detailed", label: "Detailed" },
                    { value: "bullets", label: "Bullet Points" },
                  ].map((mode) => (
                    <button
                      key={mode.value}
                      type="button"
                      onClick={() => setSummaryMode(mode.value)}
                      className={`px-4 py-2 rounded-lg text-sm ${
                        summaryMode === mode.value
                          ? "bg-blue-600 text-white"
                          : "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                      }`}
                    >
                      {mode.label}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={handleGenerateSummary}
                    disabled={toolLoading || uploadedCount < 1}
                    className="rounded-xl bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 ml-auto"
                  >
                    {toolLoading ? "Generating..." : "Generate"}
                  </button>
                </div>
                {uploadedCount < 1 && (
                  <p className="text-xs text-amber-600">Upload a document to generate summary</p>
                )}

                {summaryResult && (
                  <div className="mt-4 rounded-lg bg-zinc-50 p-4 dark:bg-zinc-800">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs text-zinc-500">{summaryResult.mode} summary • {summaryResult.word_count} words</p>
                    </div>
                    <p className="text-sm text-zinc-700 dark:text-zinc-300 whitespace-pre-wrap">{summaryResult.summary}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Questions Panel */}
          {activeResearchTool === "questions" && (
            <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-700">
              <h3 className="text-lg font-semibold mb-3 text-zinc-900 dark:text-white">Generate Study Questions</h3>
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-4">
                  <div className="flex items-center gap-2">
                    <label className="text-sm text-zinc-700 dark:text-zinc-300">Difficulty:</label>
                    <select
                      value={questionDifficulty}
                      onChange={(e) => setQuestionDifficulty(e.target.value)}
                      className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-white"
                    >
                      <option value="easy">Easy</option>
                      <option value="medium">Medium</option>
                      <option value="hard">Hard</option>
                    </select>
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="text-sm text-zinc-700 dark:text-zinc-300">Count:</label>
                    <input
                      type="number"
                      value={questionCount}
                      onChange={(e) => setQuestionCount(Math.min(20, Math.max(1, parseInt(e.target.value) || 5)))}
                      min={1}
                      max={20}
                      className="w-16 rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-white"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleGenerateQuestions}
                    disabled={toolLoading || uploadedCount < 1}
                    className="rounded-xl bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 ml-auto"
                  >
                    {toolLoading ? "Generating..." : "Generate Questions"}
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {["mcq", "short_answer", "essay"].map((type) => (
                    <label key={type} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={questionTypes.includes(type)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setQuestionTypes([...questionTypes, type]);
                          } else {
                            setQuestionTypes(questionTypes.filter((t) => t !== type));
                          }
                        }}
                        className="rounded"
                      />
                      <span className="text-sm text-zinc-700 dark:text-zinc-300">
                        {type === "mcq" ? "Multiple Choice" : type === "short_answer" ? "Short Answer" : "Essay"}
                      </span>
                    </label>
                  ))}
                </div>
                {uploadedCount < 1 && (
                  <p className="text-xs text-amber-600">Upload a document to generate questions</p>
                )}

                {questionsResult.length > 0 && (
                  <div className="mt-4 space-y-3">
                    {questionsResult.map((q, i) => (
                      <div key={i} className="rounded-lg bg-zinc-50 p-4 dark:bg-zinc-800">
                        <div className="flex items-start gap-3">
                          <span className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-medium dark:bg-blue-900 dark:text-blue-300">
                            {i + 1}
                          </span>
                          <div className="flex-1">
                            <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{q.question}</p>
                            <p className="text-xs text-zinc-500 mt-1">{q.type} • {q.difficulty}</p>
                            {q.options && q.options.length > 0 && (
                              <div className="mt-2 space-y-1">
                                {q.options.map((opt, j) => (
                                  <p key={j} className="text-sm text-zinc-600 dark:text-zinc-400">{opt}</p>
                                ))}
                              </div>
                            )}
                            {q.answer && (
                              <details className="mt-2">
                                <summary className="text-xs text-blue-600 cursor-pointer">Show Answer</summary>
                                <p className="text-sm text-emerald-600 dark:text-emerald-400 mt-1">{q.answer}</p>
                                {q.explanation && <p className="text-xs text-zinc-500 mt-1">{q.explanation}</p>}
                              </details>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Fact Check Panel */}
          {activeResearchTool === "factcheck" && (
            <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-700">
              <h3 className="text-lg font-semibold mb-3 text-zinc-900 dark:text-white">Fact Check</h3>
              <form onSubmit={handleFactCheck} className="space-y-4">
                <textarea
                  value={factCheckClaim}
                  onChange={(e) => setFactCheckClaim(e.target.value)}
                  placeholder="Enter a claim to verify against your documents..."
                  rows={3}
                  className="w-full rounded-xl border border-zinc-300 px-4 py-3 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-white"
                />
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={factCheckIncludeWeb}
                      onChange={(e) => setFactCheckIncludeWeb(e.target.checked)}
                      className="rounded"
                    />
                    <span className="text-sm text-zinc-700 dark:text-zinc-300">Include web search</span>
                  </label>
                  <button
                    type="submit"
                    disabled={toolLoading || factCheckClaim.length < 10}
                    className="rounded-xl bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {toolLoading ? "Checking..." : "Verify Claim"}
                  </button>
                </div>
              </form>

              {factCheckResult && (
                <div className="mt-4 space-y-4">
                  <div className={`rounded-lg p-4 ${
                    factCheckResult.verdict === "supported" ? "bg-emerald-50 dark:bg-emerald-900/20" :
                    factCheckResult.verdict === "contradicted" ? "bg-red-50 dark:bg-red-900/20" :
                    "bg-amber-50 dark:bg-amber-900/20"
                  }`}>
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                        factCheckResult.verdict === "supported" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-800 dark:text-emerald-300" :
                        factCheckResult.verdict === "contradicted" ? "bg-red-100 text-red-700 dark:bg-red-800 dark:text-red-300" :
                        "bg-amber-100 text-amber-700 dark:bg-amber-800 dark:text-amber-300"
                      }`}>
                        {factCheckResult.verdict === "supported" ? (
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                        ) : factCheckResult.verdict === "contradicted" ? (
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                        ) : (
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                        )}
                      </div>
                      <div>
                        <p className={`font-semibold capitalize ${
                          factCheckResult.verdict === "supported" ? "text-emerald-800 dark:text-emerald-300" :
                          factCheckResult.verdict === "contradicted" ? "text-red-800 dark:text-red-300" :
                          "text-amber-800 dark:text-amber-300"
                        }`}>
                          {factCheckResult.verdict}
                        </p>
                        <p className="text-sm text-zinc-600 dark:text-zinc-400">Confidence: {Math.round(factCheckResult.confidence * 100)}%</p>
                      </div>
                    </div>
                  </div>

                  {factCheckResult.supporting_sources.length > 0 && (
                    <div>
                      <p className="text-sm font-medium text-emerald-700 dark:text-emerald-400 mb-2">Supporting Sources ({factCheckResult.supporting_sources.length})</p>
                      {factCheckResult.supporting_sources.map((s, i) => (
                        <div key={i} className="rounded-lg bg-emerald-50/50 p-3 mb-2 dark:bg-emerald-900/10">
                          <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{s.title}</p>
                          <p className="text-xs text-zinc-600 dark:text-zinc-400 mt-1 line-clamp-2">{s.excerpt}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {factCheckResult.contradicting_sources.length > 0 && (
                    <div>
                      <p className="text-sm font-medium text-red-700 dark:text-red-400 mb-2">Contradicting Sources ({factCheckResult.contradicting_sources.length})</p>
                      {factCheckResult.contradicting_sources.map((s, i) => (
                        <div key={i} className="rounded-lg bg-red-50/50 p-3 mb-2 dark:bg-red-900/10">
                          <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{s.title}</p>
                          <p className="text-xs text-zinc-600 dark:text-zinc-400 mt-1 line-clamp-2">{s.excerpt}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </section>
        {/* ==================== END RESEARCH TOOLS SECTION ==================== */}

        {/* Ingestion Activity */}
        {statusLog.length > 0 && (
          <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-white">Recent activity</h3>
            <div className="mt-4 space-y-2">
              {statusLog.map((entry) => (
                <div
                  key={entry.id}
                  className={`flex items-center gap-3 rounded-xl p-3 text-sm ${
                    entry.state === "success"
                      ? "bg-emerald-50 dark:bg-emerald-900/20"
                      : "bg-red-50 dark:bg-red-900/20"
                  }`}
                >
                  <div className={`flex h-8 w-8 items-center justify-center rounded-full ${
                    entry.state === "success"
                      ? "bg-emerald-100 text-emerald-600 dark:bg-emerald-900/50 dark:text-emerald-400"
                      : "bg-red-100 text-red-600 dark:bg-red-900/50 dark:text-red-400"
                  }`}>
                    {entry.state === "success" ? (
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    )}
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-zinc-900 dark:text-white">
                      {entry.channel === "file"
                        ? "File upload"
                        : entry.channel === "url"
                        ? "URL ingestion"
                        : "YouTube transcript"}
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      {entry.message} • {new Date(entry.timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
    </PageShell>
  );
}
