"use client";

import { useCallback, useEffect, useMemo, useState, Suspense, useRef } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ChatMessageDTO,
  ChatAttachment,
  ChatSessionDTO,
  createChatSession,
  getApiBaseUrl,
  listChatSessions,
  getSessionFeedback,
  MessageFeedbackType,
  SessionFeedbackMap,
  deleteChatSession,
  renameChatSession,
  pinChatSession,
  archiveChatSession,
} from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { CHAT_SESSIONS_UPDATED_EVENT, dispatchChatSessionsUpdated } from "@/lib/events";
import { PageShell } from "@/components/page-shell";
import {
  MessageCircle, User, Bot, Send, Trash2, Mic, MicOff, Plus, X, Check, ChevronDown,
  Globe, Paperclip, ChevronRight, Image, FileText, FlaskConical, ShieldAlert
} from "lucide-react";
import { useUser } from "@/hooks/useUser";
import { useFeatureFlag } from "@/hooks/useFeatureFlag";
import { ResponseActionBar } from "@/components/chat/response-action-bar";
import { SourcesSidebar } from "@/components/chat/sources-sidebar";
import { ShareModal } from "@/components/chat/share-modal";
import { ReportModal } from "@/components/chat/report-modal";
import { ShareChatModal } from "@/components/chat/share-chat-modal";
import { ChatHeaderActions } from "@/components/chat/chat-header-actions";
import { DeleteChatModal } from "@/components/chat/delete-chat-modal";
import { RenameChatModal } from "@/components/chat/rename-chat-modal";
import { UserMessageActions, EditableUserMessage } from "@/components/chat/user-message-actions";
import { StreamingPhaseIndicator } from "@/components/chat/streaming-phase-indicator";
import { FilePreviewGrid, type UploadedFileItem } from "@/components/chat/file-preview-grid";
import { ResearchSidebar } from "@/components/chat/research-sidebar";
import { toast } from "sonner";

// Model ID → display name map (module-level for ChatBubble access)
const MODEL_DISPLAY_NAMES: Record<string, string> = {
  "us.meta.llama3-1-70b-instruct-v1:0": "Llama 70B",
  "us.anthropic.claude-3-5-sonnet-20241022-v2:0": "Sonnet 3.5",
  "us.anthropic.claude-3-haiku-20240307-v1:0": "Haiku 3",
  "us.anthropic.claude-opus-4-20250514-v1:0": "Opus 4",
};

function getFriendlyUserName(
  user: { display_name?: string; full_name?: string; username?: string; email?: string } | null
) {
  const directName = [user?.display_name, user?.full_name]
    .map((value) => value?.trim())
    .find((value) => value && !value.includes("@"));
  if (directName) return directName;

  const identifier = user?.username?.trim() || user?.email?.trim() || "";
  const localPart = identifier.includes("@") ? identifier.split("@", 1)[0] : identifier;
  const humanized = localPart
    .replace(/[_\-.]+/g, " ")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());

  return humanized || "there";
}

function ChatWorkspaceContent() {
  const searchParams = useSearchParams();
  const { token } = useAuthToken();
  const { user, isAdmin } = useUser();
  const agentsEnabled = useFeatureFlag("agent-system-enabled");
  const [sessions, setSessions] = useState<ChatSessionDTO[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [composerText, setComposerText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [viewerUrl, setViewerUrl] = useState<string | null>(null);
  const [viewerTitle, setViewerTitle] = useState<string | null>(null);

  // Feedback and action bar state
  const [feedbackMap, setFeedbackMap] = useState<SessionFeedbackMap>({});
  const [sourcesSidebarOpen, setSourcesSidebarOpen] = useState(false);
  const [selectedSources, setSelectedSources] = useState<Array<Record<string, unknown>>>([]);
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [shareModalMessage, setShareModalMessage] = useState("");
  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [reportMessageIndex, setReportMessageIndex] = useState<number>(0);
  const [shareChatModalOpen, setShareChatModalOpen] = useState(false);
  const [deleteChatModalOpen, setDeleteChatModalOpen] = useState(false);
  const [isDeletingChat, setIsDeletingChat] = useState(false);
  const [renameChatModalOpen, setRenameChatModalOpen] = useState(false);
  const [isRenamingChat, setIsRenamingChat] = useState(false);
  const [editingMessageIndex, setEditingMessageIndex] = useState<number | null>(null);
  const [isEditSending, setIsEditSending] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [regeneratingMessageIndex, setRegeneratingMessageIndex] = useState<number | null>(null);
  const [selectedModel, setSelectedModel] = useState("auto");
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);

  // Plus menu state
  const [plusMenuOpen, setPlusMenuOpen] = useState(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState(true); // On by default
  const [selectedStyle, setSelectedStyle] = useState("normal");
  const [styleSubmenuOpen, setStyleSubmenuOpen] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFileItem[]>([]);
  const [researchSidebarOpen, setResearchSidebarOpen] = useState(false);
  const plusMenuRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isLoggedIn = token === "authenticated" && !!user;

  // Response styles for students
  const RESPONSE_STYLES = [
    { id: "normal", name: "Normal", description: "Standard balanced responses" },
    { id: "learning", name: "Learning", description: "Step-by-step explanations with examples" },
    { id: "concise", name: "Concise", description: "Brief, to-the-point answers" },
    { id: "explanatory", name: "Explanatory", description: "Detailed explanations with context" },
    { id: "formal", name: "Formal", description: "Academic and professional tone" },
  ];

  const currentStyle = RESPONSE_STYLES.find(s => s.id === selectedStyle) || RESPONSE_STYLES[0];

  // Model quota state for per-model rate limits
  const [modelQuota, setModelQuota] = useState<Record<string, { remaining: number; limit: number }>>({});

  const fetchModelQuota = useCallback(async () => {
    try {
      const apiBaseUrl = getApiBaseUrl();
      const res = await fetch(`${apiBaseUrl}/chat/model-limits`, { credentials: "include" });
      if (res.ok) {
        const d = await res.json();
        if (d.models) setModelQuota(d.models);
      }
    } catch { /* ignore fetch errors */ }
  }, []);

  // Available LLM models (admin-only models appended conditionally)
  const LLM_MODELS = [
    {
      id: "auto",
      name: "Auto",
      shortName: "Auto",
      description: "Picks the best model for your query",
      modelId: null as string | null,
      isDefault: true,
      badge: "Smart",
      family: null as string | null,
    },
    {
      id: "llama-70b",
      name: "Llama 70B",
      shortName: "Llama 70B",
      description: "Default model, great for most tasks",
      modelId: "us.meta.llama3-1-70b-instruct-v1:0",
      badge: "Default",
      family: "default",
    },
    {
      id: "claude-sonnet",
      name: "Sonnet 3.5",
      shortName: "Sonnet 3.5",
      description: "Most capable, best for complex tasks",
      modelId: "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
      badge: "Pro",
      family: "pro",
    },
    {
      id: "claude-haiku",
      name: "Haiku 3",
      shortName: "Haiku 3",
      description: "Fast and lightweight",
      modelId: "us.anthropic.claude-3-haiku-20240307-v1:0",
      badge: "Fast",
      family: "fast",
    },
    ...(isAdmin ? [{
      id: "claude-opus",
      name: "Claude Opus 4",
      shortName: "Opus 4",
      description: "Most intelligent, admin-only",
      modelId: "us.anthropic.claude-opus-4-20250514-v1:0",
      badge: "Admin",
      family: "admin",
    }] : []),
  ];

  const currentModel = LLM_MODELS.find(m => m.id === selectedModel) || LLM_MODELS[0];

  // Speech recognition ref (using any to avoid TypeScript issues with Web Speech API)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);
  const modelDropdownRef = useRef<HTMLDivElement>(null);

  const refreshSessions = useCallback(async () => {
    if (!isLoggedIn || !token) {
      setSessions([]);
      setSelectedSessionId(null);
      return;
    }
    try {
      const data = await listChatSessions(token);
      setSessions(data);
      if (data.length > 0) {
        const querySession = searchParams.get("session");
        const validSessions = data.filter((s): s is ChatSessionDTO => Boolean(s && typeof s === 'object' && 'id' in s));
        const matchFromQuery: ChatSessionDTO | undefined = querySession ? validSessions.find((s) => s.id === querySession) : undefined;
        const firstSession = validSessions[0];
        // Prefer the URL query param so sidebar "New chat" / session clicks switch correctly
        setSelectedSessionId((current) => {
          if (querySession && matchFromQuery) return matchFromQuery.id;
          return current || firstSession?.id || null;
        });
      }
    } catch (error) {
      setStreamError(error instanceof Error ? error.message : "Unable to load sessions");
      setSessions([]);
    }
  }, [token, searchParams, isLoggedIn]);

  useEffect(() => {
    refreshSessions();
    function handleUpdate() {
      refreshSessions();
    }
    window.addEventListener(CHAT_SESSIONS_UPDATED_EVENT, handleUpdate);
    return () => {
      window.removeEventListener(CHAT_SESSIONS_UPDATED_EVENT, handleUpdate);
    };
  }, [refreshSessions]);

  // Fetch per-model quota on mount
  useEffect(() => {
    if (isLoggedIn) fetchModelQuota();
  }, [isLoggedIn, fetchModelQuota]);

  // Cleanup speech recognition, mic stream, and active fetch on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
        recognitionRef.current = null;
      }
      // Release microphone stream
      if (micStreamRef.current) {
        micStreamRef.current.getTracks().forEach(track => track.stop());
        micStreamRef.current = null;
      }
      // Abort any in-flight streaming request (backend try/finally saves the response)
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    };
  }, []);

  // Close model dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (modelDropdownRef.current && !modelDropdownRef.current.contains(event.target as Node)) {
        setModelDropdownOpen(false);
      }
    };
    if (modelDropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [modelDropdownOpen]);

  // Close plus menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (plusMenuRef.current && !plusMenuRef.current.contains(event.target as Node)) {
        setPlusMenuOpen(false);
        setStyleSubmenuOpen(false);
      }
    };
    if (plusMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [plusMenuOpen]);

  const uploadFiles = useCallback(
    async (fileList: File[]) => {
      if (!token) return;
      const pendingItems: UploadedFileItem[] = fileList.map((file) => ({
        file,
        status: "uploading",
      }));
      setUploadedFiles((prev) => [...prev, ...pendingItems]);

      const apiBaseUrl = getApiBaseUrl();
      for (const file of fileList) {
        const formData = new FormData();
        formData.append("file", file);
        try {
          const response = await fetch(`${apiBaseUrl}/chat/uploads`, {
            method: "POST",
            credentials: "include",
            body: formData,
          });
          const payload = (await response.json().catch(() => ({}))) as {
            preview?: { id?: string; file_name?: string };
            detail?: string;
          };
          if (!response.ok) {
            throw new Error(payload.detail || "Upload failed");
          }
          setUploadedFiles((prev) =>
            prev.map((item) =>
              item.file === file
                ? {
                    ...item,
                    id: payload.preview?.id,
                    status: "ready",
                  }
                : item
            )
          );
        } catch (err) {
          setUploadedFiles((prev) =>
            prev.map((item) =>
              item.file === file
                ? {
                    ...item,
                    status: "error",
                    error: err instanceof Error ? err.message : "Upload failed",
                  }
                : item
            )
          );
        }
      }
    },
    [token]
  );

  // Handle file upload
  const handleFileSelect = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = event.target.files;
      if (!files || !token) return;
      await uploadFiles(Array.from(files));
      setPlusMenuOpen(false);
    },
    [token, uploadFiles]
  );

  const removeUploadedFile = useCallback((index: number) => {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  // Handle adding files from research sidebar
  const handleResearchFilesAdded = useCallback(
    async (files: File[]) => {
      await uploadFiles(files);
    },
    [uploadFiles]
  );

  // Handle URL submission from research sidebar
  const handleResearchUrlSubmit = useCallback((url: string) => {
    // For now, add the URL as a message context - could be expanded later
    console.log("Research URL submitted:", url);
    // Close the sidebar after URL submission
    setResearchSidebarOpen(false);
  }, []);

  // Fetch feedback when session changes
  useEffect(() => {
    if (!token || !selectedSessionId) {
      setFeedbackMap({});
      return;
    }

    const fetchFeedback = async () => {
      try {
        const response = await getSessionFeedback({
          token,
          sessionId: selectedSessionId,
        });
        setFeedbackMap(response.feedback || {});
      } catch (err) {
        console.error("Failed to fetch feedback:", err);
        setFeedbackMap({});
      }
    };

    fetchFeedback();
  }, [token, selectedSessionId]);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId) || null,
    [sessions, selectedSessionId]
  );

  async function handleCreateSession() {
    if (!token || !isLoggedIn) return;
    setIsCreatingSession(true);
    try {
      const next = await createChatSession({ token, title: undefined });
      setSessions((prev) => [next, ...prev.filter((s) => s.id !== next.id)]);
      setSelectedSessionId(next.id);
      dispatchChatSessionsUpdated();
      toast.success("New chat created");
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to create session";
      setStreamError(msg);
      toast.error(msg);
    } finally {
      setIsCreatingSession(false);
    }
  }

  function updateActiveSessionMessages(updater: (messages: ChatMessageDTO[]) => ChatMessageDTO[]) {
    setSessions((prev) =>
      prev.map((session) =>
        session.id === selectedSessionId
          ? {
              ...session,
              messages: updater(session.messages || []),
              updated_at: new Date().toISOString(),
            }
          : session
      )
    );
  }

  async function handleSendMessage(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !isLoggedIn || !selectedSessionId || !composerText.trim() || isStreaming) {
      return;
    }

    const content = composerText.trim();
    setComposerText("");
    setStreamError(null);

    // Snapshot uploaded file info before clearing
    const readyFiles = uploadedFiles.filter((f) => f.status === "ready");
    const attachments: ChatAttachment[] = readyFiles.map((f) => {
      const ext = f.file.name.split(".").pop()?.toLowerCase() || "";
      const isImage = f.file.type.startsWith("image/");
      return {
        name: f.file.name,
        ext,
        isImage,
        previewUrl: isImage ? URL.createObjectURL(f.file) : undefined,
      };
    });
    const uploadedFileIds = readyFiles
      .map((item) => item.id)
      .filter((id): id is string => Boolean(id));

    const userMessage: ChatMessageDTO = {
      role: "user",
      content,
      timestamp: new Date().toISOString(),
      ...(attachments.length > 0 ? { attachments } : {}),
    };

    const assistantMessage: ChatMessageDTO = {
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
    };

    updateActiveSessionMessages((messages) => [...messages, userMessage, assistantMessage]);
    setUploadedFiles([]);
    setIsStreaming(true);

    try {
      const apiBaseUrl = getApiBaseUrl();
      const controller = new AbortController();
      abortControllerRef.current = controller;
      const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minute timeout

      const response = await fetch(
        `${apiBaseUrl}/chat/sessions/${selectedSessionId}/messages`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify({
            query: content,
            model_id: currentModel.modelId,
            web_search_enabled: webSearchEnabled,
            response_style: selectedStyle,
            uploaded_only: attachments.length > 0,
            uploaded_file_ids: uploadedFileIds.length > 0 ? uploadedFileIds : undefined,
            attachments: attachments.length > 0
              ? attachments.map(({ name, ext, isImage }) => ({ name, ext, isImage }))
              : undefined,
          }),
          signal: controller.signal,
        }
      );

      clearTimeout(timeoutId);

      // Handle per-model rate limit (429)
      if (response.status === 429) {
        const err = await response.json();
        const detail = err.detail || {};
        const mins = Math.ceil((detail.retry_after || 3600) / 60);
        toast.error(`${detail.model_family || "Model"} limit reached. Resets in ${mins}m. Try a different model.`);
        // Remove the placeholder assistant message
        updateActiveSessionMessages((messages) => messages.slice(0, -1));
        setIsStreaming(false);
        fetchModelQuota();
        return;
      }

      // Handle LLM unavailable / server busy (503)
      if (response.status === 503) {
        const err = await response.json();
        const secs = err.detail?.retry_after || 60;
        toast.error(`LLM unavailable. Retrying in ${secs}s — the service may be overloaded.`);
        updateActiveSessionMessages((messages) => messages.slice(0, -1));
        setIsStreaming(false);
        return;
      }

      if (!response.ok || !response.body) {
        throw new Error("Chat endpoint unavailable");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantText = "";
      let agentName: string | undefined;
      let routeReason: string | undefined;
      let modelUsed: string | undefined;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        assistantText += decoder.decode(value, { stream: true });

        // Parse __AGENT_META__ prefix from agent system
        let displayText = assistantText;
        if (displayText.startsWith("__AGENT_META__")) {
          const newlineIdx = displayText.indexOf("\n");
          if (newlineIdx !== -1) {
            const metaLine = displayText.substring("__AGENT_META__".length, newlineIdx);
            try {
              const meta = JSON.parse(metaLine);
              agentName = meta.agent;
              routeReason = meta.route_reason;
              if (meta.model_used) modelUsed = meta.model_used;
            } catch { /* ignore parse errors */ }
            displayText = displayText.substring(newlineIdx + 1);
          } else {
            continue; // Wait for full meta line
          }
        }

        const latestText = displayText;
        const latestAgent = agentName;
        const latestReason = routeReason;
        const latestModelUsed = modelUsed;
        setSessions((prev) =>
          prev.map((session) =>
            session.id === selectedSessionId
              ? {
                  ...session,
                  messages: session.messages.map((message, index, arr) =>
                    index === arr.length - 1
                      ? { ...message, content: latestText, agent: latestAgent, route_reason: latestReason, model_used: latestModelUsed }
                      : message
                  ),
                }
              : session
          )
        );
      }

      await refreshSessions();
      dispatchChatSessionsUpdated();
      fetchModelQuota();
      toast.success("Response ready");
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        // User navigated away — backend try/finally saves the response
        return;
      }
      let errMessage = "Unable to stream a response";
      if (error instanceof Error) {
        if (error.message.includes("Failed to fetch") || error.message.includes("NetworkError")) {
          errMessage = "Network error. Please check your connection and try again.";
        } else {
          errMessage = error.message;
        }
      }
      setStreamError(errMessage);
      toast.error(errMessage);
      setSessions((prev) =>
        prev.map((session) =>
          session.id === selectedSessionId
            ? {
                ...session,
                messages: session.messages.map((message, index, arr) =>
                  index === arr.length - 1
                    ? { ...message, content: `Error: ${errMessage}` }
                    : message
                ),
              }
            : session
        )
      );
    } finally {
      abortControllerRef.current = null;
      setIsStreaming(false);
    }
  }

  // Action bar handlers
  const handleFeedbackChange = useCallback(
    (messageIndex: number, feedback: MessageFeedbackType | null) => {
      setFeedbackMap((prev) => {
        const next = { ...prev };
        if (feedback) {
          next[messageIndex] = feedback;
        } else {
          delete next[messageIndex];
        }
        return next;
      });
    },
    []
  );

  const handleOpenSources = useCallback((sources: Array<Record<string, unknown>>) => {
    setSelectedSources(sources);
    setSourcesSidebarOpen(true);
  }, []);

  const handleOpenShare = useCallback((messageContent: string) => {
    setShareModalMessage(messageContent);
    setShareModalOpen(true);
  }, []);

  const handleOpenReport = useCallback((messageIndex: number) => {
    setReportMessageIndex(messageIndex);
    setReportModalOpen(true);
  }, []);

  const handleDeleteChat = useCallback(async () => {
    if (!token || !selectedSessionId) return;
    setIsDeletingChat(true);
    try {
      await deleteChatSession(token, selectedSessionId);
      setDeleteChatModalOpen(false);
      const remainingSessions = sessions.filter(s => s.id !== selectedSessionId);
      if (remainingSessions.length > 0) {
        setSelectedSessionId(remainingSessions[0].id);
      } else {
        setSelectedSessionId(null);
      }
      toast.success("Chat deleted");
      await refreshSessions();
      dispatchChatSessionsUpdated();
    } catch (error) {
      console.error("Failed to delete chat:", error);
      toast.error("Failed to delete chat");
    } finally {
      setIsDeletingChat(false);
    }
  }, [token, selectedSessionId, sessions, refreshSessions]);

  const handleRenameChat = useCallback(() => {
    setRenameChatModalOpen(true);
  }, []);

  const handlePinChat = useCallback(async () => {
    if (!token || !activeSession) return;
    try {
      await pinChatSession(token, activeSession.id, !activeSession.is_pinned);
      await refreshSessions();
      dispatchChatSessionsUpdated();
      toast.success(activeSession.is_pinned ? "Chat unpinned" : "Chat pinned");
    } catch (error) {
      console.error("Failed to pin chat:", error);
      toast.error("Failed to pin chat");
    }
  }, [token, activeSession, refreshSessions]);

  const handleArchiveChat = useCallback(async () => {
    if (!token || !activeSession) return;
    try {
      await archiveChatSession(token, activeSession.id, !activeSession.is_archived);
      await refreshSessions();
      dispatchChatSessionsUpdated();
      toast.success(activeSession.is_archived ? "Chat unarchived" : "Chat archived");
    } catch (error) {
      console.error("Failed to archive chat:", error);
      toast.error("Failed to archive chat");
    }
  }, [token, activeSession, refreshSessions]);

  const handleConfirmRename = useCallback(async (newTitle: string) => {
    if (!token || !activeSession) return;
    setIsRenamingChat(true);
    try {
      await renameChatSession(token, activeSession.id, newTitle);
      setRenameChatModalOpen(false);
      await refreshSessions();
      dispatchChatSessionsUpdated();
      toast.success("Chat renamed");
    } catch (error) {
      console.error("Failed to rename chat:", error);
      toast.error("Failed to rename chat");
    } finally {
      setIsRenamingChat(false);
    }
  }, [token, activeSession, refreshSessions]);

  // Handle editing and resending a user message
  const handleEditMessage = useCallback(async (messageIndex: number, newContent: string) => {
    if (!token || !isLoggedIn || !selectedSessionId || isStreaming || isEditSending) return;

    setIsEditSending(true);
    setStreamError(null);

    // Remove messages from the edited message onwards (keep messages before it)
    // The edited message will be the new user message
    setSessions((prev) =>
      prev.map((session) =>
        session.id === selectedSessionId
          ? {
              ...session,
              messages: session.messages.slice(0, messageIndex),
            }
          : session
      )
    );

    // Create new user message and assistant placeholder
    const userMessage: ChatMessageDTO = {
      role: "user",
      content: newContent,
      timestamp: new Date().toISOString(),
    };

    const assistantMessage: ChatMessageDTO = {
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
    };

    // Add the new messages
    setSessions((prev) =>
      prev.map((session) =>
        session.id === selectedSessionId
          ? {
              ...session,
              messages: [...session.messages, userMessage, assistantMessage],
              updated_at: new Date().toISOString(),
            }
          : session
      )
    );

    setEditingMessageIndex(null);
    setIsStreaming(true);

    try {
      const apiBaseUrl = getApiBaseUrl();
      const controller = new AbortController();
      abortControllerRef.current = controller;
      const timeoutId = setTimeout(() => controller.abort(), 300000);

      const response = await fetch(
        `${apiBaseUrl}/chat/sessions/${selectedSessionId}/messages`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify({
            query: newContent,
            model_id: currentModel.modelId,
            web_search_enabled: webSearchEnabled,
            response_style: selectedStyle,
            uploaded_only: uploadedFiles.length > 0,
            uploaded_file_ids: uploadedFiles
              .map((item) => item.id)
              .filter((id): id is string => Boolean(id)),
          }),
          signal: controller.signal,
        }
      );

      clearTimeout(timeoutId);

      // Handle per-model rate limit (429)
      if (response.status === 429) {
        const err = await response.json();
        const detail = err.detail || {};
        const mins = Math.ceil((detail.retry_after || 3600) / 60);
        toast.error(`${detail.model_family || "Model"} limit reached. Resets in ${mins}m. Try a different model.`);
        setIsStreaming(false);
        setIsEditSending(false);
        fetchModelQuota();
        return;
      }

      // Handle LLM unavailable / server busy (503)
      if (response.status === 503) {
        const err = await response.json();
        const secs = err.detail?.retry_after || 60;
        toast.error(`LLM unavailable. Retrying in ${secs}s — the service may be overloaded.`);
        setIsStreaming(false);
        setIsEditSending(false);
        return;
      }

      if (!response.ok || !response.body) {
        throw new Error("Chat endpoint unavailable");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantText = "";
      let agentName: string | undefined;
      let routeReason: string | undefined;
      let modelUsed: string | undefined;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        assistantText += decoder.decode(value, { stream: true });

        let displayText = assistantText;
        if (displayText.startsWith("__AGENT_META__")) {
          const newlineIdx = displayText.indexOf("\n");
          if (newlineIdx !== -1) {
            const metaLine = displayText.substring("__AGENT_META__".length, newlineIdx);
            try {
              const meta = JSON.parse(metaLine);
              agentName = meta.agent;
              routeReason = meta.route_reason;
              if (meta.model_used) modelUsed = meta.model_used;
            } catch { /* ignore parse errors */ }
            displayText = displayText.substring(newlineIdx + 1);
          } else {
            continue;
          }
        }

        const latestText = displayText;
        const latestAgent = agentName;
        const latestReason = routeReason;
        const latestModelUsed = modelUsed;
        setSessions((prev) =>
          prev.map((session) =>
            session.id === selectedSessionId
              ? {
                  ...session,
                  messages: session.messages.map((message, index, arr) =>
                    index === arr.length - 1
                      ? { ...message, content: latestText, agent: latestAgent, route_reason: latestReason, model_used: latestModelUsed }
                      : message
                  ),
                }
              : session
          )
        );
      }

      await refreshSessions();
      dispatchChatSessionsUpdated();
      fetchModelQuota();
      toast.success("Response ready");
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        return;
      }
      let errMessage = "Unable to stream a response";
      if (error instanceof Error) {
        if (error.message.includes("Failed to fetch") || error.message.includes("NetworkError")) {
          errMessage = "Network error. Please check your connection and try again.";
        } else {
          errMessage = error.message;
        }
      }
      setStreamError(errMessage);
      toast.error(errMessage);
      setSessions((prev) =>
        prev.map((session) =>
          session.id === selectedSessionId
            ? {
                ...session,
                messages: session.messages.map((message, index, arr) =>
                  index === arr.length - 1
                    ? { ...message, content: `Error: ${errMessage}` }
                    : message
                ),
              }
            : session
        )
      );
    } finally {
      abortControllerRef.current = null;
      setIsStreaming(false);
      setIsEditSending(false);
    }
  }, [token, selectedSessionId, isStreaming, isEditSending, refreshSessions]);

  // Handle regenerating a response (Try Again)
  const handleRegenerateMessage = useCallback(async (messageIndex: number) => {
    if (!token || !isLoggedIn || !selectedSessionId || isStreaming || !activeSession) return;

    // Find the user message before this assistant message
    const userMessageIndex = messageIndex - 1;
    if (userMessageIndex < 0 || activeSession.messages[userMessageIndex]?.role !== "user") {
      setStreamError("Cannot regenerate: No user message found before this response.");
      return;
    }

    const userQuery = activeSession.messages[userMessageIndex].content;
    setRegeneratingMessageIndex(messageIndex);
    setStreamError(null);

    // Keep messages up to and including the user message, then add new assistant placeholder
    setSessions((prev) =>
      prev.map((session) =>
        session.id === selectedSessionId
          ? {
              ...session,
              messages: [
                ...session.messages.slice(0, messageIndex),
                { role: "assistant" as const, content: "", timestamp: new Date().toISOString() },
              ],
            }
          : session
      )
    );

    setIsStreaming(true);

    try {
      const apiBaseUrl = getApiBaseUrl();
      const controller = new AbortController();
      abortControllerRef.current = controller;
      const timeoutId = setTimeout(() => controller.abort(), 300000);

      const response = await fetch(
        `${apiBaseUrl}/chat/sessions/${selectedSessionId}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            query: userQuery,
            model_id: currentModel.modelId,
            web_search_enabled: webSearchEnabled,
            response_style: selectedStyle,
            uploaded_only: uploadedFiles.length > 0,
            uploaded_file_ids: uploadedFiles
              .map((item) => item.id)
              .filter((id): id is string => Boolean(id)),
          }),
          signal: controller.signal,
        }
      );

      clearTimeout(timeoutId);

      // Handle per-model rate limit (429)
      if (response.status === 429) {
        const err = await response.json();
        const detail = err.detail || {};
        const mins = Math.ceil((detail.retry_after || 3600) / 60);
        toast.error(`${detail.model_family || "Model"} limit reached. Resets in ${mins}m. Try a different model.`);
        setIsStreaming(false);
        setRegeneratingMessageIndex(null);
        fetchModelQuota();
        return;
      }

      // Handle LLM unavailable / server busy (503)
      if (response.status === 503) {
        const err = await response.json();
        const secs = err.detail?.retry_after || 60;
        toast.error(`LLM unavailable. Retrying in ${secs}s — the service may be overloaded.`);
        setIsStreaming(false);
        setRegeneratingMessageIndex(null);
        return;
      }

      if (!response.ok || !response.body) {
        throw new Error("Chat endpoint unavailable");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantText = "";
      let modelUsed: string | undefined;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        assistantText += decoder.decode(value, { stream: true });

        // Parse __AGENT_META__ for model_used in regeneration too
        let displayText = assistantText;
        if (displayText.startsWith("__AGENT_META__")) {
          const newlineIdx = displayText.indexOf("\n");
          if (newlineIdx !== -1) {
            const metaLine = displayText.substring("__AGENT_META__".length, newlineIdx);
            try {
              const meta = JSON.parse(metaLine);
              if (meta.model_used) modelUsed = meta.model_used;
            } catch { /* ignore parse errors */ }
            displayText = displayText.substring(newlineIdx + 1);
          } else {
            continue;
          }
        }

        const latestText = displayText;
        const latestModelUsed = modelUsed;
        setSessions((prev) =>
          prev.map((session) =>
            session.id === selectedSessionId
              ? {
                  ...session,
                  messages: session.messages.map((message, index) =>
                    index === messageIndex ? { ...message, content: latestText, model_used: latestModelUsed } : message
                  ),
                }
              : session
          )
        );
      }

      await refreshSessions();
      dispatchChatSessionsUpdated();
      fetchModelQuota();
      toast.success("Response ready");
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        return;
      }
      let errMessage = "Unable to regenerate response";
      if (error instanceof Error) {
        if (error.message.includes("Failed to fetch") || error.message.includes("NetworkError")) {
          errMessage = "Network error. Please check your connection and try again.";
        } else {
          errMessage = error.message;
        }
      }
      setStreamError(errMessage);
      toast.error(errMessage);
      setSessions((prev) =>
        prev.map((session) =>
          session.id === selectedSessionId
            ? {
                ...session,
                messages: session.messages.map((message, index) =>
                  index === messageIndex ? { ...message, content: `Error: ${errMessage}` } : message
                ),
              }
            : session
        )
      );
    } finally {
      abortControllerRef.current = null;
      setIsStreaming(false);
      setRegeneratingMessageIndex(null);
    }
  }, [token, selectedSessionId, isStreaming, activeSession, currentModel.modelId, refreshSessions]);

  // Persistent mic permission ref - once granted, stays for the session
  const micPermissionGranted = useRef(false);
  const micStreamRef = useRef<MediaStream | null>(null);

  // Speech recognition handler with persistent permission
  const handleToggleDictation = useCallback(async () => {
    // Check if speech recognition is supported
    const SpeechRecognitionAPI = (window as unknown as { SpeechRecognition?: typeof window.SpeechRecognition; webkitSpeechRecognition?: typeof window.SpeechRecognition }).SpeechRecognition ||
                              (window as unknown as { webkitSpeechRecognition?: typeof window.SpeechRecognition }).webkitSpeechRecognition;

    if (!SpeechRecognitionAPI) {
      setStreamError("Speech recognition is not supported in your browser. Try using Chrome or Edge.");
      return;
    }

    if (isListening) {
      // Stop listening
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }

    // Request microphone permission once via getUserMedia - this persists for the session
    // and prevents SpeechRecognition from re-prompting every time
      if (!micPermissionGranted.current) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          micStreamRef.current = stream;
          micPermissionGranted.current = true;
      } catch (err) {
        setStreamError("Microphone access denied. Please allow microphone access in your browser settings and try again.");
        return;
      }
    }

    // Reuse existing recognition instance or create new one
    if (!recognitionRef.current) {
      const recognition = new SpeechRecognitionAPI();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
      };

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      recognition.onresult = (event: any) => {
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcript;
          }
        }

        // Append transcribed text to composer
        if (finalTranscript) {
          setComposerText((prev) => prev + (prev ? ' ' : '') + finalTranscript.trim());
        }
      };

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      recognition.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error);
        if (event.error === 'not-allowed') {
          micPermissionGranted.current = false;
          setStreamError("Microphone access was revoked. Please re-enable it in browser settings.");
        } else if (event.error === 'no-speech') {
          // No speech detected - just stop silently, don't show error
          setIsListening(false);
        } else if (event.error !== 'aborted') {
          setStreamError(`Speech recognition error: ${event.error}`);
        }
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    }

    try {
      recognitionRef.current.start();
    } catch {
      // If start fails (e.g. already started), recreate the instance
      recognitionRef.current = null;
      handleToggleDictation();
    }
  }, [isListening]);

  const hasMessages = activeSession && activeSession.messages.length > 0;

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Full-width Header Bar - Outside of content constraints */}
      <div className="flex-shrink-0 sticky top-0 z-10 bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800">
        <div className="flex items-center px-4 py-3 max-w-6xl mx-auto w-full">
          {activeSession ? (
            <ChatHeaderActions
              sessionTitle={activeSession.title}
              onShareClick={() => setShareChatModalOpen(true)}
              onDeleteClick={() => setDeleteChatModalOpen(true)}
              onRenameClick={handleRenameChat}
              onPinClick={handlePinChat}
              onArchiveClick={handleArchiveChat}
              isPinned={activeSession.is_pinned}
              isArchived={activeSession.is_archived}
              hasActiveSession={!!activeSession}
              uploadedFiles={uploadedFiles}
              onRemoveFile={removeUploadedFile}
            />
          ) : (
            <div className="flex items-center justify-between w-full">
              <h1 className="text-base font-medium text-zinc-800 dark:text-zinc-100">
                New chat
              </h1>
            </div>
          )}
          <div className="flex items-center gap-1.5 sm:gap-2 ml-auto flex-shrink-0">
            {isAdmin && (
              <>
                <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold uppercase tracking-wider text-amber-700 dark:bg-amber-950/40 dark:text-amber-400">
                  <ShieldAlert className="h-3 w-3" />
                  Admin
                </span>
                <Link
                  href="/admin"
                  className="hidden sm:inline text-xs font-medium text-amber-700 dark:text-amber-400 hover:underline"
                >
                  Dashboard →
                </Link>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Main content area */}
      <div className="flex-1 min-h-0 overflow-y-auto">
      <div className="flex flex-col max-w-5xl mx-auto w-full px-3 sm:px-6 animate-fade-in-up">
        {/* Error banner */}
        {streamError && (
          <div className="mt-4 rounded-xl bg-red-500/10 px-4 py-3">
            <div className="flex items-center gap-3">
              <svg className="h-5 w-5 text-red-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm text-red-400 flex-1">{streamError}</p>
              <button
                type="button"
                onClick={() => setStreamError(null)}
                className="text-sm font-medium text-red-400 hover:text-red-300"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Unauthenticated state */}
        {!isLoggedIn && (
          <div className="flex flex-col items-center justify-center flex-1 px-6 text-center pb-16">
            <h1 className="text-3xl font-semibold text-zinc-900 dark:text-white mb-3">
              Sign in to start chatting
            </h1>
            <p className="text-base text-zinc-500 dark:text-zinc-400 mb-6 max-w-xl">
              Your chat history and saved sessions appear after signing in.
            </p>
            <Link
              href="/login"
              className="px-6 py-3 rounded-full bg-indigo-600 text-white font-medium hover:bg-indigo-700 transition"
            >
              Sign in
            </Link>
          </div>
        )}

        {/* Welcome screen when no messages */}
        {isLoggedIn && (!activeSession || !hasMessages) && (
          <div className="flex flex-col items-center justify-center flex-1 px-6 text-center pb-16 pt-24">
            <h1 className="text-2xl sm:text-4xl font-semibold text-zinc-900 dark:text-white mb-3">
              {`Hi, ${getFriendlyUserName(user)}`}
            </h1>
            <p className="text-base sm:text-xl text-zinc-500 dark:text-zinc-400">
              {isAdmin ? "What would you like to test or explore?" : "What would you like to learn today?"}
            </p>
          </div>
        )}

        {/* Messages */}
        {hasMessages && (
          <div className="py-6 space-y-6">
              {activeSession.messages.map((message, index) => {
                const isLastMessage = index === activeSession.messages.length - 1;
                const isStreamingMessage = isLastMessage && isStreaming && message.role === "assistant";
                const isEditingThisMessage = editingMessageIndex === index;

                return (
                  <ChatBubble
                    key={`${message.timestamp}-${index}`}
                    message={message}
                    messageIndex={index}
                    sessionId={selectedSessionId!}
                    token={token}
                    isStreaming={isStreamingMessage}
                    currentFeedback={feedbackMap[index] || null}
                    onFeedbackChange={(feedback) => handleFeedbackChange(index, feedback)}
                    onOpenSources={handleOpenSources}
                    onOpenShare={handleOpenShare}
                    onOpenReport={handleOpenReport}
                    onOpenViewer={(url, title) => {
                      setViewerUrl(url);
                      setViewerTitle(title);
                    }}
                    // User message edit props
                    isEditing={isEditingThisMessage}
                    isEditSending={isEditSending}
                    onStartEdit={() => setEditingMessageIndex(index)}
                    onCancelEdit={() => setEditingMessageIndex(null)}
                    onConfirmEdit={(newContent) => handleEditMessage(index, newContent)}
                    // Regenerate props
                    onRegenerateClick={message.role === "assistant" ? () => handleRegenerateMessage(index) : undefined}
                    isRegenerating={regeneratingMessageIndex === index}
                  />
                );
            })}
          </div>
        )}
      </div>
      </div>

      {/* Input area - fixed at bottom */}
      <div className="flex-shrink-0 max-w-5xl mx-auto w-full px-3 sm:px-6 pb-4 pt-2">
          {isListening ? (
            /* Dictation mode - waveform animation */
            <div className="rounded-2xl border border-zinc-700 bg-zinc-800 px-4 py-3">
              <div className="flex items-center gap-4">
                {/* Plus button */}
                <button
                  type="button"
                  aria-label="Attachments and options"
                  className="flex h-9 w-9 items-center justify-center text-zinc-400 hover:text-white transition-colors"
                >
                  <Plus className="h-5 w-5" aria-hidden="true" />
                </button>

                {/* Audio waveform animation */}
                <div className="flex-1 flex items-center justify-center h-8 gap-[2px]">
                  {Array.from({ length: 80 }).map((_, i) => (
                    <div
                      key={i}
                      className="w-[2px] bg-zinc-500 rounded-full animate-waveform"
                      style={{
                        height: `${Math.random() * 20 + 4}px`,
                        animationDelay: `${i * 20}ms`,
                        animationDuration: `${300 + Math.random() * 200}ms`,
                      }}
                    />
                  ))}
                </div>

                {/* Cancel button */}
                <button
                  type="button"
                  onClick={() => {
                    recognitionRef.current?.stop();
                    setIsListening(false);
                    setComposerText(""); // Clear any transcribed text
                  }}
                  className="flex h-9 w-9 items-center justify-center text-zinc-400 hover:text-white transition-colors"
                  title="Cancel dictation"
                >
                  <X className="h-5 w-5" />
                </button>

                {/* Confirm/Send button */}
                <button
                  type="button"
                  onClick={() => {
                    recognitionRef.current?.stop();
                    setIsListening(false);
                    // Submit if there's text
                    if (composerText.trim() && activeSession) {
                      const fakeEvent = { preventDefault: () => {} } as React.FormEvent<HTMLFormElement>;
                      handleSendMessage(fakeEvent);
                    }
                  }}
                  className="flex h-9 w-9 items-center justify-center text-zinc-400 hover:text-white transition-colors"
                  title="Send message"
                >
                  <Check className="h-5 w-5" />
                </button>
              </div>
              {composerText.trim() && (
                <div className="mt-2 rounded-lg bg-zinc-900/40 px-3 py-2 text-xs text-zinc-200">
                  {composerText}
                </div>
              )}
            </div>
          ) : (
            /* Normal input mode - ChatGPT-style single line */
            <form onSubmit={handleSendMessage}>
              {/* Enhanced file/image preview grid */}
              <FilePreviewGrid
                files={uploadedFiles}
                onRemoveFile={removeUploadedFile}
              />

              {/* Active options indicator */}
              {(webSearchEnabled || selectedStyle !== 'normal') && (
                <div className="flex items-center gap-2 mb-2 px-2">
                  {webSearchEnabled && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 text-xs">
                      <Globe className="h-3 w-3" />
                      Web search
                    </span>
                  )}
                  {selectedStyle !== 'normal' && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 text-xs">
                      {currentStyle.name}
                    </span>
                  )}
                </div>
              )}

              <div className="flex items-center gap-2 sm:gap-3 rounded-full border border-zinc-200 bg-zinc-100 px-3 sm:px-4 py-2 focus-within:border-zinc-300 focus-within:bg-white transition dark:border-zinc-700 dark:bg-zinc-800 dark:focus-within:border-zinc-600 dark:focus-within:bg-zinc-800">
                {/* Plus Menu Button (Left side) */}
                <div className="relative" ref={plusMenuRef}>
                  <button
                    type="button"
                    onClick={() => {
                      setPlusMenuOpen(!plusMenuOpen);
                      setStyleSubmenuOpen(false);
                    }}
                    className="flex h-8 w-8 items-center justify-center rounded-full border border-zinc-300 dark:border-zinc-600 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition"
                    title="More options"
                  >
                    <Plus className={`h-5 w-5 transition-transform ${plusMenuOpen ? 'rotate-45' : ''}`} />
                  </button>

                  {/* Plus Menu Dropdown */}
                  {plusMenuOpen && (
                    <div className="absolute bottom-full left-0 mb-2 w-56 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-xl overflow-visible z-50 animate-fade-in-up">
                      {/* Hidden file input */}
                      <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileSelect}
                        className="hidden"
                        multiple
                        accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg,.gif,.webp,.py,.ipynb"
                      />

                      <div className="py-2">
                        {/* Add files or photos */}
                        <button
                          type="button"
                          onClick={() => fileInputRef.current?.click()}
                          className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors"
                        >
                          <Paperclip className="h-5 w-5 text-zinc-500" />
                          <span className="text-sm">Add files or photos</span>
                        </button>

                        {/* Research Mode */}
                        <button
                          type="button"
                          onClick={() => {
                            setResearchSidebarOpen(true);
                            setPlusMenuOpen(false);
                          }}
                          className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors"
                        >
                          <FlaskConical className="h-5 w-5 text-indigo-500" />
                          <div className="flex flex-col">
                            <span className="text-sm font-medium">Research Mode</span>
                            <span className="text-xs text-zinc-400">Upload sources & use research tools</span>
                          </div>
                        </button>

                        {/* Divider */}
                        <div className="h-px bg-zinc-200 dark:bg-zinc-700 my-1" />

                        {/* Web search toggle */}
                        <button
                          type="button"
                          onClick={() => setWebSearchEnabled(!webSearchEnabled)}
                          className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <Globe className={`h-5 w-5 ${webSearchEnabled ? 'text-blue-500' : 'text-zinc-500'}`} />
                            <span className={`text-sm ${webSearchEnabled ? 'text-blue-500 font-medium' : 'text-zinc-700 dark:text-zinc-300'}`}>
                              Web search
                            </span>
                          </div>
                          {webSearchEnabled && (
                            <Check className="h-4 w-4 text-blue-500" />
                          )}
                        </button>

                        {/* Use style - with submenu */}
                        <div className="relative">
                          <button
                            type="button"
                            onClick={() => setStyleSubmenuOpen(!styleSubmenuOpen)}
                            className="w-full flex items-center justify-between px-4 py-2.5 text-left text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors"
                          >
                            <div className="flex items-center gap-3">
                              <span className="text-sm">Use style</span>
                            </div>
                            <ChevronRight className="h-4 w-4 text-zinc-400" />
                          </button>

                          {/* Style submenu */}
                          {styleSubmenuOpen && (
                            <div className="absolute left-0 bottom-full mb-1 sm:left-full sm:bottom-0 sm:mb-0 sm:ml-1 w-56 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-xl z-50 animate-fade-in-up">
                              <div className="py-2">
                                {RESPONSE_STYLES.map((style) => (
                                  <button
                                    key={style.id}
                                    type="button"
                                    onClick={() => {
                                      setSelectedStyle(style.id);
                                      setStyleSubmenuOpen(false);
                                      setPlusMenuOpen(false);
                                    }}
                                    className={`w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors ${
                                      selectedStyle === style.id ? 'bg-zinc-100 dark:bg-zinc-700/50' : ''
                                    }`}
                                  >
                                    <div className="flex items-center gap-3">
                                      <span className={`text-sm ${selectedStyle === style.id ? 'text-blue-500 font-medium' : 'text-zinc-700 dark:text-zinc-300'}`}>
                                        {style.name}
                                      </span>
                                    </div>
                                    {selectedStyle === style.id && (
                                      <Check className="h-4 w-4 text-blue-500" />
                                    )}
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Input */}
                <input
                  type="text"
                  placeholder={isLoggedIn ? (activeSession ? "Ask anything..." : "Create a session to start") : "Sign in to start chatting"}
                  value={composerText}
                  disabled={!isLoggedIn || !activeSession || isStreaming}
                  onChange={(event) => setComposerText(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault();
                      if (activeSession && composerText.trim() && !isStreaming) {
                        handleSendMessage(event as unknown as React.FormEvent<HTMLFormElement>);
                      }
                    }
                  }}
                  className="flex-1 bg-transparent text-base text-zinc-900 outline-none placeholder:text-zinc-500 dark:text-white dark:placeholder:text-zinc-400 caret-zinc-900 dark:caret-white"
                />

                {/* Right side buttons */}
                <div className="flex items-center gap-2">
                  {/* Model Selector Button */}
                  <div className="relative" ref={modelDropdownRef}>
                    <button
                      type="button"
                      onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
                      className="flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1.5 rounded-full border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-zinc-700 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-600 transition text-sm font-medium"
                      title="Select model"
                    >
                      <span className="hidden sm:inline">{currentModel.shortName}</span>
                      <ChevronDown className={`h-4 w-4 transition-transform ${modelDropdownOpen ? 'rotate-180' : ''}`} />
                    </button>

                    {/* Model Dropdown Menu */}
                    {modelDropdownOpen && (
                      <div className="absolute bottom-full right-0 mb-2 w-72 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-xl overflow-hidden z-50 animate-fade-in-up">
                        <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-700">
                          <p className="text-sm font-semibold text-zinc-900 dark:text-white">Models</p>
                        </div>
                        <div className="py-2">
                          {LLM_MODELS.map((model) => {
                            const family = model.family;
                            const quota = family ? modelQuota[family] : null;
                            return (
                              <button
                                key={model.id}
                                type="button"
                                onClick={() => {
                                  setSelectedModel(model.id);
                                  setModelDropdownOpen(false);
                                }}
                                className={`w-full flex items-center justify-between px-4 py-3 hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors ${
                                  selectedModel === model.id ? 'bg-zinc-100 dark:bg-zinc-700/50' : ''
                                }`}
                              >
                                <div className="text-left">
                                  <p className="text-sm font-medium text-zinc-900 dark:text-white">{model.name}</p>
                                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                                    {quota ? `${quota.remaining}/${quota.limit} remaining` : model.description}
                                  </p>
                                </div>
                                <div className="flex items-center gap-2">
                                  {model.badge && (
                                    <span className="px-2 py-0.5 text-xs font-medium bg-zinc-200 dark:bg-zinc-600 text-zinc-600 dark:text-zinc-300 rounded">
                                      {model.badge}
                                    </span>
                                  )}
                                  {selectedModel === model.id && (
                                    <div className="w-5 h-5 rounded-full bg-indigo-500 flex items-center justify-center">
                                      <Check className="h-3 w-3 text-white" />
                                    </div>
                                  )}
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Dictate Button */}
                  <button
                    type="button"
                    onClick={handleToggleDictation}
                    disabled={!isLoggedIn || !activeSession || isStreaming}
                    className="flex h-8 w-8 items-center justify-center text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition disabled:opacity-50 disabled:cursor-not-allowed"
                    aria-label={isListening ? "Stop dictation" : "Start dictation"}
                  >
                    <Mic className="h-5 w-5" aria-hidden="true" />
                  </button>
                  {/* Send Button */}
                  <button
                    type="submit"
                    disabled={!isLoggedIn || !activeSession || isStreaming || !composerText.trim()}
                    className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-600 text-white transition hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    aria-label="Send message"
                  >
                    <Send className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              </div>
            </form>
          )}

          {/* AI disclaimer */}
          <p className="mt-2 text-center text-xs text-zinc-400 dark:text-zinc-500 select-none">
            AI is experimental and can make mistakes. Please double-check responses.
          </p>

          {/* Suggestion chips - only show when no messages */}
          {isLoggedIn && (!activeSession || !hasMessages) && (
            <div className="flex flex-wrap justify-center gap-2 mt-4">
              {isAdmin ? (
                <>
                  <button
                    type="button"
                    onClick={() => setComposerText("Run a system health check on the RAG pipeline")}
                    className="px-4 py-2 rounded-full border border-amber-200 bg-amber-50 text-sm text-amber-800 hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300 dark:hover:bg-amber-950/50 transition-colors"
                  >
                    RAG health check
                  </button>
                  <button
                    type="button"
                    onClick={() => setComposerText("Test multi-model response comparison for a complex query")}
                    className="px-4 py-2 rounded-full border border-amber-200 bg-amber-50 text-sm text-amber-800 hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300 dark:hover:bg-amber-950/50 transition-colors"
                  >
                    Model comparison
                  </button>
                  <button
                    type="button"
                    onClick={() => setComposerText("What are the current system metrics and performance stats?")}
                    className="px-4 py-2 rounded-full border border-amber-200 bg-amber-50 text-sm text-amber-800 hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300 dark:hover:bg-amber-950/50 transition-colors"
                  >
                    System metrics
                  </button>
                  <button
                    type="button"
                    onClick={() => setComposerText("Evaluate the quality of responses for edge-case queries")}
                    className="px-4 py-2 rounded-full border border-amber-200 bg-amber-50 text-sm text-amber-800 hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300 dark:hover:bg-amber-950/50 transition-colors"
                  >
                    Edge-case testing
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => setComposerText("What is the main topic of this course?")}
                    className="px-4 py-2 rounded-full border border-zinc-200 bg-white text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700 transition-colors"
                  >
                    Course overview
                  </button>
                  <button
                    type="button"
                    onClick={() => setComposerText("Help me understand machine learning basics")}
                    className="px-4 py-2 rounded-full border border-zinc-200 bg-white text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700 transition-colors"
                  >
                    ML basics
                  </button>
                  <button
                    type="button"
                    onClick={() => setComposerText("How do I use the research mode?")}
                    className="px-4 py-2 rounded-full border border-zinc-200 bg-white text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700 transition-colors"
                  >
                    Research mode
                  </button>
                  <button
                    type="button"
                    onClick={() => setComposerText("Explain a complex concept simply")}
                    className="px-4 py-2 rounded-full border border-zinc-200 bg-white text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700 transition-colors"
                  >
                    Explain concepts
                  </button>
                </>
              )}
            </div>
          )}
      </div>

      {/* File Viewer Modal */}
      <FileViewerModal
        url={viewerUrl}
        title={viewerTitle}
        onClose={() => {
          setViewerUrl(null);
          setViewerTitle(null);
        }}
      />

      {/* Sources Sidebar */}
      <SourcesSidebar
        isOpen={sourcesSidebarOpen}
        onClose={() => setSourcesSidebarOpen(false)}
        sources={selectedSources}
        token={token}
        onOpenViewer={(url, title) => {
          setViewerUrl(url);
          setViewerTitle(title);
        }}
      />

      {/* Share Modal */}
      <ShareModal
        isOpen={shareModalOpen}
        onClose={() => setShareModalOpen(false)}
        sessionId={selectedSessionId || ""}
        sessionTitle={activeSession?.title || "Chat Session"}
        messageContent={shareModalMessage}
        token={token}
      />

      {/* Report Modal */}
      <ReportModal
        isOpen={reportModalOpen}
        onClose={() => setReportModalOpen(false)}
        sessionId={selectedSessionId || ""}
        messageIndex={reportMessageIndex}
        token={token}
      />

      {/* Share Chat Modal */}
      <ShareChatModal
        isOpen={shareChatModalOpen}
        onClose={() => setShareChatModalOpen(false)}
        sessionId={selectedSessionId || ""}
        sessionTitle={activeSession?.title || "Chat Conversation"}
        messages={activeSession?.messages || []}
        token={token}
      />

      {/* Delete Chat Modal */}
      <DeleteChatModal
        isOpen={deleteChatModalOpen}
        onClose={() => setDeleteChatModalOpen(false)}
        onConfirm={handleDeleteChat}
        chatTitle={activeSession?.title || `Session ${activeSession?.id?.slice(0, 6) || ""}`}
        isDeleting={isDeletingChat}
      />

      {/* Rename Chat Modal */}
      <RenameChatModal
        isOpen={renameChatModalOpen}
        onClose={() => setRenameChatModalOpen(false)}
        onConfirm={handleConfirmRename}
        currentTitle={activeSession?.title || "Chat Session"}
        isRenaming={isRenamingChat}
      />

      {/* Research Sidebar */}
      <ResearchSidebar
        isOpen={researchSidebarOpen}
        onClose={() => setResearchSidebarOpen(false)}
        onFilesAdded={handleResearchFilesAdded}
        onUrlSubmit={handleResearchUrlSubmit}
        activeSourceCount={uploadedFiles.length}
      />
    </div>
  );
}

interface ChatBubbleProps {
  message: ChatMessageDTO;
  messageIndex: number;
  sessionId: string;
  token?: string | null;
  isStreaming?: boolean;
  currentFeedback: MessageFeedbackType | null;
  onFeedbackChange: (feedback: MessageFeedbackType | null) => void;
  onOpenSources: (sources: Array<Record<string, unknown>>) => void;
  onOpenShare: (messageContent: string) => void;
  onOpenReport: (messageIndex: number) => void;
  onOpenViewer?: (url: string, title: string) => void;
  // User message edit props
  isEditing?: boolean;
  isEditSending?: boolean;
  onStartEdit?: () => void;
  onCancelEdit?: () => void;
  onConfirmEdit?: (newContent: string) => void;
  // Regenerate props
  onRegenerateClick?: () => void;
  isRegenerating?: boolean;
}

function ChatBubble({
  message,
  messageIndex,
  sessionId,
  token,
  isStreaming,
  currentFeedback,
  onFeedbackChange,
  onOpenSources,
  onOpenShare,
  onOpenReport,
  onOpenViewer,
  isEditing,
  isEditSending,
  onStartEdit,
  onCancelEdit,
  onConfirmEdit,
  onRegenerateClick,
  isRegenerating,
}: ChatBubbleProps) {
  const [isHovered, setIsHovered] = useState(false);
  const isUser = message.role === "user";
  const hasSources = message.sources && message.sources.length > 0;

  // Handle copy for user messages
  const handleCopyUserMessage = () => {
    navigator.clipboard.writeText(message.content);
  };

  // User message - right aligned dark bubble
  if (isUser) {
    // Editing mode
    if (isEditing && onCancelEdit && onConfirmEdit) {
      return (
        <div className="flex justify-end animate-fade-in-up">
          <EditableUserMessage
            initialContent={message.content}
            onCancel={onCancelEdit}
            onSend={onConfirmEdit}
            isSending={isEditSending}
          />
        </div>
      );
    }

    // Helper: get icon + color for document attachments
    const getAttachmentStyle = (ext: string) => {
      switch (ext) {
        case "pdf": return { color: "bg-red-500", label: "PDF" };
        case "docx": case "doc": return { color: "bg-blue-500", label: "Word" };
        case "pptx": case "ppt": return { color: "bg-orange-500", label: "PPT" };
        case "py": return { color: "bg-yellow-500", label: "Python" };
        case "ipynb": return { color: "bg-orange-600", label: "Notebook" };
        case "txt": case "md": case "csv": return { color: "bg-zinc-500", label: ext.toUpperCase() };
        default: return { color: "bg-zinc-500", label: ext.toUpperCase() || "File" };
      }
    };

    // Normal view with Copy/Edit buttons (shown on hover)
    return (
      <div
        className="flex justify-end animate-fade-in-up"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <div className="flex flex-col items-end gap-2 min-w-0 max-w-full">
          {/* Attached files - shown above the message */}
          {message.attachments && message.attachments.length > 0 && (
            <div className="flex flex-wrap justify-end gap-2">
              {message.attachments.map((att, i) =>
                att.isImage && att.previewUrl ? (
                  <div key={i} className="w-48 rounded-xl overflow-hidden border border-zinc-600 shadow-md">
                    <img src={att.previewUrl} alt={att.name} className="w-full h-auto object-cover max-h-48" />
                    <div className="px-2 py-1 bg-zinc-800 text-[10px] text-zinc-400 truncate">{att.name}</div>
                  </div>
                ) : (
                  <div key={i} className="flex items-center gap-2 rounded-xl bg-zinc-800 border border-zinc-600 px-3 py-2 max-w-[200px]">
                    <div className={`flex-shrink-0 w-8 h-8 rounded-lg ${getAttachmentStyle(att.ext).color} flex items-center justify-center`}>
                      <FileText className="h-4 w-4 text-white" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-zinc-200 truncate">{att.name}</p>
                      <p className="text-[10px] text-zinc-400">{getAttachmentStyle(att.ext).label}</p>
                    </div>
                  </div>
                )
              )}
            </div>
          )}
          <div className="max-w-[85%] sm:max-w-2xl rounded-2xl bg-zinc-700 dark:bg-zinc-700 px-4 py-3 text-white">
            <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{message.content}</p>
          </div>
          {/* Copy and Edit buttons - visible on hover */}
          {onStartEdit && (
            <UserMessageActions
              onCopy={handleCopyUserMessage}
              onEdit={onStartEdit}
              visible={isHovered}
            />
          )}
        </div>
      </div>
    );
  }

  // Strip __AGENT_META__ prefix and unwanted headings from stored messages (safety net)
  const cleanContent = (() => {
    let c = message.content || "";
    if (c.startsWith("__AGENT_META__")) {
      const idx = c.indexOf("\n");
      c = idx !== -1 ? c.substring(idx + 1) : c;
    }
    // Remove "Concise Answer:" / "Elaboration:" section headings (with or without bold markdown)
    c = c.replace(/^#{0,3}\s*\*{0,2}Concise\s+Answer:?\*{0,2}\s*\n?/gim, "");
    c = c.replace(/^#{0,3}\s*\*{0,2}Elaboration:?\*{0,2}\s*\n?/gim, "");
    return c.trim();
  })();

  // Show phase indicator when streaming starts and no content yet
  const showPhaseIndicator = isStreaming && !cleanContent;

  // Agent badge color mapping
  const agentBadgeConfig: Record<string, { label: string; color: string }> = {
    tutor_agent: { label: "Tutor", color: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20" },
    doubts_agent: { label: "Doubt Resolver", color: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20" },
    personalised_agent: { label: "Personalized", color: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20" },
    quiz_helper_agent: { label: "Quiz Helper", color: "bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20" },
    feedback_agent: { label: "Feedback", color: "bg-teal-500/10 text-teal-600 dark:text-teal-400 border-teal-500/20" },
  };
  const agentInfo = message.agent ? agentBadgeConfig[message.agent] : null;

  // Assistant message - left aligned, no bubble
  return (
    <div className="animate-fade-in-up">
      <div className="max-w-3xl">
        {showPhaseIndicator ? (
          <StreamingPhaseIndicator
            isStreaming={isStreaming || false}
            hasContent={!!cleanContent}
            agentName={message.agent}
          />
        ) : (
          <>
            {/* Agent badge */}
            {agentInfo && (
              <div className="mb-1.5 flex items-center gap-2">
                <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${agentInfo.color}`}>
                  <span className="h-1.5 w-1.5 rounded-full bg-current" />
                  {agentInfo.label}
                </span>
                {message.route_reason && (
                  <span className="text-[11px] text-zinc-400 dark:text-zinc-500 italic">{message.route_reason}</span>
                )}
              </div>
            )}
            {/* Auto-routed model chip */}
            {message.model_used && !message.agent && (
              <div className="mb-1.5">
                <span className="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/20">
                  via {MODEL_DISPLAY_NAMES[message.model_used] || "Auto"}
                </span>
              </div>
            )}
            <MarkdownContent
              content={cleanContent}
              sources={message.sources}
              isStreaming={isStreaming}
              onOpenSources={onOpenSources}
            />
            {/* Response Action Bar - only show when not streaming */}
            {!isStreaming && (
              <ResponseActionBar
                messageContent={cleanContent}
                sessionId={sessionId}
                messageIndex={messageIndex}
                token={token || null}
                hasSources={hasSources || false}
                currentFeedback={currentFeedback}
                onFeedbackChange={onFeedbackChange}
                onShareClick={() => onOpenShare(cleanContent)}
                onReportClick={() => onOpenReport(messageIndex)}
                onSourcesClick={() => {
                  if (message.sources) {
                    onOpenSources(message.sources);
                  }
                }}
                onRegenerateClick={onRegenerateClick}
                isRegenerating={isRegenerating}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}

// Component to render markdown content with inline source citations
interface MarkdownContentProps {
  content: string;
  sources?: Array<Record<string, unknown>> | null;
  isStreaming?: boolean;
  onOpenSources: (sources: Array<Record<string, unknown>>) => void;
}

function MarkdownContent({ content, sources, isStreaming, onOpenSources }: MarkdownContentProps) {
  const sanitizeText = (raw: string) => {
    // Iteratively strip HTML tags to prevent bypass via nested tags
    // e.g. "<scr<script>ipt>" → "<script>" after one pass
    let result = raw;
    let prev = "";
    while (result !== prev) {
      prev = result;
      result = result.replace(/<[^>]*>/g, "");
    }
    return result.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, "");
  };

  const safeContent = sanitizeText(content || "");

  // Create a source chip component for inline use with hover preview
  const SourceChip = ({ sourceIndex, displayName }: { sourceIndex: number; displayName: string }) => {
    const [showTooltip, setShowTooltip] = useState(false);

    if (!sources || sourceIndex >= sources.length) return null;

    const source = sources[sourceIndex];
    const snippet = typeof source?.chunk_text === 'string'
      ? source.chunk_text.slice(0, 200) + (source.chunk_text.length > 200 ? '...' : '')
      : null;
    const location = source?.page ? `Page ${source.page}` : source?.slide ? `Slide ${source.slide}` : null;

    return (
      <span className="relative inline-block">
        <button
          onClick={() => onOpenSources(sources)}
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
          className="inline-flex items-center gap-1 px-2 py-0.5 mx-0.5 rounded-md bg-zinc-100 dark:bg-zinc-700 text-xs text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-600 transition-colors align-middle border border-zinc-200 dark:border-zinc-600"
        >
          <span className="w-3 h-3 rounded-full bg-zinc-300 dark:bg-zinc-500 flex items-center justify-center text-[8px] font-bold">
            {sourceIndex + 1}
          </span>
          <span className="max-w-[120px] truncate">{displayName}</span>
        </button>
        {/* Hover tooltip with source preview */}
        {showTooltip && (
          <div className="absolute z-50 bottom-full left-0 mb-2 w-72 p-3 rounded-lg bg-white dark:bg-zinc-800 shadow-xl border border-zinc-200 dark:border-zinc-700 animate-fade-in-up">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-5 h-5 rounded bg-zinc-200 dark:bg-zinc-600 flex items-center justify-center text-xs font-semibold text-zinc-600 dark:text-zinc-300">
                {sourceIndex + 1}
              </div>
              <span className="font-medium text-zinc-900 dark:text-white text-sm truncate flex-1">{displayName}</span>
            </div>
            {location && (
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-1">{location}</p>
            )}
            {snippet && (
              <p className="text-xs text-zinc-600 dark:text-zinc-300 leading-relaxed line-clamp-4">&quot;{snippet}&quot;</p>
            )}
            <p className="text-xs text-indigo-500 mt-2">Click to view all sources</p>
          </div>
        )}
      </span>
    );
  };

  // Parse inline citations like [1], [2], [Source Name], etc.
  const renderWithCitations = (text: string, keyPrefix: string): React.ReactNode[] => {
    const parts: React.ReactNode[] = [];
    // Match [1], [2], [Source 1], [Source Name], etc.
    const citationPattern = /\[(\d+)\]|\[Source\s*(\d+)\]|\[([^\]]+)\]/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null;
    let citationKey = 0;

    while ((match = citationPattern.exec(text)) !== null) {
      const currentMatch = match; // Store to avoid null checks

      // Add text before citation
      if (currentMatch.index > lastIndex) {
        parts.push(text.substring(lastIndex, currentMatch.index));
      }

      // Determine source index and display name
      let sourceIndex = -1;
      let displayName = '';

      if (currentMatch[1]) {
        // Numeric citation like [1]
        sourceIndex = parseInt(currentMatch[1]) - 1; // Convert to 0-indexed
        const source = sources?.[sourceIndex];
        displayName = source
          ? ((source.file_name as string) || (source.name as string) || (source.title as string) || `Source ${currentMatch[1]}`).substring(0, 15)
          : `Source ${currentMatch[1]}`;
        if (displayName.length === 15) displayName += '...';
      } else if (currentMatch[2]) {
        // "Source N" format like [Source 1]
        sourceIndex = parseInt(currentMatch[2]) - 1;
        const source = sources?.[sourceIndex];
        displayName = source
          ? ((source.file_name as string) || (source.name as string) || (source.title as string) || `Source ${currentMatch[2]}`).substring(0, 15)
          : `Source ${currentMatch[2]}`;
        if (displayName.length === 15) displayName += '...';
      } else if (currentMatch[3]) {
        // Named citation like [Some Name]
        const namedCitation = currentMatch[3];
        displayName = namedCitation.length > 15 ? namedCitation.substring(0, 15) + '...' : namedCitation;
        // Try to find matching source by name
        sourceIndex = sources?.findIndex(s =>
          (s.name as string)?.toLowerCase().includes(namedCitation.toLowerCase()) ||
          (s.title as string)?.toLowerCase().includes(namedCitation.toLowerCase())
        ) ?? -1;
        if (sourceIndex === -1 && sources && sources.length > 0) {
          sourceIndex = 0; // Default to first source if no match
        }
      }

      // Add citation chip if we have sources
      if (sources && sources.length > 0 && sourceIndex >= 0) {
        parts.push(
          <SourceChip
            key={`${keyPrefix}-cite-${citationKey++}`}
            sourceIndex={sourceIndex}
            displayName={displayName}
          />
        );
      } else {
        // No sources, just show the citation text
        parts.push(currentMatch[0]);
      }

      lastIndex = currentMatch.index + currentMatch[0].length;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    return parts.length > 0 ? parts : [text];
  };

  // Render inline markdown (bold, italic) with citations
  const renderInlineMarkdown = (text: string, keyPrefix: string = ''): React.ReactNode => {
    // First, handle citations, then bold/italic within each part
    const partsWithCitations = renderWithCitations(text, keyPrefix);

    // Process each text part for bold/italic (skip React elements)
    const result: React.ReactNode[] = [];
    let partKey = 0;

    partsWithCitations.forEach((part, partIndex) => {
      if (typeof part !== 'string') {
        // Already a React element (citation chip)
        result.push(part);
        return;
      }

      // Process bold and italic
      let remaining = part;
      while (remaining.length > 0) {
        // Check for bold **text**
        const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
        // Check for italic *text* (not part of **)
        const italicMatch = remaining.match(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/);

        if (boldMatch && (!italicMatch || boldMatch.index! <= italicMatch.index!)) {
          // Add text before bold
          if (boldMatch.index! > 0) {
            result.push(remaining.substring(0, boldMatch.index));
          }
          // Add bold text
          result.push(
            <strong key={`${keyPrefix}-bold-${partKey++}`} className="font-semibold text-zinc-900 dark:text-white">
              {boldMatch[1]}
            </strong>
          );
          remaining = remaining.substring(boldMatch.index! + boldMatch[0].length);
        } else if (italicMatch) {
          // Add text before italic
          if (italicMatch.index! > 0) {
            result.push(remaining.substring(0, italicMatch.index));
          }
          // Add italic text
          result.push(
            <em key={`${keyPrefix}-italic-${partKey++}`} className="italic">
              {italicMatch[1]}
            </em>
          );
          remaining = remaining.substring(italicMatch.index! + italicMatch[0].length);
        } else {
          // No more matches, add remaining text
          result.push(remaining);
          break;
        }
      }
    });

    return result;
  };

  // Parse markdown: headers, bold, paragraphs, lists, with inline citations
  const renderMarkdown = (text: string) => {
    const lines = text.split('\n');
    const elements: React.ReactNode[] = [];
    let currentParagraph: React.ReactNode[] = [];
    let currentList: React.ReactNode[] = [];
    let listType: 'ul' | 'ol' | null = null;
    let paragraphKey = 0;
    let listKey = 0;

    const flushParagraph = () => {
      if (currentParagraph.length > 0) {
        elements.push(
          <p key={`p-${paragraphKey++}`} className="mb-5 leading-7 text-zinc-700 dark:text-zinc-200">
            {currentParagraph}
          </p>
        );
        currentParagraph = [];
      }
    };

    const flushList = () => {
      if (currentList.length > 0) {
        if (listType === 'ol') {
          elements.push(
            <ol key={`ol-${listKey++}`} className="mb-5 ml-6 list-decimal space-y-2">
              {currentList}
            </ol>
          );
        } else {
          elements.push(
            <ul key={`ul-${listKey++}`} className="mb-5 ml-6 list-disc space-y-2">
              {currentList}
            </ul>
          );
        }
        currentList = [];
        listType = null;
      }
    };

    lines.forEach((line, lineIndex) => {
      // Check for headers
      const h1Match = line.match(/^# (.+)$/);
      const h2Match = line.match(/^## (.+)$/);
      const h3Match = line.match(/^### (.+)$/);
      // Check for list items
      const unorderedListMatch = line.match(/^[-*]\s+(.+)$/);
      const orderedListMatch = line.match(/^\d+\.\s+(.+)$/);

      if (h1Match) {
        flushParagraph();
        flushList();
        elements.push(
          <h1 key={`h1-${lineIndex}`} className="text-2xl font-bold mb-4 mt-8 text-zinc-900 dark:text-white">
            {renderInlineMarkdown(h1Match[1], `h1-${lineIndex}`)}
          </h1>
        );
      } else if (h2Match) {
        flushParagraph();
        flushList();
        elements.push(
          <h2 key={`h2-${lineIndex}`} className="text-xl font-bold mb-3 mt-6 text-zinc-900 dark:text-white">
            {renderInlineMarkdown(h2Match[1], `h2-${lineIndex}`)}
          </h2>
        );
      } else if (h3Match) {
        flushParagraph();
        flushList();
        elements.push(
          <h3 key={`h3-${lineIndex}`} className="text-lg font-semibold mb-3 mt-5 text-zinc-900 dark:text-white">
            {renderInlineMarkdown(h3Match[1], `h3-${lineIndex}`)}
          </h3>
        );
      } else if (unorderedListMatch) {
        flushParagraph();
        if (listType !== 'ul') {
          flushList();
          listType = 'ul';
        }
        currentList.push(
          <li key={`li-${lineIndex}`} className="text-zinc-700 dark:text-zinc-200 leading-relaxed">
            {renderInlineMarkdown(unorderedListMatch[1], `li-${lineIndex}`)}
          </li>
        );
      } else if (orderedListMatch) {
        flushParagraph();
        if (listType !== 'ol') {
          flushList();
          listType = 'ol';
        }
        currentList.push(
          <li key={`li-${lineIndex}`} className="text-zinc-700 dark:text-zinc-200 leading-relaxed">
            {renderInlineMarkdown(orderedListMatch[1], `li-${lineIndex}`)}
          </li>
        );
      } else if (line.trim() === '') {
        // Empty line - flush current paragraph and list
        flushParagraph();
        flushList();
      } else {
        // Regular text - add to current paragraph
        flushList(); // End any active list when encountering non-list text
        if (currentParagraph.length > 0) {
          currentParagraph.push(' '); // Use space instead of br for better text flow
        }
        currentParagraph.push(
          <span key={`span-${lineIndex}`}>{renderInlineMarkdown(line, `line-${lineIndex}`)}</span>
        );
      }
    });

    // Flush remaining paragraph and list
    flushParagraph();
    flushList();

    return elements;
  };

  return (
    <div className="prose prose-sm dark:prose-invert max-w-none text-zinc-800 dark:text-zinc-200">
      {renderMarkdown(safeContent)}
      {isStreaming && <span className="inline-block w-2 h-4 ml-1 bg-indigo-500 animate-pulse rounded-sm"></span>}
    </div>
  );
}

// File Viewer Modal Component
function FileViewerModal({ 
  url, 
  title, 
  onClose 
}: { 
  url: string | null; 
  title: string | null; 
  onClose: () => void;
}) {
  if (!url || !title) return null;
  
  const getFileExt = (filename: string) => {
    return filename.split('.').pop()?.toLowerCase() || '';
  };
  
  const ext = getFileExt(title);
  const isPDF = ext === 'pdf';
  const isOffice = ['pptx', 'ppt', 'docx', 'doc'].includes(ext);
  const isNotebook = ext === 'ipynb';
  const isImage = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'].includes(ext);
  const isVideo = ['mp4', 'webm', 'mov', 'avi', 'mkv'].includes(ext);
  const isAudio = ['mp3', 'wav', 'ogg', 'm4a', 'aac'].includes(ext);
  const isHTML = ext === 'html' || ext === 'htm';
  const isCode = ['py', 'js', 'ts', 'jsx', 'tsx', 'java', 'c', 'cpp', 'h', 'hpp', 'cs', 'go', 'rs', 'rb', 'php', 'pl', 'lua', 'r', 'scala', 'kt', 'swift'].includes(ext);
  const isText = ['txt', 'json', 'md', 'css', 'scss', 'yaml', 'yml', 'xml', 'csv', 'sh', 'bash', 'zsh', 'sql'].includes(ext);
  
  const displayUrl = url;
  
  const getGoogleDocsUrl = () => {
    return `https://docs.google.com/gview?embedded=1&url=${encodeURIComponent(displayUrl)}`;
  };
  
  const getColabUrl = () => {
    return `https://colab.research.google.com/notebook#create=true&url=${encodeURIComponent(displayUrl)}`;
  };
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-6xl h-[90vh] bg-white dark:bg-zinc-900 rounded-xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-white truncate">
            {title}
          </h3>
          <button
            onClick={onClose}
            className="p-2 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5 text-zinc-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        {/* Content area */}
        <div className="h-[calc(100%-120px)] w-full overflow-auto">
          {isPDF ? (
            // PDF - embed directly
            <iframe
              src={displayUrl}
              className="w-full h-full"
              title={`PDF: ${title}`}
            />
          ) : isImage ? (
            // Images - display inline
            <div className="flex items-center justify-center h-full p-4">
              <img 
                src={displayUrl} 
                alt={title}
                className="max-w-full max-h-full object-contain rounded-lg shadow-lg"
              />
            </div>
          ) : isVideo ? (
            // Video - embed player
            <div className="flex items-center justify-center h-full p-4">
              <video 
                controls 
                className="max-w-full max-h-full rounded-lg shadow-lg"
                preload="metadata"
              >
                <source src={displayUrl} />
                Your browser does not support video playback.
              </video>
            </div>
          ) : isAudio ? (
            // Audio - embed player
            <div className="flex flex-col items-center justify-center h-full p-4">
              <div className="w-24 h-24 mb-6 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                <svg className="w-12 h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                </svg>
              </div>
              <audio controls className="w-full max-w-lg mt-4">
                <source src={displayUrl} />
                Your browser does not support audio playback.
              </audio>
              <a
                href={displayUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-4 text-sm text-blue-600 dark:text-blue-400 hover:underline"
              >
                Download audio file
              </a>
            </div>
          ) : isHTML ? (
            // HTML - embed directly
            <iframe
              src={displayUrl}
              className="w-full h-full"
              title={`HTML: ${title}`}
              sandbox="allow-scripts"
            />
          ) : isCode ? (
            // Code files - show with download option
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
              <div className="w-20 h-20 mb-6 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
              </div>
              <h4 className="text-xl font-semibold text-zinc-900 dark:text-white mb-2">
                {title}
              </h4>
              <p className="text-zinc-600 dark:text-zinc-400 mb-6 max-w-md">
                Code file detected. Download to view in your editor or IDE.
              </p>
              <a
                href={displayUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
              >
                Download Code
              </a>
            </div>
          ) : isOffice ? (
            // Office files - show info card with multiple options
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
              <div className="w-20 h-20 mb-6 rounded-2xl bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h4 className="text-xl font-semibold text-zinc-900 dark:text-white mb-2">
                {title}
              </h4>
              <p className="text-zinc-600 dark:text-zinc-400 mb-6 max-w-md">
                Office documents require Microsoft Office or Google Docs to view. 
                Download the file and open it with your preferred application.
              </p>
              <div className="flex gap-4">
                <a
                  href={displayUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium flex items-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download & Open
                </a>
              </div>
              <p className="mt-6 text-sm text-zinc-500 dark:text-zinc-400 max-w-md">
                <strong>Tip:</strong> Right-click the download button and choose &quot;Save link as...&quot; to download the file, then open it with Microsoft Office, Google Docs, or any compatible viewer.
              </p>
            </div>
          ) : isNotebook ? (
            // Jupyter notebooks - show info card
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
              <div className="w-20 h-20 mb-6 rounded-2xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
              </div>
              <h4 className="text-xl font-semibold text-zinc-900 dark:text-white mb-2">
                {title}
              </h4>
              <p className="text-zinc-600 dark:text-zinc-400 mb-6 max-w-md">
                Jupyter notebook detected. Download the file to open in Jupyter Lab, 
                VS Code, or upload to Google Colab.
              </p>
              <div className="flex gap-4">
                <a
                  href={displayUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium flex items-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download & Open
                </a>
                <a
                  href={getColabUrl()}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-6 py-3 bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-white rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors font-medium"
                >
                  Open in Colab
                </a>
              </div>
                <p className="mt-6 text-sm text-zinc-500 dark:text-zinc-400 max-w-md">
                  <strong>Tip:</strong> For Colab, you may need to upload the downloaded .ipynb file manually.
                </p>
              </div>
            ) : isText ? (
            // Text files - show with open link
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
              <div className="w-20 h-20 mb-6 rounded-2xl bg-gradient-to-br from-zinc-500 to-zinc-700 flex items-center justify-center">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h4 className="text-xl font-semibold text-zinc-900 dark:text-white mb-2">
                {title}
              </h4>
              <a
                href={displayUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
              >
                Open File
              </a>
            </div>
          ) : (
            // Default - show download link
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
              <div className="w-20 h-20 mb-6 rounded-2xl bg-gradient-to-br from-zinc-400 to-zinc-600 flex items-center justify-center">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h4 className="text-xl font-semibold text-zinc-900 dark:text-white mb-2">
                {title}
              </h4>
              <a
                href={displayUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
              >
                Download File
              </a>
            </div>
          )}
        </div>
        
        {/* Footer */}
        <div className="absolute bottom-0 left-0 right-0 px-4 py-3 bg-zinc-50 dark:bg-zinc-800 border-t border-zinc-200 dark:border-zinc-700">
          <span className="text-xs text-zinc-500 dark:text-zinc-400">
            {isPDF ? 'PDF document' : 
             isImage ? 'Image file' : 
             isVideo ? 'Video file' : 
             isAudio ? 'Audio file' : 
             isHTML ? 'HTML document' : 
             isCode ? 'Code file' : 
             isOffice ? 'Office document' : 
             isNotebook ? 'Jupyter notebook' : 
             isText ? 'Text file' : 
             'File'} • Click the button above to view or download
          </span>
        </div>
      </div>
    </div>
  );
}

export default function ChatWorkspace() {
  return (
    <Suspense fallback={<ChatWorkspaceSkeleton />}>
      <ChatWorkspaceContent />
    </Suspense>
  );
}

function ChatWorkspaceSkeleton() {
  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header skeleton */}
      <div className="flex-shrink-0 sticky top-0 z-10 bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800">
        <div className="flex items-center px-6 py-3 max-w-5xl mx-auto">
          <div className="h-5 w-32 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
        </div>
      </div>

      {/* Welcome screen skeleton */}
      <div className="flex-1 min-h-0 flex flex-col items-center justify-center px-6 max-w-4xl mx-auto w-full">
        <div className="h-10 w-48 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse mb-3"></div>
        <div className="h-6 w-64 bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
      </div>

      {/* Input skeleton */}
      <div className="flex-shrink-0 max-w-4xl mx-auto w-full px-4 pb-4 pt-2">
        <div className="rounded-3xl bg-zinc-100 px-4 py-3 dark:bg-zinc-800">
          <div className="h-6 w-full bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse"></div>
          <div className="flex items-center justify-end mt-2">
            <div className="h-9 w-9 bg-indigo-600 rounded-full animate-pulse"></div>
          </div>
        </div>
        <div className="flex justify-center gap-2 mt-4">
          <div className="h-10 w-32 bg-zinc-200 dark:bg-zinc-700 rounded-full animate-pulse"></div>
          <div className="h-10 w-24 bg-zinc-200 dark:bg-zinc-700 rounded-full animate-pulse"></div>
          <div className="h-10 w-28 bg-zinc-200 dark:bg-zinc-700 rounded-full animate-pulse"></div>
        </div>
      </div>
    </div>
  );
}
