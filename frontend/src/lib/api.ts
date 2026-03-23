import { AUTH_EXPIRED_EVENT, clearAuthToken } from "./auth";

const EXPLICIT_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;
const DEFAULT_API_PORT = process.env.NEXT_PUBLIC_API_PORT || "8000";
const FALLBACK_API_BASE_URL = `http://localhost:${DEFAULT_API_PORT}`;
const SERVER_API_BASE_URL =
  process.env.BACKEND_API_BASE_URL || FALLBACK_API_BASE_URL;
const APP_BASE_URL =
  process.env.NEXT_PUBLIC_APP_BASE_URL || "http://localhost:4000";
const CLIENT_PROXY_API_BASE_URL = "/api/backend";

function withAbsoluteOrigin(url: string): string {
  if (!url || url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }
  const origin =
    typeof window !== "undefined"
      ? `${window.location.protocol}//${window.location.host}`
      : APP_BASE_URL;
  const normalizedOrigin = origin.replace(/\/$/, "");
  const normalizedPath = url.startsWith("/") ? url : `/${url}`;
  return `${normalizedOrigin}${normalizedPath}`;
}

function resolveApiBaseUrl(): string {
  if (typeof window === "undefined") {
    if (EXPLICIT_API_BASE_URL && !EXPLICIT_API_BASE_URL.startsWith("/")) {
      return EXPLICIT_API_BASE_URL;
    }
    return SERVER_API_BASE_URL;
  }

  if (EXPLICIT_API_BASE_URL) {
    return withAbsoluteOrigin(EXPLICIT_API_BASE_URL);
  }

  return CLIENT_PROXY_API_BASE_URL;
}

export const API_BASE_URL = resolveApiBaseUrl();

export function getApiBaseUrl(): string {
  return resolveApiBaseUrl();
}

// Get direct backend URL for admin/file operations that should bypass the proxy
function getDirectBackendUrl(): string {
  // On server side, use the backend URL directly
  if (typeof window === "undefined") {
    return process.env.BACKEND_API_BASE_URL || "http://localhost:8010";
  }
  // On client side, prefer an explicit public backend URL (e.g. EC2 IP via nginx port 80)
  if (process.env.NEXT_PUBLIC_BACKEND_URL) {
    return process.env.NEXT_PUBLIC_BACKEND_URL;
  }
  // Fallback: construct from window.location + port
  const { protocol, hostname } = window.location;
  const backendPort = process.env.NEXT_PUBLIC_BACKEND_PORT || "8010";
  return `${protocol}//${hostname}:${backendPort}`;
}

/**
 * Admin request — always targets the backend directly so auth-gated `/admin/*`
 * endpoints behave consistently across environments. Admin auth is enforced by
 * the backend's get_admin_session dependency (role == "Admin").
 */
async function adminRequest<T>(
  path: string,
  init?: RequestInit & { authToken?: string }
): Promise<T> {
  const { authToken, ...rest } = init || {};
  const headers = new Headers(rest.headers);
  headers.set("Content-Type", "application/json");

  // Support both cookie-only auth ("authenticated" pseudo-token) and real JWT
  if (authToken && authToken !== "authenticated") {
    headers.set("Authorization", `Bearer ${authToken}`);
  }

  const baseUrl = getDirectBackendUrl().replace(/\/$/, "");
  const url = `${baseUrl}${path}`;

  const res = await fetch(url, {
    ...rest,
    headers,
    cache: "no-store",
    credentials: "include",
  });

  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined") {
      clearAuthToken();
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    }
    const message = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(message.detail || `Request failed with ${res.status}`);
  }

  return (await res.json()) as T;
}

export type HealthResponse = {
  status: string;
};

export type ChatAttachment = {
  name: string;
  ext: string;
  previewUrl?: string; // data URL for image thumbnails
  isImage: boolean;
};

export type ChatMessageDTO = {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: string;
  sources?: Array<Record<string, unknown>>;
  agent?: string;
  route_reason?: string;
  model_used?: string;
  attachments?: ChatAttachment[];
};

export type ChatSessionDTO = {
  id: string;
  title: string;
  messages: ChatMessageDTO[];
  created_at?: string;
  updated_at?: string;
  is_pinned?: boolean;
  is_archived?: boolean;
};

export type QuizFolder = {
  path: string;
  label: string;
  file_count: number;
};

export type QuizQuestion = {
  id: string;
  question: string;
  options: string[];
  explanation?: string | null;
};

export type QuizHistoryEntry = {
  id: string;
  score: number;
  total_questions: number;
  percentage: number;
  created_at: string;
  metadata?: Record<string, unknown>;
};

export type ResearchFolder = QuizFolder;

export type ResearchDocument = {
  id: string;
  title: string;
  file_path?: string;
  source?: string;
  last_modified?: string;
};

export type ResearchAnswer = {
  answer: string;
  sources: Array<{
    score?: number;
    excerpt?: string;
    file_path?: string;
    title?: string;
  }>;
};

export type ResearchPreview = {
  preview_type: string;
  title: string;
  excerpt: string;
  thumbnail?: string;
  source?: string;
};

export type ResearchUpload = {
  id: string;
  file_name: string;
  path: string;
  size_bytes: number;
  uploaded_at: string;
};

export type KnowledgeBaseStats = {
  ready: boolean;
  document_count: number;
  source_count: number;
  sample_sources: string[];
  last_updated: string | null;
  last_updated_display: string | null;
  path: string;
};

export type AnnouncementCard = {
  id: string;
  title: string;
  body: string;
  accent: string;
};

export type ProfessorCard = {
  name: string;
  avatar?: string;
  links: { label: string; url: string }[];
  email?: string;
};

export type CourseTopic = {
  title: string;
  url?: string;
};

export type QuickAction = {
  title: string;
  description: string;
  href: string;
  icon?: string;
};

export type SystemStatus = {
  knowledge_base: KnowledgeBaseStats;
  vector_store_ready: boolean;
  chroma_ready: boolean;
  evaluation_ready: boolean;
  evaluation_cases: number;
  evaluation: Record<string, unknown>;
  ollama: {
    ready: boolean;
    models: string[];
    error?: string;
    base_url?: string;
  };
  issues: string[];
};

export type HomeOverview = {
  announcements: AnnouncementCard[];
  professor: ProfessorCard;
  course_topics: CourseTopic[];
  quick_actions: QuickAction[];
  system_status: SystemStatus;
};

export type EvaluationCase = {
  id: string;
  query: string;
  category?: string;
  difficulty?: string;
  expected_topics: string[];
};

export type EvaluationRetrievalMetrics = {
  precision_at_3: number;
  precision_at_5: number;
  recall_at_3: number;
  recall_at_5: number;
  mrr: number;
  ndcg: number;
  topics_found: string[];
  missing_topics: string[];
  retrieved_topic_coverage: number;
  relevant_doc_ratio: number;
  retrieval_success: boolean;
};

export type EvaluationGenerationMetrics = {
  topic_coverage: number;
  covered_topics: string[];
  missing_topics: string[];
  relevance_score: number;
  completeness: boolean;
  hallucination_flag: boolean;
  clarity_score: number;
  response_length_chars: number;
  response_length_words: number;
};

export type EvaluationResult = {
  test_id: string;
  query: string;
  category?: string;
  difficulty?: string;
  response: string;
  response_length: number;
  total_time: number;
  expected_topics: string[];
  retrieval_metrics: EvaluationRetrievalMetrics;
  generation_metrics: EvaluationGenerationMetrics;
};

export type RAGQualityMetrics = {
  faithfulness: number;
  answer_relevance: number;
  context_recall: number;
  context_precision: number;
  correctness: number;
  reasoning?: string;
};

export type QualitySummary = {
  avg_faithfulness: number;
  avg_answer_relevance: number;
  avg_context_recall: number;
  avg_context_precision: number;
  avg_correctness: number;
  evaluated_count: number;
};

export type BatchQualityResult = {
  total_evaluated: number;
  quality_summary: QualitySummary | null;
  individual_results: Array<{
    query: string;
    faithfulness: number;
    answer_relevance: number;
    context_recall: number;
    context_precision: number;
    correctness: number;
    reasoning?: string;
  }>;
  message?: string;
};

export type DatasetQualityResult = {
  total_evaluated: number;
  total_dataset_questions?: number;
  avg_latency?: number;
  quality_summary: QualitySummary | null;
  individual_results: Array<{
    query: string;
    faithfulness: number;
    answer_relevance: number;
    context_recall: number;
    context_precision: number;
    correctness: number;
    reasoning?: string;
    latency?: number;
    docs_retrieved?: number;
    avg_retrieval_score?: number;
  }>;
  message?: string;
};

export type EvaluationAnalysis = {
  total_tests: number;
  avg_response_time: number;
  p95_response_time: number;
  avg_topic_coverage: number;
  coverage_above_80: number;
  coverage_above_60: number;
  retrieval_summary: {
    precision_at_3: number;
    precision_at_5: number;
    recall_at_3: number;
    recall_at_5: number;
    mrr: number;
    ndcg: number;
  };
  generation_summary: {
    avg_relevance_score: number;
    avg_clarity_score: number;
    hallucination_rate: number;
  };
  quality_summary?: QualitySummary;
};

export type EvaluationRunResponse = {
  analysis: EvaluationAnalysis;
  results: EvaluationResult[];
};

export type EvaluationLogSummary = {
  total_queries_analyzed?: number;
  avg_retrieval_time_seconds?: number;
  avg_generation_time_seconds?: number;
  avg_total_time_seconds?: number;
  avg_num_retrieved?: number;
  avg_relevance_score?: number;
  error?: string;
};

export type EvaluationRunSummary = {
  total_evaluated?: number;
  total_dataset_questions?: number;
  avg_latency?: number;
  quality_summary?: QualitySummary | null;
  delta?: {
    avg_faithfulness?: number | null;
    avg_answer_relevance?: number | null;
    avg_context_recall?: number | null;
    avg_context_precision?: number | null;
    avg_correctness?: number | null;
    avg_latency?: number | null;
  };
};

export type EvaluationRunRecord = {
  run_id: string;
  timestamp: string;
  source: string;
  run_type: string;
  dataset: string;
  params: {
    limit?: number;
    model_id?: string | null;
  };
  summary: EvaluationRunSummary;
  sample_results: Array<{
    query: string;
    faithfulness: number;
    answer_relevance: number;
    context_recall: number;
    context_precision: number;
    correctness: number;
    latency?: number;
  }>;
};

// Real-time RAG Pipeline Metrics
export type RealtimeRAGSummary = {
  total_queries_analyzed: number;
  avg_retrieval_time_seconds: number;
  avg_generation_time_seconds: number;
  avg_total_time_seconds: number;
  p50_total_time_seconds: number;
  p95_total_time_seconds: number;
  p99_total_time_seconds: number;
  avg_relevance_score: number;
  min_relevance_score: number;
  max_relevance_score: number;
  avg_docs_retrieved: number;
  avg_response_length_words: number;
};

export type RealtimeRAGPerformance = {
  latency_distribution: {
    fast_under_2s: number;
    medium_2_to_5s: number;
    slow_over_5s: number;
    fast_percentage: number;
  };
  relevance_distribution: {
    high_above_0_7: number;
    medium_0_4_to_0_7: number;
    low_below_0_4: number;
    high_relevance_percentage: number;
  };
};

export type RealtimeRAGQuery = {
  timestamp: string;
  query: string;
  retrieval_time: number;
  generation_time: number;
  total_time: number;
  relevance_score: number;
  docs_retrieved: number;
  response_words: number;
  mode: string;
  quality_scores?: {
    faithfulness: number;
    answer_relevance: number;
    context_recall: number;
    correctness: number;
  };
};

export type RealtimeRAGMetrics = {
  status: "ok" | "no_data" | "error";
  message?: string;
  summary: RealtimeRAGSummary | null;
  performance: RealtimeRAGPerformance | null;
  quality_summary: QualitySummary | null;
  recent_queries: RealtimeRAGQuery[];
};

// Metrics History for Charts
export type MetricsHistoryDataPoint = {
  timestamp: string;
  query_count: number;
  avg_latency: number;
  avg_retrieval_latency: number;
  avg_generation_latency: number;
  avg_relevance: number;
  avg_docs_retrieved: number;
};

export type MetricsHistory = {
  status: "ok" | "no_data" | "error";
  message?: string;
  hours?: number;
  granularity?: string;
  total_queries?: number;
  data_points: MetricsHistoryDataPoint[];
};

async function request<T>(
  path: string,
  init?: RequestInit & { authToken?: string; timeoutMs?: number }
): Promise<T> {
  const { authToken, timeoutMs, ...rest } = init || {};
  const headers = new Headers(rest.headers);
  headers.set("Content-Type", "application/json");

  // SECURITY: HttpOnly cookies handle authentication
  // IMPORTANT: Don't add Authorization header when token is "authenticated" (pseudo-token)
  // Only add it for actual JWT tokens (backward compatibility for non-cookie auth)
  if (authToken && authToken !== "authenticated") {
    headers.set("Authorization", `Bearer ${authToken}`);
  }

  const baseUrl = resolveApiBaseUrl();

  // Set up timeout with AbortController if timeoutMs is provided
  const controller = new AbortController();
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  if (timeoutMs && timeoutMs > 0) {
    timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  }

  let res: Response;
  try {
    res = await fetch(`${baseUrl}${path}`, {
      ...rest,
      headers,
      cache: "no-store",
      credentials: "include", // SECURITY: Send HttpOnly cookies with all requests
      signal: controller.signal,
    });
  } catch (error) {
    if (timeoutId) clearTimeout(timeoutId);
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(`Request timed out after ${timeoutMs}ms`);
    }
    const message = error instanceof Error ? error.message : "Unknown fetch error";
    throw new Error(`Network request failed: ${message}`);
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }

  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined") {
      clearAuthToken();
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    }
    const message = await res
      .json()
      .catch(() => ({ detail: res.statusText }));
    throw new Error(message.detail || `Request failed with ${res.status}`);
  }

  return (await res.json()) as T;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function fetchHomeOverview(): Promise<HomeOverview> {
  return request<HomeOverview>("/home/overview", { timeoutMs: 8000 });
}

export async function postJSON<T>({
  path,
  body,
  token,
  timeoutMs,
}: {
  path: string;
  body: unknown;
  token?: string;
  timeoutMs?: number;
}) {
  return request<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
    authToken: token,
    timeoutMs,
  });
}

export async function patchJSON<T>({
  path,
  body,
  token,
}: {
  path: string;
  body: unknown;
  token?: string;
}) {
  return request<T>(path, {
    method: "PATCH",
    body: JSON.stringify(body),
    authToken: token,
  });
}

export async function deleteJSON<T>({
  path,
  body,
  token,
}: {
  path: string;
  body?: unknown;
  token?: string;
}) {
  return request<T>(path, {
    method: "DELETE",
    body: body ? JSON.stringify(body) : undefined,
    authToken: token,
  });
}

export async function getJSON<T>({
  path,
  token,
}: {
  path: string;
  token?: string;
}) {
  return request<T>(path, { method: "GET", authToken: token });
}

export async function listChatSessions(token: string): Promise<ChatSessionDTO[]> {
  const data = await getJSON<{ sessions: ChatSessionDTO[] }>({
    path: "/chat/sessions",
    token,
  });
  return data.sessions ?? [];
}

export async function fetchChatSession(token: string, sessionId: string) {
  return getJSON<{ session: ChatSessionDTO }>({
    path: `/chat/sessions/${sessionId}`,
    token,
  });
}

export async function renameChatSession(token: string, sessionId: string, title: string) {
  return patchJSON<{ session: ChatSessionDTO }>({
    path: `/chat/sessions/${sessionId}`,
    body: { title },
    token,
  });
}

export async function deleteChatSession(token: string, sessionId: string) {
  return deleteJSON<{ success: boolean }>({
    path: `/chat/sessions/${sessionId}`,
    token,
  });
}

export async function pinChatSession(token: string, sessionId: string, pinned: boolean) {
  return patchJSON<{ session: ChatSessionDTO }>({
    path: `/chat/sessions/${sessionId}`,
    body: { is_pinned: pinned },
    token,
  });
}

export async function archiveChatSession(token: string, sessionId: string, archived: boolean) {
  return patchJSON<{ session: ChatSessionDTO }>({
    path: `/chat/sessions/${sessionId}`,
    body: { is_archived: archived },
    token,
  });
}

export async function createChatSession({
  token,
  title,
}: {
  token: string;
  title?: string;
}): Promise<ChatSessionDTO> {
  const query = title ? `?title=${encodeURIComponent(title)}` : "";
  const data = await postJSON<{ session: ChatSessionDTO }>({
    path: `/chat/sessions${query}`,
    body: {},
    token,
  });
  return data.session;
}

export async function fetchQuizFolders(token: string): Promise<QuizFolder[]> {
  const data = await getJSON<{ folders: QuizFolder[] }>({
    path: "/quiz/folders",
    token,
  });
  return data.folders || [];
}

export async function generateQuiz({
  token,
  folders,
  numQuestions,
}: {
  token: string;
  folders: string[];
  numQuestions: number;
}) {
  return postJSON<{
    quiz_id: string;
    selected_folders: string[];
    questions: QuizQuestion[];
    generated_at: string;
  }>({
    path: "/quiz/generate",
    body: { folders, num_questions: numQuestions },
    token,
  });
}

export async function submitQuiz({
  token,
  payload,
}: {
  token: string;
  payload: {
    quiz_id: string;
    answers: Record<string, string>;
  };
}) {
  return postJSON<{ result: QuizHistoryEntry }>({
    path: "/quiz/submit",
    body: payload,
    token,
  });
}

export async function fetchQuizHistory(token: string) {
  return getJSON<{ results: QuizHistoryEntry[] }>({
    path: "/quiz/history",
    token,
  });
}

export async function fetchResearchFolders(token: string) {
  return getJSON<{ folders: ResearchFolder[] }>({
    path: "/research/folders",
    token,
  });
}

export async function fetchResearchDocuments(token: string) {
  return getJSON<{ documents: ResearchDocument[] }>({
    path: "/research/documents",
    token,
  });
}

export async function fetchResearchUploads(token: string): Promise<ResearchUpload[]> {
  const data = await getJSON<{ uploads: ResearchUpload[] }>({
    path: "/research/uploads",
    token,
  });
  return data.uploads ?? [];
}

export async function runResearchQuery({
  token,
  query,
  folders,
  uploaded_only,
}: {
  token: string;
  query: string;
  folders?: string[];
  uploaded_only?: boolean;
}) {
  return postJSON<ResearchAnswer>({
    path: "/research/query",
    body: { query, folders, uploaded_only },
    token,
  });
}

export async function fetchKnowledgeBaseStats(token: string): Promise<KnowledgeBaseStats> {
  const data = await getJSON<{ stats: KnowledgeBaseStats }>({
    path: "/research/stats",
    token,
  });
  return data.stats;
}

export type ResourceCategory = {
  name: string;
  links: { title: string; url: string }[];
};

// ── Dynamic Resource Types ──────────────────────────────────────

export type Resource = {
  id: string;
  category: string;
  title: string;
  url: string | null;
  description: string;
  type: "link" | "file";
  file_name: string | null;
  s3_key: string | null;
  file_size_bytes: number | null;
  mime_type: string | null;
  order: number;
  active: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export async function fetchResources(token: string) {
  return getJSON<{
    categories: Record<string, { title: string; url: string }[]>;
    resources?: Resource[];
  }>({
    path: "/resources",
    token,
  });
}

export async function getResourceDownloadUrl(
  token: string,
  resourceId: string
): Promise<{ download_url: string; file_name: string }> {
  return getJSON<{ download_url: string; file_name: string }>({
    path: `/resources/download/${encodeURIComponent(resourceId)}`,
    token,
  });
}

// ── Admin Resource API Functions ────────────────────────────────

export async function fetchAdminResources(token: string): Promise<{ resources: Resource[]; total: number }> {
  return adminRequest<{ resources: Resource[]; total: number }>("/admin/resources", { authToken: token });
}

export async function createResource(
  token: string,
  data: { category: string; title: string; url: string; description?: string; order?: number }
): Promise<Resource> {
  const res = await adminRequest<{ resource: Resource }>("/admin/resources", {
    method: "POST",
    body: JSON.stringify(data),
    authToken: token,
  });
  return res.resource;
}

export async function uploadResourceFile({
  token,
  file,
  category,
  title,
  description,
  order,
}: {
  token: string;
  file: File;
  category: string;
  title: string;
  description?: string;
  order?: number;
}): Promise<Resource> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("category", category);
  formData.append("title", title);
  if (description) formData.append("description", description);
  if (order !== undefined) formData.append("order", String(order));

  // Use direct backend URL so admin uploads and other admin APIs share the same routing path.
  const directUrl = getDirectBackendUrl();
  const response = await fetch(`${directUrl}/admin/resources/upload`, {
    method: "POST",
    headers: token && token !== "authenticated" ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
    credentials: "include",
  });

  if (!response.ok) {
    const msg = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(msg.detail || `Upload failed with ${response.status}`);
  }

  const data = (await response.json()) as { resource: Resource };
  return data.resource;
}

export async function updateResource(
  token: string,
  resourceId: string,
  data: Partial<{ category: string; title: string; url: string; description: string; order: number; active: boolean }>
): Promise<Resource> {
  const res = await adminRequest<{ resource: Resource }>(
    `/admin/resources/${encodeURIComponent(resourceId)}`,
    { method: "PUT", body: JSON.stringify(data), authToken: token }
  );
  return res.resource;
}

export async function deleteResource(
  token: string,
  resourceId: string
): Promise<{ success: boolean }> {
  return adminRequest<{ success: boolean }>(
    `/admin/resources/${encodeURIComponent(resourceId)}`,
    { method: "DELETE", authToken: token }
  );
}

export async function fetchResourceCategories(token: string): Promise<string[]> {
  const data = await adminRequest<{ categories: string[] }>("/admin/resources/categories", { authToken: token });
  return data.categories ?? [];
}

export async function migrateStaticResources(token: string): Promise<{ success: boolean; imported: number; total: number }> {
  return adminRequest<{ success: boolean; imported: number; total: number }>("/admin/resources/migrate", {
    method: "POST",
    body: JSON.stringify({}),
    authToken: token,
  });
}

export interface IndexStatus {
  status: string; // "queued" | "extracting" | "chunking" | "embedding" | "uploading" | "complete" | "error" | "not_started"
  progress_pct: number;
  chunks_created: number;
  total_chunks: number | null;
  error: string | null;
  started_at?: string;
  completed_at?: string | null;
}

export async function triggerReindex(
  token: string,
  resourceId: string
): Promise<{ started: boolean; resource_id: string }> {
  return adminRequest<{ started: boolean; resource_id: string }>(
    `/admin/resources/${encodeURIComponent(resourceId)}/reindex`,
    { method: "POST", body: JSON.stringify({}), authToken: token }
  );
}

export async function fetchIndexStatus(
  token: string,
  resourceId: string
): Promise<IndexStatus> {
  return adminRequest<IndexStatus>(
    `/admin/resources/${encodeURIComponent(resourceId)}/reindex-status`,
    { authToken: token }
  );
}

export type AppointmentRecord = {
  id: string;
  user_name: string;
  user_email: string;
  appointment_with: string;
  preferred_date: string;
  preferred_time: string;
  primary_reason: string;
  additional_details: string;
  status: string;
  requested_at: string;
};

export type ProfileUser = {
  username: string;
  email: string;
  display_name: string;
  phone_number: string;
  role: string;
  last_login: string;
  theme: "light" | "dark";
};

export type ProfileData = {
  user: ProfileUser;
  notes: string;
  recent_quizzes: QuizHistoryEntry[];
  recent_appointments: AppointmentRecord[];
  profile_picture?: string | null;
};

export type FeedbackHistory = {
  feedback: Array<{
    category: string;
    message: string;
    created_at: string;
    name?: string;
    email?: string;
  }>;
  bugs: Array<{
    feature: string;
    severity: string;
    description: string;
    steps?: string;
    created_at: string;
    name?: string;
    email?: string;
  }>;
};

export async function fetchAppointments(token: string) {
  return getJSON<{ appointments: AppointmentRecord[] }>({
    path: "/appointments",
    token,
  });
}

export async function createAppointment({
  token,
  payload,
}: {
  token: string;
  payload: {
    name: string;
    email: string;
    appointment_with: string;
    preferred_date: string;
    preferred_time: string;
    primary_reason: string;
    additional_details?: string;
  };
}) {
  return postJSON<{ appointment: AppointmentRecord }>({
    path: "/appointments",
    body: payload,
    token,
  });
}

async function fetchWithAuth<T>(
  path: string,
  token: string,
  init: RequestInit
): Promise<T> {
  const headers = new Headers(init.headers);
  // SECURITY: Keep Authorization header for backward compatibility
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: "include", // SECURITY: Send HttpOnly cookies
  });
  if (!response.ok) {
    const message = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(message.detail || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function uploadResearchFile({
  token,
  file,
}: {
  token: string;
  file: File;
}): Promise<ResearchPreview> {
  const formData = new FormData();
  formData.append("file", file);

  // Use the API base URL (goes through proxy)
  const baseUrl = getApiBaseUrl();
  const response = await fetch(
    `${baseUrl}/research/upload/file`,
    {
      method: "POST",
      headers: {
        // SECURITY: Keep Authorization header for backward compatibility
        Authorization: `Bearer ${token}`,
      },
      body: formData,
      credentials: "include", // SECURITY: Send HttpOnly cookies
    }
  );

  if (!response.ok) {
    const message = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(message.detail || `Upload failed with ${response.status}`);
  }

  const data = await response.json() as { preview: ResearchPreview };
  return data.preview;
}

export async function uploadResearchUrl({
  token,
  url,
}: {
  token: string;
  url: string;
}): Promise<ResearchPreview> {
  const data = await postJSON<{ preview: ResearchPreview }>({
    path: "/research/upload/url",
    body: { url },
    token,
  });
  return data.preview;
}

export async function uploadResearchYoutube({
  token,
  url,
}: {
  token: string;
  url: string;
}): Promise<ResearchPreview> {
  const data = await postJSON<{ preview: ResearchPreview }>({
    path: "/research/upload/youtube",
    body: { url },
    token,
  });
  return data.preview;
}

export async function clearResearchUploads(token: string): Promise<{ success: boolean; deleted_count: number }> {
  const baseUrl = getApiBaseUrl();
  try {
    const response = await fetch(`${baseUrl}/research/uploads/clear`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        // SECURITY: Keep Authorization header for backward compatibility
        Authorization: `Bearer ${token}`,
      },
      credentials: "include", // SECURITY: Send HttpOnly cookies
    });
    if (!response.ok) {
      // Don't throw for auth errors - just return success:false
      // This prevents errors when token expires or page is closing
      console.warn("Clear uploads failed:", response.status);
      return { success: false, deleted_count: 0 };
    }
    return response.json();
  } catch (err) {
    // Network errors during page unload are expected
    console.warn("Clear uploads error:", err);
    return { success: false, deleted_count: 0 };
  }
}

// ==================== RESEARCH CAPABILITIES TYPES ====================

export type WebSearchResult = {
  title: string;
  url: string;
  content: string;
};

export type WebSearchResponse = {
  query: string;
  web_results: WebSearchResult[];
  count: number;
  timestamp: string;
  error?: string;
};

export type AcademicPaper = {
  title: string;
  authors: string[];
  abstract: string;
  url: string;
  source: "arxiv" | "pubmed" | "scholar";
  published_date?: string;
  doi?: string;
  cited_by?: number;
};

export type AcademicSearchResponse = {
  query: string;
  papers: AcademicPaper[];
  sources_searched: string[];
  count: number;
  errors?: Array<{ source: string; error: string }>;
  timestamp: string;
};

export type SourceComparison = {
  document_title: string;
  file_path?: string;
  excerpts: string[];
  relevance_score: number;
};

export type ComparisonResult = {
  topic: string;
  documents_analyzed: number;
  comparisons: SourceComparison[];
  agreements: string[];
  contradictions: string[];
  summary: string;
  timestamp: string;
};

export type Citation = {
  raw: string;
  formatted: string;
  authors?: string[];
  title?: string;
  year?: string;
};

export type CitationResult = {
  citations: Citation[];
  format: string;
  count: number;
  exportable_bibliography: string;
  message?: string;
  timestamp: string;
};

export type SummaryResult = {
  mode: string;
  summary: string;
  source_document?: string;
  word_count?: number;
  timestamp: string;
};

export type StudyQuestion = {
  id: string;
  question: string;
  type: "mcq" | "short_answer" | "essay";
  difficulty: string;
  options?: string[];
  answer?: string;
  explanation?: string;
};

export type QuestionsResult = {
  questions: StudyQuestion[];
  difficulty: string;
  types: string[];
  count: number;
  source_document?: string;
  message?: string;
  error?: string;
  timestamp: string;
};

export type FactCheckEvidence = {
  source_type: "document" | "web";
  title: string;
  excerpt: string;
  supports_claim: boolean;
  confidence: number;
  analysis?: string;
  url?: string;
};

export type FactCheckResult = {
  claim: string;
  verdict: "supported" | "contradicted" | "inconclusive";
  confidence: number;
  supporting_sources: FactCheckEvidence[];
  contradicting_sources: FactCheckEvidence[];
  evidence: FactCheckEvidence[];
  timestamp: string;
};

// ==================== RESEARCH CAPABILITIES API FUNCTIONS ====================

export async function searchWeb({
  token,
  query,
  max_results = 5,
}: {
  token: string;
  query: string;
  max_results?: number;
}): Promise<WebSearchResponse> {
  return postJSON<WebSearchResponse>({
    path: "/research/search/web",
    body: { query, max_results },
    token,
  });
}

export async function searchAcademicPapers({
  token,
  query,
  sources,
  max_results = 10,
}: {
  token: string;
  query: string;
  sources?: string[];
  max_results?: number;
}): Promise<AcademicSearchResponse> {
  return postJSON<AcademicSearchResponse>({
    path: "/research/search/academic",
    body: { query, sources, max_results },
    token,
  });
}

export async function compareSources({
  token,
  topic,
  document_ids,
  uploaded_only = true,
}: {
  token: string;
  topic: string;
  document_ids?: string[];
  uploaded_only?: boolean;
}): Promise<ComparisonResult> {
  return postJSON<ComparisonResult>({
    path: "/research/compare",
    body: { topic, document_ids, uploaded_only },
    token,
  });
}

export async function extractCitations({
  token,
  document_id,
  format_style = "apa",
}: {
  token: string;
  document_id?: string;
  format_style?: string;
}): Promise<CitationResult> {
  return postJSON<CitationResult>({
    path: "/research/citations",
    body: { document_id, format_style },
    token,
  });
}

export async function generateSummary({
  token,
  document_id,
  mode = "executive",
  max_length,
}: {
  token: string;
  document_id?: string;
  mode?: string;
  max_length?: number;
}): Promise<SummaryResult> {
  return postJSON<SummaryResult>({
    path: "/research/summary",
    body: { document_id, mode, max_length },
    token,
  });
}

export async function generateStudyQuestions({
  token,
  document_id,
  difficulty = "medium",
  question_types,
  count = 5,
}: {
  token: string;
  document_id?: string;
  difficulty?: string;
  question_types?: string[];
  count?: number;
}): Promise<QuestionsResult> {
  return postJSON<QuestionsResult>({
    path: "/research/questions",
    body: { document_id, difficulty, question_types, count },
    token,
  });
}

export async function factCheck({
  token,
  claim,
  uploaded_only = true,
  include_web = false,
}: {
  token: string;
  claim: string;
  uploaded_only?: boolean;
  include_web?: boolean;
}): Promise<FactCheckResult> {
  return postJSON<FactCheckResult>({
    path: "/research/fact-check",
    body: { claim, uploaded_only, include_web },
    token,
  });
}

// ==================== END RESEARCH CAPABILITIES ====================

export async function fetchProfile(token: string): Promise<ProfileData> {
  const data = await getJSON<{ profile: ProfileData }>({
    path: "/profile",
    token,
  });
  return data.profile;
}

export async function fetchProfileQuizHistory(token: string): Promise<QuizHistoryEntry[]> {
  const data = await getJSON<{ results: QuizHistoryEntry[] }>({
    path: "/profile/history/quizzes",
    token,
  });
  return data.results ?? [];
}

export async function fetchProfileAppointmentsHistory(token: string): Promise<AppointmentRecord[]> {
  const data = await getJSON<{ appointments: AppointmentRecord[] }>({
    path: "/profile/history/appointments",
    token,
  });
  return data.appointments ?? [];
}

export async function fetchFeedbackHistory(token: string): Promise<FeedbackHistory> {
  return getJSON<FeedbackHistory>({
    path: "/profile/history/feedback",
    token,
  });
}

export async function updateProfileDetails({
  token,
  updates,
}: {
  token: string;
  updates: Partial<Pick<ProfileUser, "display_name" | "phone_number" | "theme">>;
}) {
  const data = await patchJSON<{ user: ProfileUser }>({
    path: "/profile",
    body: updates,
    token,
  });
  return data.user;
}

export async function saveProfileNotes({
  token,
  content,
}: {
  token: string;
  content: string;
}) {
  const data = await postJSON<{ notes: string }>({
    path: "/profile/notes",
    body: { content },
    token,
  });
  return data.notes;
}

export async function changeProfilePassword({
  token,
  current_password,
  new_password,
}: {
  token: string;
  current_password: string;
  new_password: string;
}) {
  return postJSON<{ success: boolean }>({
    path: "/profile/password",
    body: { current_password, new_password },
    token,
  });
}

export async function deleteAccount({
  token,
  confirm_username,
}: {
  token: string;
  confirm_username: string;
}) {
  return deleteJSON<{ success: boolean }>({
    path: "/profile",
    body: { confirm_username },
    token,
  });
}

export async function uploadProfilePicture({
  token,
  file,
}: {
  token: string;
  file: File;
}) {
  const formData = new FormData();
  formData.append("file", file);
  const data = await fetchWithAuth<{ profile_picture: string | null }>(
    "/profile/picture",
    token,
    {
      method: "POST",
      body: formData,
    }
  );
  return data.profile_picture;
}

export async function fetchEvaluationCases({
  token,
  limit,
}: {
  token: string;
  limit?: number;
}): Promise<EvaluationCase[]> {
  const query = typeof limit === "number" ? `?limit=${limit}` : "";
  const data = await getJSON<{ cases: EvaluationCase[] }>({
    path: `/evaluation/cases${query}`,
    token,
  });
  return data.cases ?? [];
}

export async function runEvaluationSuite({
  token,
  limit,
  categories,
  difficulties,
  enableQualityEval,
}: {
  token: string;
  limit?: number;
  categories?: string[];
  difficulties?: string[];
  enableQualityEval?: boolean;
}): Promise<EvaluationRunResponse> {
  const body: Record<string, unknown> = {};
  if (typeof limit === "number") body.limit = limit;
  if (categories && categories.length > 0) body.categories = categories;
  if (difficulties && difficulties.length > 0) body.difficulties = difficulties;
  if (enableQualityEval) body.enable_quality_eval = true;

  // Use 2-minute timeout for evaluation runs (they can take 30-60s for multiple tests)
  return postJSON<EvaluationRunResponse>({
    path: "/evaluation/run",
    body,
    token,
    timeoutMs: 120000,
  });
}

export async function runBatchQuality(
  token: string,
  lastN: number = 20,
  modelId?: string
): Promise<BatchQualityResult> {
  const body: Record<string, unknown> = { last_n: lastN };
  if (modelId) body.model_id = modelId;

  return postJSON<BatchQualityResult>({
    path: "/evaluation/batch-quality",
    body,
    token,
    timeoutMs: 300000, // 5 min — LLM calls can be slow for large batches
  });
}

export async function runDatasetQuality(
  token: string,
  limit: number = 10,
  modelId?: string
): Promise<DatasetQualityResult> {
  const body: Record<string, unknown> = { limit };
  if (modelId) body.model_id = modelId;

  return postJSON<DatasetQualityResult>({
    path: "/evaluation/run-dataset-quality",
    body,
    token,
    timeoutMs: 600000, // 10 min — runs each question through full pipeline
  });
}

export async function fetchEvaluationLogSummary(token: string): Promise<EvaluationLogSummary> {
  const data = await getJSON<{ summary: EvaluationLogSummary }>({
    path: "/evaluation/summary",
    token,
  });
  return data.summary;
}

export async function fetchEvaluationRuns(
  token: string,
  limit: number = 10
): Promise<EvaluationRunRecord[]> {
  const data = await getJSON<{ runs: EvaluationRunRecord[] }>({
    path: `/evaluation/runs?limit=${limit}`,
    token,
  });
  return data.runs ?? [];
}

export async function fetchRealtimeRAGMetrics(token: string, lastN?: number): Promise<RealtimeRAGMetrics> {
  const query = lastN ? `?last_n=${lastN}` : "";
  const data = await getJSON<{ realtime_metrics: RealtimeRAGMetrics }>({
    path: `/evaluation/realtime-metrics${query}`,
    token,
  });
  return data.realtime_metrics;
}

export async function fetchMetricsHistory(
  token: string,
  hours: number = 24,
  granularity: "minute" | "hour" | "day" = "hour"
): Promise<MetricsHistory> {
  const data = await getJSON<{ history: MetricsHistory }>({
    path: `/evaluation/metrics-history?hours=${hours}&granularity=${granularity}`,
    token,
  });
  return data.history;
}

export function getMetricsExportUrl(format: "json" | "csv" = "json"): string {
  const baseUrl = resolveApiBaseUrl();
  return `${baseUrl}/evaluation/export?format=${format}`;
}

export async function clearEvaluationLogs(token: string) {
  return postJSON<{ status: string }>({
    path: "/evaluation/logs/clear",
    body: {},
    token,
  });
}

// AWS Metrics Types
export type AWSServiceStatus = "active" | "limited" | "error" | "unavailable";

export type AWSMetrics = {
  timestamp: string;
  region: string;
  services: {
    bedrock?: {
      status: AWSServiceStatus;
      models?: {
        llm: {
          model_id: string;
          pricing: { input_per_1k: number; output_per_1k: number };
        };
        embedding: {
          model_id: string;
          pricing: { input_per_1k: number };
          dimension: number;
        };
      };
      available_models?: Array<{ id: string; name: string; type: string }>;
      error?: string;
    };
    s3?: {
      status: AWSServiceStatus;
      bucket?: string;
      total_objects?: number;
      total_size_mb?: number;
      index_prefix?: string;
      documents_prefix?: string;
      pricing?: { storage_per_gb_month: number; get_per_1k: number; put_per_1k: number };
      error?: string;
    };
    dynamodb?: {
      status: AWSServiceStatus;
      table_name?: string;
      item_count?: number;
      size_bytes?: number;
      size_mb?: number;
      billing_mode?: string;
      table_status?: string;
      pricing?: { read_per_million: number; write_per_million: number; storage_per_gb_month: number };
      error?: string;
    };
    sts?: {
      status: AWSServiceStatus;
      account_id?: string;
      arn_suffix?: string;
      error?: string;
    };
    cloudwatch?: {
      status: AWSServiceStatus;
      bedrock_invocations_today?: number;
      note?: string;
    };
  };
  costs: {
    daily: {
      date: string;
      total_cost_usd: number;
      total_tokens: number;
      entries: number;
      by_service?: Record<string, number>;
      error?: string;
    };
    tracking_enabled: boolean;
  };
  summary: {
    total_services: number;
    active_services: number;
    has_errors: boolean;
  };
  errors: string[];
};

export async function fetchAWSMetrics(token: string, date?: string): Promise<AWSMetrics> {
  const query = date ? `?date=${date}` : "";
  const data = await getJSON<{ aws_metrics: AWSMetrics }>({
    path: `/evaluation/aws-metrics${query}`,
    token,
  });
  return data.aws_metrics;
}

// Code Sandbox Types
export type CodeLanguage = "python" | "javascript" | "java";

export type CodeExecuteRequest = {
  code: string;
  language: CodeLanguage;
};

export type CodeExecuteResponse = {
  output: string;
  success: boolean;
  error?: string;
};

export type CodeGenerateRequest = {
  prompt: string;
  language: CodeLanguage;
};

export type CodeGenerateResponse = {
  code: string;
  language: string;
};

export type CodeExplainRequest = {
  code: string;
  language: CodeLanguage;
};

export type CodeExplainResponse = {
  explanation: string;
};

export type CodeDebugRequest = {
  code: string;
  language: CodeLanguage;
};

export type CodeDebugResponse = {
  analysis: string;
  fixed_code?: string;
};

export type CodeChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type CodeChatRequest = {
  message: string;
  history?: CodeChatMessage[];
};

export type CodeChatResponse = {
  response: string;
};

// Code Sandbox API Functions
export async function executeCode({
  token,
  code,
  language,
}: {
  token: string;
  code: string;
  language: CodeLanguage;
}): Promise<CodeExecuteResponse> {
  return postJSON<CodeExecuteResponse>({
    path: "/code/execute",
    body: { code, language },
    token,
  });
}

export async function generateCode({
  token,
  prompt,
  language,
}: {
  token: string;
  prompt: string;
  language: CodeLanguage;
}): Promise<CodeGenerateResponse> {
  return postJSON<CodeGenerateResponse>({
    path: "/code/generate",
    body: { prompt, language },
    token,
  });
}

export async function explainCode({
  token,
  code,
  language,
}: {
  token: string;
  code: string;
  language: CodeLanguage;
}): Promise<CodeExplainResponse> {
  return postJSON<CodeExplainResponse>({
    path: "/code/explain",
    body: { code, language },
    token,
  });
}

export async function debugCode({
  token,
  code,
  language,
}: {
  token: string;
  code: string;
  language: CodeLanguage;
}): Promise<CodeDebugResponse> {
  return postJSON<CodeDebugResponse>({
    path: "/code/debug",
    body: { code, language },
    token,
  });
}

export async function chatWithCodeLLM({
  token,
  message,
  history,
}: {
  token: string;
  message: string;
  history?: CodeChatMessage[];
}): Promise<CodeChatResponse> {
  return postJSON<CodeChatResponse>({
    path: "/code/chat",
    body: { message, history },
    token,
  });
}

export async function getSupportedLanguages(token: string): Promise<{ languages: CodeLanguage[] }> {
  return getJSON<{ languages: CodeLanguage[] }>({
    path: "/code/languages",
    token,
  });
}

// Research Chat Types and Functions
export type ResearchChatMessage = {
  role: "user" | "assistant";
  content: string;
  sources?: Array<{
    title?: string;
    file_path?: string;
    excerpt?: string;
  }>;
  timestamp?: string;
};

export type ResearchChatHistory = {
  messages: ResearchChatMessage[];
  created_at: string;
  updated_at: string;
};

export async function getRecentChatSessions(token: string, limit: number = 3): Promise<ChatSessionDTO[]> {
  const sessions = await listChatSessions(token);
  return sessions.slice(0, limit);
}

export type ShareSessionResponse = {
  share_id: string;
  share_url: string;
  expires_at: string;
  session: ChatSessionDTO;
};

export type SharedSessionInfo = {
  title: string;
  message_count: number;
  created_at: string;
  expires_at: string;
};

export async function shareChatSession(
  token: string,
  sessionId: string,
  expiresInHours: number = 7
): Promise<ShareSessionResponse> {
  return postJSON<ShareSessionResponse>({
    path: `/chat/sessions/${sessionId}/share`,
    body: { expires_in_hours: expiresInHours },
    token,
  });
}

export async function getSharedChatSession(shareId: string): Promise<{ session: ChatSessionDTO; expires_at: string }> {
  return getJSON<{ session: ChatSessionDTO; expires_at: string }>({
    path: `/chat/share/${shareId}`,
  });
}

export async function getSharedChatSessionInfo(shareId: string): Promise<SharedSessionInfo> {
  return getJSON<SharedSessionInfo>({
    path: `/chat/share/${shareId}/info`,
  });
}

export async function revokeSharedChatSession(token: string, shareId: string): Promise<{ success: boolean }> {
  return deleteJSON<{ success: boolean }>({
    path: `/chat/share/${shareId}`,
    token,
  });
}

// ==================== MESSAGE FEEDBACK TYPES ====================

export type MessageFeedbackType = "thumbs_up" | "thumbs_down" | "report";

export type MessageFeedbackRequest = {
  type: MessageFeedbackType;
  reason?: string;
};

export type MessageFeedbackResponse = {
  success: boolean;
  feedback_type: MessageFeedbackType | null;
  message?: string;
};

export type SessionFeedbackMap = Record<number, MessageFeedbackType>;

// ==================== MESSAGE FEEDBACK API FUNCTIONS ====================

export async function submitMessageFeedback({
  token,
  sessionId,
  messageIndex,
  feedbackType,
  reason,
}: {
  token: string;
  sessionId: string;
  messageIndex: number;
  feedbackType: MessageFeedbackType;
  reason?: string;
}): Promise<MessageFeedbackResponse> {
  return postJSON<MessageFeedbackResponse>({
    path: `/chat/sessions/${sessionId}/messages/${messageIndex}/feedback`,
    body: { type: feedbackType, reason },
    token,
  });
}

export async function getMessageFeedback({
  token,
  sessionId,
  messageIndex,
}: {
  token: string;
  sessionId: string;
  messageIndex: number;
}): Promise<{ feedback_type: MessageFeedbackType | null }> {
  return getJSON<{ feedback_type: MessageFeedbackType | null }>({
    path: `/chat/sessions/${sessionId}/messages/${messageIndex}/feedback`,
    token,
  });
}

export async function getSessionFeedback({
  token,
  sessionId,
}: {
  token: string;
  sessionId: string;
}): Promise<{ feedback: SessionFeedbackMap }> {
  return getJSON<{ feedback: SessionFeedbackMap }>({
    path: `/chat/sessions/${sessionId}/feedback`,
    token,
  });
}

// ==================== ADMIN API TYPES ====================

export type AdminStats = {
  total_users: number;
  total_queries: number;
  total_feedback: number;
  new_feedback: number;
  active_announcements: number;
  admin_users: number;
};

export type AdminUser = {
  username: string;
  email: string;
  role: string;
  display_name?: string;
  last_login?: string;
  created_at?: string;
};

export type Announcement = {
  id: string;
  title: string;
  content: string;
  priority: "info" | "warning" | "critical";
  author: string;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type AdminFeedbackEntry = {
  id: string;
  username: string;
  type: "feedback" | "bug";
  status: "new" | "reviewed" | "resolved";
  created_at: string;
  // feedback fields
  category?: string;
  message?: string;
  name?: string;
  email?: string;
  // bug fields
  feature?: string;
  severity?: string;
  description?: string;
  steps?: string;
};

export type QuizMetrics = {
  total_quizzes: number;
  unique_users: number;
  avg_percentage: number;
  highest_percentage: number;
  lowest_percentage: number;
  total_questions_answered: number;
  score_distribution: Record<string, number>;
  popular_topics: Array<{ folder: string; quiz_count: number }>;
  recent_activity: Array<{ date: string; count: number; avg_score: number }>;
  top_performers: Array<{ username: string; quizzes_taken: number; avg_score: number }>;
  error?: string;
};

function normalizeQuizMetrics(metrics?: Partial<QuizMetrics> | null): QuizMetrics {
  const scoreDistribution = metrics?.score_distribution ?? {};
  return {
    total_quizzes: Number(metrics?.total_quizzes ?? 0),
    unique_users: Number(metrics?.unique_users ?? 0),
    avg_percentage: Number(metrics?.avg_percentage ?? 0),
    highest_percentage: Number(metrics?.highest_percentage ?? 0),
    lowest_percentage: Number(metrics?.lowest_percentage ?? 0),
    total_questions_answered: Number(metrics?.total_questions_answered ?? 0),
    score_distribution: {
      "0-20": Number(scoreDistribution["0-20"] ?? 0),
      "20-40": Number(scoreDistribution["20-40"] ?? 0),
      "40-60": Number(scoreDistribution["40-60"] ?? 0),
      "60-80": Number(scoreDistribution["60-80"] ?? 0),
      "80-100": Number(scoreDistribution["80-100"] ?? 0),
    },
    popular_topics: Array.isArray(metrics?.popular_topics) ? metrics.popular_topics : [],
    recent_activity: Array.isArray(metrics?.recent_activity) ? metrics.recent_activity : [],
    top_performers: Array.isArray(metrics?.top_performers) ? metrics.top_performers : [],
    error: metrics?.error,
  };
}

// ==================== ADMIN API FUNCTIONS ====================

export async function fetchAdminStats(token: string): Promise<AdminStats> {
  const data = await adminRequest<{ stats: AdminStats }>("/admin/stats", { authToken: token });
  return data.stats;
}

export async function fetchQuizMetrics(token: string): Promise<QuizMetrics> {
  const data = await adminRequest<{ quiz_metrics: QuizMetrics }>("/admin/quiz-metrics", { authToken: token });
  return normalizeQuizMetrics(data.quiz_metrics);
}

export async function fetchAdminUsers(token: string): Promise<AdminUser[]> {
  const data = await adminRequest<{ users: AdminUser[] }>("/admin/users", { authToken: token });
  return data.users ?? [];
}

export async function updateUserRole(
  token: string,
  username: string,
  role: string
): Promise<{ success: boolean }> {
  return adminRequest<{ success: boolean }>(`/admin/users/${encodeURIComponent(username)}/role`, {
    method: "PUT",
    body: JSON.stringify({ role }),
    authToken: token,
  });
}

export async function deleteAdminUser(
  token: string,
  username: string
): Promise<{ success: boolean }> {
  return adminRequest<{ success: boolean }>(`/admin/users/${encodeURIComponent(username)}`, {
    method: "DELETE",
    authToken: token,
  });
}

export async function fetchAllFeedback(
  token: string,
  feedbackType?: string,
  limit?: number
): Promise<{ feedback: AdminFeedbackEntry[]; total: number }> {
  const params = new URLSearchParams();
  if (feedbackType) params.set("feedback_type", feedbackType);
  if (limit) params.set("limit", String(limit));
  const query = params.toString() ? `?${params.toString()}` : "";
  return adminRequest<{ feedback: AdminFeedbackEntry[]; total: number }>(`/admin/feedback${query}`, { authToken: token });
}

export async function updateFeedbackStatus(
  token: string,
  feedbackId: string,
  newStatus: string
): Promise<{ success: boolean }> {
  return adminRequest<{ success: boolean }>(`/admin/feedback/${encodeURIComponent(feedbackId)}`, {
    method: "PUT",
    body: JSON.stringify({ status: newStatus }),
    authToken: token,
  });
}

export async function fetchAdminAnnouncements(token: string): Promise<Announcement[]> {
  const data = await adminRequest<{ announcements: Announcement[] }>("/admin/announcements", { authToken: token });
  return data.announcements ?? [];
}

export async function createAnnouncement(
  token: string,
  data: { title: string; content: string; priority: string }
): Promise<Announcement> {
  const res = await adminRequest<{ announcement: Announcement }>("/admin/announcements", {
    method: "POST",
    body: JSON.stringify(data),
    authToken: token,
  });
  return res.announcement;
}

export async function updateAnnouncement(
  token: string,
  id: string,
  data: Partial<{ title: string; content: string; priority: string; active: boolean }>
): Promise<Announcement> {
  const res = await adminRequest<{ announcement: Announcement }>(`/admin/announcements/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(data),
    authToken: token,
  });
  return res.announcement;
}

export async function deleteAnnouncement(
  token: string,
  id: string
): Promise<{ success: boolean }> {
  return adminRequest<{ success: boolean }>(`/admin/announcements/${encodeURIComponent(id)}`, {
    method: "DELETE",
    authToken: token,
  });
}

export async function fetchPublicAnnouncements(): Promise<Announcement[]> {
  const data = await request<{ announcements: Announcement[] }>("/home/announcements");
  return data.announcements ?? [];
}

// ── Agent & Knowledge Graph Metrics ──────────────────────────────

export type AgentMetrics = {
  total_agent_interactions: number;
  unique_users: number;
  agent_distribution: Record<string, number>;
  avg_response_time_ms: number;
  response_time_by_agent: Record<string, number>;
  daily_usage: Array<{ date: string; count: number; unique_users: number }>;
  top_query_types: Array<{ type: string; count: number }>;
  routing_accuracy: { positive_after_route: number; negative_after_route: number };
  error?: string;
};

function normalizeAgentMetrics(metrics?: Partial<AgentMetrics> | null): AgentMetrics {
  return {
    total_agent_interactions: Number(metrics?.total_agent_interactions ?? 0),
    unique_users: Number(metrics?.unique_users ?? 0),
    agent_distribution: metrics?.agent_distribution ?? {},
    avg_response_time_ms: Number(metrics?.avg_response_time_ms ?? 0),
    response_time_by_agent: metrics?.response_time_by_agent ?? {},
    daily_usage: Array.isArray(metrics?.daily_usage) ? metrics.daily_usage : [],
    top_query_types: Array.isArray(metrics?.top_query_types) ? metrics.top_query_types : [],
    routing_accuracy: {
      positive_after_route: Number(metrics?.routing_accuracy?.positive_after_route ?? 0),
      negative_after_route: Number(metrics?.routing_accuracy?.negative_after_route ?? 0),
    },
    error: metrics?.error,
  };
}

export type KnowledgeGraphMetrics = {
  total_nodes: number;
  total_relationships: number;
  nodes_by_type: Record<string, number>;
  relationships_by_type: Record<string, number>;
  most_struggled_concepts: Array<{ concept: string; students: number }>;
  most_studied_topics: Array<{ topic: string; study_count: number }>;
  student_engagement: Array<{ username: string; queries: number; sessions: number; doubts: number }>;
  feedback_sentiment_overview: Record<string, number>;
  error?: string;
};

function normalizeKnowledgeGraphMetrics(
  metrics?: Partial<KnowledgeGraphMetrics> | null
): KnowledgeGraphMetrics {
  return {
    total_nodes: Number(metrics?.total_nodes ?? 0),
    total_relationships: Number(metrics?.total_relationships ?? 0),
    nodes_by_type: metrics?.nodes_by_type ?? {},
    relationships_by_type: metrics?.relationships_by_type ?? {},
    most_struggled_concepts: Array.isArray(metrics?.most_struggled_concepts)
      ? metrics.most_struggled_concepts
      : [],
    most_studied_topics: Array.isArray(metrics?.most_studied_topics)
      ? metrics.most_studied_topics
      : [],
    student_engagement: Array.isArray(metrics?.student_engagement)
      ? metrics.student_engagement
      : [],
    feedback_sentiment_overview: metrics?.feedback_sentiment_overview ?? {},
    error: metrics?.error,
  };
}

export async function fetchAgentMetrics(token: string): Promise<AgentMetrics> {
  const data = await adminRequest<{ agent_metrics: AgentMetrics }>("/admin/agent-metrics", { authToken: token });
  return normalizeAgentMetrics(data.agent_metrics);
}

export async function fetchKnowledgeGraphMetrics(token: string): Promise<KnowledgeGraphMetrics> {
  const data = await adminRequest<{ knowledge_graph_metrics: KnowledgeGraphMetrics }>("/admin/knowledge-graph-metrics", { authToken: token });
  return normalizeKnowledgeGraphMetrics(data.knowledge_graph_metrics);
}
