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

export function ensureAbsoluteAppUrl(url: string): string {
  return withAbsoluteOrigin(url);
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

function joinApiUrl(baseUrl: string, path: string): string {
  const normalizedBase = baseUrl.replace(/\/$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBase}${normalizedPath}`;
}

const CSRF_MUTATION_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

// The csrf_token cookie is set with HttpOnly=false (backend/csrf_protection.py)
// precisely so the browser can echo it back as X-CSRF-Token for the
// double-submit check. The Next.js proxy forwards this header automatically;
// callers that bypass the proxy (adminRequest fallback, uploadResourceFile)
// must set it themselves or the backend's csrf_protect dependency will 403.
function readCsrfTokenCookie(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((c) => c.startsWith("csrf_token="));
  if (!match) return null;
  return decodeURIComponent(match.slice("csrf_token=".length)) || null;
}

function getAdminRequestTargets(path: string): string[] {
  // Keep browser requests same-origin. A public port fallback is unreliable in
  // deployments and can bypass the cookie/security boundary of the app proxy.
  return [joinApiUrl(resolveApiBaseUrl(), path)];
}

async function parseRequestError(response: Response): Promise<Error & { status?: number }> {
  const payload = await response
    .json()
    .catch(() => ({ detail: response.statusText || `Request failed with ${response.status}` }));
  const error = new Error(payload.detail || `Request failed with ${response.status}`) as Error & {
    status?: number;
  };
  error.status = response.status;
  return error;
}

/**
 * Admin requests always use the configured API base. In the browser this is the
 * same-origin proxy, preserving the application's auth and security boundary.
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

  // CSRF double-submit for direct-backend fallback. The proxy already adds
  // this header (api/backend/[...path]/route.ts:147), but if the proxy fails
  // and we fall through to getDirectBackendUrl(), the backend's csrf_protect
  // dependency would 403 without it.
  const method = (rest.method ?? "GET").toUpperCase();
  if (CSRF_MUTATION_METHODS.has(method) && !headers.has("X-CSRF-Token")) {
    const csrfToken = readCsrfTokenCookie();
    if (csrfToken) {
      headers.set("X-CSRF-Token", csrfToken);
    }
  }

  const targets = getAdminRequestTargets(path);
  let lastError: (Error & { status?: number }) | null = null;

  for (const url of targets) {
    try {
      const res = await fetch(url, {
        ...rest,
        headers,
        cache: "no-store",
        credentials: "include",
      });

      if (!res.ok) {
        lastError = await parseRequestError(res);
        continue;
      }

      return (await res.json()) as T;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error("Request failed");
    }
  }

  if (lastError?.status === 401 && typeof window !== "undefined") {
    clearAuthToken();
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  }

  throw lastError ?? new Error("Request failed");
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
  course_id?: string | null;
};

export type QuizFolder = {
  path: string;
  label: string;
  file_count: number;
};

export type Course = {
  id: string;
  code: string;
  title: string;
  description: string;
  membership_role: "student" | "instructor" | "admin";
};

export type CourseCatalogEntry = Omit<Course, "membership_role"> & {
  enrolled: boolean;
};

export type CourseMembership = {
  username: string;
  course_id: string;
  role: "student" | "instructor";
  active: boolean;
  enrolled_at: string;
};

export type CourseIngestionDocument = IndexStatus & {
  resource_id: string;
  title: string;
  file_name: string;
  active: boolean;
  indexable: boolean;
};

export type CourseIngestionStatus = {
  course_id: string;
  total_documents: number;
  indexable_documents: number;
  status_counts: Record<string, number>;
  documents: CourseIngestionDocument[];
};

export type ObjectiveCoverage = {
  course_id: string;
  total_objectives: number;
  covered_objectives: number;
  coverage_pct: number;
  objectives: Array<{ objective_id: string; title: string; module_id: string; quiz_item_count: number; assessed_item_count: number; covered: boolean }>;
};

export type InstructorSummary = {
  course_id: string;
  enrolled_students: number;
  objectives: Array<{ objective_id: string; title: string; student_count: number; average_mastery: number | null }>;
};

export type MasterySnapshot = {
  objective_id: string;
  title: string;
  module_id: string;
  score: number;
  attempts: number;
  correct: number;
  next_review_at?: string | null;
  self_confidence?: number | null;
};

export type StudyRecommendation = {
  objective_id: string;
  title: string;
  module_id: string;
  mastery: number;
  reason: string;
  difficulty: "easy" | "medium" | "hard";
};

export type LearningDashboard = {
  course: Pick<Course, "id" | "code" | "title"> | null;
  mastery: MasterySnapshot[];
  recommendation: StudyRecommendation | null;
  weekly_goal: { target: number; completed: number };
  recent_activity: Array<{ id: string; created_at: string; is_correct: boolean }>;
};

export type QuizQuestion = {
  id: string;
  question: string;
  options: string[];
  explanation?: string | null;
  objective_id?: string | null;
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

export type DriftSummary = {
  enabled: boolean;
  baseline_path: string;
  scored_count: number;
  avg_drift_score: number | null;
  max_drift_score: number | null;
  high_drift_threshold: number;
  high_drift_count: number;
  high_drift_percentage: number;
};

export type BatchQualityResult = {
  total_evaluated: number;
  quality_summary: QualitySummary | null;
  individual_results: Array<{
    query: string;
    faithfulness: number | null;
    answer_relevance: number | null;
    context_recall: number | null;
    context_precision: number | null;
    correctness: number | null;
    reasoning?: string;
  }>;
  message?: string;
};

export type DatasetQualityResult = {
  total_evaluated: number;
  total_dataset_questions?: number;
  avg_latency?: number;
  dataset_path?: string;
  drift_summary?: DriftSummary | null;
  quality_summary: QualitySummary | null;
  individual_results: Array<{
    query: string;
    faithfulness: number | null;
    answer_relevance: number | null;
    context_recall: number | null;
    context_precision: number | null;
    correctness: number | null;
    reasoning?: string;
    latency?: number;
    docs_retrieved?: number;
    drift_score?: number | null;
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
  drift_summary?: DriftSummary | null;
  quality_summary?: QualitySummary | null;
  delta?: {
    avg_faithfulness?: number | null;
    avg_answer_relevance?: number | null;
    avg_context_recall?: number | null;
    avg_context_precision?: number | null;
    avg_correctness?: number | null;
    avg_drift_score?: number | null;
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
    faithfulness: number | null;
    answer_relevance: number | null;
    context_recall: number | null;
    context_precision: number | null;
    correctness: number | null;
    latency?: number;
    drift_score?: number | null;
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
  relevance_score: number | null;
  docs_retrieved: number;
  response_words: number;
  mode: string;
  quality_scores?: {
    faithfulness: number | null;
    answer_relevance: number | null;
    context_recall: number | null;
    correctness: number | null;
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

function normalizeEvaluationLogSummary(summary?: EvaluationLogSummary | null): EvaluationLogSummary {
  return {
    total_queries_analyzed: toFiniteNumberOrNull(summary?.total_queries_analyzed) ?? 0,
    avg_retrieval_time_seconds: toFiniteNumberOrNull(summary?.avg_retrieval_time_seconds) ?? 0,
    avg_generation_time_seconds: toFiniteNumberOrNull(summary?.avg_generation_time_seconds) ?? 0,
    avg_total_time_seconds: toFiniteNumberOrNull(summary?.avg_total_time_seconds) ?? 0,
    avg_num_retrieved: toFiniteNumberOrNull(summary?.avg_num_retrieved) ?? 0,
    avg_relevance_score: toFiniteNumberOrNull(summary?.avg_relevance_score) ?? 0,
    error: summary?.error,
  };
}

function normalizeMetricsHistory(history?: MetricsHistory | null): MetricsHistory {
  return {
    status: history?.status ?? "no_data",
    message: history?.message,
    hours: toFiniteNumberOrNull(history?.hours) ?? undefined,
    granularity: history?.granularity,
    total_queries: toFiniteNumberOrNull(history?.total_queries) ?? undefined,
    data_points: (history?.data_points ?? []).map((point) => ({
      timestamp: point.timestamp ?? "",
      query_count: toFiniteNumber(point.query_count),
      avg_latency: toFiniteNumber(point.avg_latency),
      avg_retrieval_latency: toFiniteNumber(point.avg_retrieval_latency),
      avg_generation_latency: toFiniteNumber(point.avg_generation_latency),
      avg_relevance: toFiniteNumber(point.avg_relevance),
      avg_docs_retrieved: toFiniteNumber(point.avg_docs_retrieved),
    })),
  };
}

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

export async function putJSON<T>({
  path,
  body,
  token,
}: {
  path: string;
  body: unknown;
  token?: string;
}) {
  return request<T>(path, {
    method: "PUT",
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

export async function listChatSessions(token: string, courseId?: string): Promise<ChatSessionDTO[]> {
  const data = await getJSON<{ sessions: ChatSessionDTO[] }>({
    path: courseId ? `/chat/sessions?course_id=${encodeURIComponent(courseId)}` : "/chat/sessions",
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
  courseId,
}: {
  token: string;
  title?: string;
  courseId?: string;
}): Promise<ChatSessionDTO> {
  const params = new URLSearchParams();
  if (title) params.set("title", title);
  if (courseId) params.set("course_id", courseId);
  const query = params.size ? `?${params.toString()}` : "";
  const data = await postJSON<{ session: ChatSessionDTO }>({
    path: `/chat/sessions${query}`,
    body: {},
    token,
  });
  return data.session;
}

export async function fetchQuizFolders(token: string, courseId?: string): Promise<QuizFolder[]> {
  const data = await getJSON<{ folders: QuizFolder[] }>({
    path: courseId ? `/quiz/folders?course_id=${encodeURIComponent(courseId)}` : "/quiz/folders",
    token,
  });
  return data.folders || [];
}

export async function generateQuiz({
  token,
  folders,
  numQuestions,
  courseId,
  objectiveIds,
  difficulty,
}: {
  token: string;
  folders: string[];
  numQuestions: number;
  courseId?: string;
  objectiveIds?: string[];
  difficulty?: "easy" | "medium" | "hard";
}) {
  return postJSON<{
    quiz_id: string;
    selected_folders: string[];
    questions: QuizQuestion[];
    generated_at: string;
  }>({
    path: "/quiz/generate",
    body: { folders, num_questions: numQuestions, course_id: courseId, objective_ids: objectiveIds, difficulty },
    token,
  });
}

export async function fetchCourses(token: string): Promise<Course[]> {
  const data = await getJSON<{ courses: Course[] }>({ path: "/courses", token });
  return data.courses ?? [];
}

export async function fetchCourseCatalog(token: string): Promise<CourseCatalogEntry[]> {
  const data = await getJSON<{ courses: CourseCatalogEntry[] }>({ path: "/courses/catalog", token });
  return data.courses ?? [];
}

export async function enrollInCourse(token: string, courseId: string): Promise<void> {
  await postJSON({ path: `/courses/${encodeURIComponent(courseId)}/enroll`, token, body: {} });
}

export async function createCourse(token: string, payload: {
  id?: string;
  code: string;
  title: string;
  description?: string;
  open_enrollment?: boolean;
  resource_prefixes?: string[];
  modules?: Array<{ id: string; title: string; resource_prefixes?: string[]; objectives: Array<{ id: string; title: string; module_id: string }> }>;
}): Promise<Course> {
  const data = await postJSON<{ course: Course }>({ path: "/courses", token, body: payload });
  return data.course;
}

export async function fetchCourseMemberships(token: string, courseId: string): Promise<CourseMembership[]> {
  const data = await getJSON<{ memberships: CourseMembership[] }>({ path: `/courses/${encodeURIComponent(courseId)}/memberships`, token });
  return data.memberships ?? [];
}

export async function saveCourseMembership(token: string, courseId: string, username: string, role: "student" | "instructor"): Promise<CourseMembership> {
  const data = await putJSON<{ membership: CourseMembership }>({ path: `/courses/${encodeURIComponent(courseId)}/memberships`, token, body: { username, role } });
  return data.membership;
}

export async function removeCourseMembership(token: string, courseId: string, username: string): Promise<void> {
  await deleteJSON<{ success: boolean }>({ path: `/courses/${encodeURIComponent(courseId)}/memberships/${encodeURIComponent(username)}`, token });
}

export async function fetchCourseIngestionStatus(token: string, courseId: string): Promise<CourseIngestionStatus> {
  return getJSON<CourseIngestionStatus>({ path: `/courses/${encodeURIComponent(courseId)}/content-ingestion`, token });
}

export async function reindexCourseResource(token: string, courseId: string, resourceId: string): Promise<void> {
  await postJSON({ path: `/courses/${encodeURIComponent(courseId)}/resources/${encodeURIComponent(resourceId)}/reindex`, token, body: {} });
}

export async function fetchObjectiveCoverage(token: string, courseId: string): Promise<ObjectiveCoverage> {
  return getJSON<ObjectiveCoverage>({ path: `/courses/${encodeURIComponent(courseId)}/objective-coverage`, token });
}

export async function fetchInstructorSummary(token: string, courseId: string): Promise<InstructorSummary> {
  return getJSON<InstructorSummary>({ path: `/courses/${encodeURIComponent(courseId)}/instructor-summary`, token });
}

export async function fetchCourseEvaluationCases(token: string, courseId: string): Promise<EvaluationCase[]> {
  const data = await getJSON<{ cases: EvaluationCase[] }>({ path: `/courses/${encodeURIComponent(courseId)}/evaluation/cases`, token });
  return data.cases ?? [];
}

export async function createCourseEvaluationCase(token: string, courseId: string, payload: Omit<EvaluationCase, "id"> & { objective_ids?: string[] }): Promise<EvaluationCase> {
  const data = await postJSON<{ case: EvaluationCase }>({ path: `/courses/${encodeURIComponent(courseId)}/evaluation/cases`, token, body: payload });
  return data.case;
}

export async function runCourseEvaluationSuite(token: string, courseId: string): Promise<EvaluationRunResponse> {
  return postJSON<EvaluationRunResponse>({ path: `/courses/${encodeURIComponent(courseId)}/evaluation/run`, token, body: {}, timeoutMs: 120000 });
}

export async function uploadCourseResource(token: string, courseId: string, file: File): Promise<Resource> {
  const form = new FormData();
  form.append("file", file);
  form.append("title", file.name);
  const response = await fetch(`${getApiBaseUrl()}/courses/${encodeURIComponent(courseId)}/resources/upload`, {
    method: "POST",
    body: form,
    credentials: "include",
    headers: token && token !== "authenticated" ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) throw await parseRequestError(response);
  return ((await response.json()) as { resource: Resource }).resource;
}

export async function fetchLearningDashboard(token: string, courseId?: string): Promise<LearningDashboard> {
  const query = courseId ? `?course_id=${encodeURIComponent(courseId)}` : "";
  return getJSON<LearningDashboard>({ path: `/learning/dashboard${query}`, token });
}

export async function fetchStudyRecommendation(token: string, courseId: string): Promise<StudyRecommendation | null> {
  const data = await getJSON<{ recommendation: StudyRecommendation | null }>({
    path: `/learning/recommendation?course_id=${encodeURIComponent(courseId)}`,
    token,
  });
  return data.recommendation;
}

export async function saveObjectiveConfidence(token: string, payload: { course_id: string; objective_id: string; confidence: number }) {
  return postJSON<{ confidence: { confidence: number } }>({ path: "/learning/confidence", token, body: payload });
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

export async function fetchQuizHistory(token: string, courseId?: string) {
  return getJSON<{ results: QuizHistoryEntry[] }>({
    path: courseId ? `/quiz/history?course_id=${encodeURIComponent(courseId)}` : "/quiz/history",
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
  course_id?: string | null;
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
  data: { category: string; title: string; url: string; description?: string; order?: number; course_id?: string }
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
  courseId,
}: {
  token: string;
  file: File;
  category: string;
  title: string;
  description?: string;
  order?: number;
  courseId?: string;
}): Promise<Resource> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("category", category);
  formData.append("title", title);
  if (description) formData.append("description", description);
  if (order !== undefined) formData.append("order", String(order));
  if (courseId) formData.append("course_id", courseId);

  let lastError: Error | null = null;

  const uploadHeaders: Record<string, string> = {};
  if (token && token !== "authenticated") {
    uploadHeaders.Authorization = `Bearer ${token}`;
  }
  // CSRF for direct-backend fallback (proxy adds it on its own; see adminRequest).
  const csrfToken = readCsrfTokenCookie();
  if (csrfToken) {
    uploadHeaders["X-CSRF-Token"] = csrfToken;
  }
  // Do NOT set Content-Type for multipart/form-data — the browser must
  // generate the boundary parameter or the backend will fail to parse.

  for (const url of getAdminRequestTargets("/admin/resources/upload")) {
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: uploadHeaders,
        body: formData,
        credentials: "include",
      });

      if (!response.ok) {
        lastError = await parseRequestError(response);
        continue;
      }

      const data = (await response.json()) as { resource: Resource };
      return data.resource;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error("Upload failed");
    }
  }

  throw lastError ?? new Error("Upload failed");
}

export async function updateResource(
  token: string,
  resourceId: string,
  data: Partial<{ category: string; title: string; url: string; description: string; order: number; active: boolean; course_id: string }>
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

  const result = await postJSON<BatchQualityResult>({
    path: "/evaluation/batch-quality",
    body,
    token,
    timeoutMs: 300000, // 5 min — LLM calls can be slow for large batches
  });
  return normalizeBatchQualityResult(result);
}

export async function runDatasetQuality(
  token: string,
  limit: number = 10,
  modelId?: string
): Promise<DatasetQualityResult> {
  const body: Record<string, unknown> = { limit };
  if (modelId) body.model_id = modelId;

  const result = await postJSON<DatasetQualityResult>({
    path: "/evaluation/run-dataset-quality",
    body,
    token,
    timeoutMs: 600000, // 10 min — runs each question through full pipeline
  });
  return normalizeDatasetQualityResult(result);
}

export async function fetchEvaluationLogSummary(token: string): Promise<EvaluationLogSummary> {
  const data = await getJSON<{ summary: EvaluationLogSummary }>({
    path: "/evaluation/summary",
    token,
  });
  return normalizeEvaluationLogSummary(data.summary);
}

export async function fetchEvaluationRuns(
  token: string,
  limit: number = 10
): Promise<EvaluationRunRecord[]> {
  const data = await getJSON<{ runs: EvaluationRunRecord[] }>({
    path: `/evaluation/runs?limit=${limit}`,
    token,
  });
  return (data.runs ?? []).map(normalizeEvaluationRunRecord);
}

export async function fetchRealtimeRAGMetrics(token: string, lastN?: number): Promise<RealtimeRAGMetrics> {
  const query = lastN ? `?last_n=${lastN}` : "";
  const data = await getJSON<{ realtime_metrics: RealtimeRAGMetrics }>({
    path: `/evaluation/realtime-metrics${query}`,
    token,
  });
  return normalizeRealtimeRAGMetrics(data.realtime_metrics);
}

function toFiniteNumberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function toFiniteNumber(value: unknown, fallback: number = 0): number {
  return toFiniteNumberOrNull(value) ?? fallback;
}

function normalizeQualitySummary(summary: QualitySummary | null | undefined): QualitySummary | null {
  if (!summary) return null;
  return {
    avg_faithfulness: toFiniteNumber(summary.avg_faithfulness),
    avg_answer_relevance: toFiniteNumber(summary.avg_answer_relevance),
    avg_context_recall: toFiniteNumber(summary.avg_context_recall),
    avg_context_precision: toFiniteNumber(summary.avg_context_precision),
    avg_correctness: toFiniteNumber(summary.avg_correctness),
    evaluated_count: toFiniteNumber(summary.evaluated_count),
  };
}

function normalizeDriftSummary(summary: DriftSummary | null | undefined): DriftSummary | null {
  if (!summary) return null;
  return {
    enabled: Boolean(summary.enabled),
    baseline_path: summary.baseline_path ?? "",
    scored_count: toFiniteNumber(summary.scored_count),
    avg_drift_score: toFiniteNumberOrNull(summary.avg_drift_score),
    max_drift_score: toFiniteNumberOrNull(summary.max_drift_score),
    high_drift_threshold: toFiniteNumber(summary.high_drift_threshold, 2),
    high_drift_count: toFiniteNumber(summary.high_drift_count),
    high_drift_percentage: toFiniteNumber(summary.high_drift_percentage),
  };
}

function normalizeBatchQualityResult(result: BatchQualityResult): BatchQualityResult {
  return {
    ...result,
    total_evaluated: toFiniteNumber(result.total_evaluated),
    quality_summary: normalizeQualitySummary(result.quality_summary),
    individual_results: (result.individual_results ?? []).map((item) => ({
      ...item,
      faithfulness: toFiniteNumberOrNull(item.faithfulness),
      answer_relevance: toFiniteNumberOrNull(item.answer_relevance),
      context_recall: toFiniteNumberOrNull(item.context_recall),
      context_precision: toFiniteNumberOrNull(item.context_precision),
      correctness: toFiniteNumberOrNull(item.correctness),
    })),
  };
}

function normalizeDatasetQualityResult(result: DatasetQualityResult): DatasetQualityResult {
  return {
    ...normalizeBatchQualityResult(result),
    total_dataset_questions: toFiniteNumberOrNull(result.total_dataset_questions) ?? undefined,
    avg_latency: toFiniteNumberOrNull(result.avg_latency) ?? undefined,
    dataset_path: result.dataset_path ?? undefined,
    drift_summary: normalizeDriftSummary(result.drift_summary),
    individual_results: (result.individual_results ?? []).map((item) => ({
      ...item,
      faithfulness: toFiniteNumberOrNull(item.faithfulness),
      answer_relevance: toFiniteNumberOrNull(item.answer_relevance),
      context_recall: toFiniteNumberOrNull(item.context_recall),
      context_precision: toFiniteNumberOrNull(item.context_precision),
      correctness: toFiniteNumberOrNull(item.correctness),
      latency: toFiniteNumberOrNull(item.latency) ?? undefined,
      docs_retrieved: toFiniteNumberOrNull(item.docs_retrieved) ?? undefined,
      drift_score: toFiniteNumberOrNull(item.drift_score) ?? undefined,
      avg_retrieval_score: toFiniteNumberOrNull(item.avg_retrieval_score) ?? undefined,
    })),
  };
}

function normalizeEvaluationRunRecord(run: EvaluationRunRecord): EvaluationRunRecord {
  return {
    ...run,
    summary: {
      ...run.summary,
      total_evaluated: toFiniteNumberOrNull(run.summary?.total_evaluated) ?? undefined,
      total_dataset_questions: toFiniteNumberOrNull(run.summary?.total_dataset_questions) ?? undefined,
      avg_latency: toFiniteNumberOrNull(run.summary?.avg_latency) ?? undefined,
      drift_summary: normalizeDriftSummary(run.summary?.drift_summary ?? null),
      quality_summary: normalizeQualitySummary(run.summary?.quality_summary ?? null),
      delta: run.summary?.delta
        ? {
            avg_faithfulness: toFiniteNumberOrNull(run.summary.delta.avg_faithfulness),
            avg_answer_relevance: toFiniteNumberOrNull(run.summary.delta.avg_answer_relevance),
            avg_context_recall: toFiniteNumberOrNull(run.summary.delta.avg_context_recall),
            avg_context_precision: toFiniteNumberOrNull(run.summary.delta.avg_context_precision),
            avg_correctness: toFiniteNumberOrNull(run.summary.delta.avg_correctness),
            avg_drift_score: toFiniteNumberOrNull(run.summary.delta.avg_drift_score),
            avg_latency: toFiniteNumberOrNull(run.summary.delta.avg_latency),
          }
        : undefined,
    },
    sample_results: (run.sample_results ?? []).map((item) => ({
      ...item,
      faithfulness: toFiniteNumberOrNull(item.faithfulness),
      answer_relevance: toFiniteNumberOrNull(item.answer_relevance),
      context_recall: toFiniteNumberOrNull(item.context_recall),
      context_precision: toFiniteNumberOrNull(item.context_precision),
      correctness: toFiniteNumberOrNull(item.correctness),
      latency: toFiniteNumberOrNull(item.latency) ?? undefined,
      drift_score: toFiniteNumberOrNull(item.drift_score) ?? undefined,
    })),
  };
}

function normalizeRealtimeRAGMetrics(metrics: RealtimeRAGMetrics): RealtimeRAGMetrics {
  return {
    ...metrics,
    summary: metrics.summary
      ? {
          total_queries_analyzed: toFiniteNumber(metrics.summary.total_queries_analyzed),
          avg_retrieval_time_seconds: toFiniteNumber(metrics.summary.avg_retrieval_time_seconds),
          avg_generation_time_seconds: toFiniteNumber(metrics.summary.avg_generation_time_seconds),
          avg_total_time_seconds: toFiniteNumber(metrics.summary.avg_total_time_seconds),
          p50_total_time_seconds: toFiniteNumber(metrics.summary.p50_total_time_seconds),
          p95_total_time_seconds: toFiniteNumber(metrics.summary.p95_total_time_seconds),
          p99_total_time_seconds: toFiniteNumber(metrics.summary.p99_total_time_seconds),
          avg_relevance_score: toFiniteNumber(metrics.summary.avg_relevance_score),
          min_relevance_score: toFiniteNumber(metrics.summary.min_relevance_score),
          max_relevance_score: toFiniteNumber(metrics.summary.max_relevance_score),
          avg_docs_retrieved: toFiniteNumber(metrics.summary.avg_docs_retrieved),
          avg_response_length_words: toFiniteNumber(metrics.summary.avg_response_length_words),
        }
      : null,
    performance: metrics.performance
      ? {
          latency_distribution: {
            fast_under_2s: toFiniteNumber(metrics.performance.latency_distribution.fast_under_2s),
            medium_2_to_5s: toFiniteNumber(metrics.performance.latency_distribution.medium_2_to_5s),
            slow_over_5s: toFiniteNumber(metrics.performance.latency_distribution.slow_over_5s),
            fast_percentage: toFiniteNumber(metrics.performance.latency_distribution.fast_percentage),
          },
          relevance_distribution: {
            high_above_0_7: toFiniteNumber(metrics.performance.relevance_distribution.high_above_0_7),
            medium_0_4_to_0_7: toFiniteNumber(metrics.performance.relevance_distribution.medium_0_4_to_0_7),
            low_below_0_4: toFiniteNumber(metrics.performance.relevance_distribution.low_below_0_4),
            high_relevance_percentage: toFiniteNumber(metrics.performance.relevance_distribution.high_relevance_percentage),
          },
        }
      : null,
    quality_summary: normalizeQualitySummary(metrics.quality_summary),
    recent_queries: (metrics.recent_queries ?? []).map((query) => ({
      ...query,
      retrieval_time: toFiniteNumber(query.retrieval_time),
      generation_time: toFiniteNumber(query.generation_time),
      total_time: toFiniteNumber(query.total_time),
      relevance_score: toFiniteNumberOrNull(query.relevance_score),
      docs_retrieved: toFiniteNumber(query.docs_retrieved),
      response_words: toFiniteNumber(query.response_words),
      quality_scores: query.quality_scores
        ? {
            faithfulness: toFiniteNumberOrNull(query.quality_scores.faithfulness),
            answer_relevance: toFiniteNumberOrNull(query.quality_scores.answer_relevance),
            context_recall: toFiniteNumberOrNull(query.quality_scores.context_recall),
            correctness: toFiniteNumberOrNull(query.quality_scores.correctness),
          }
        : undefined,
    })),
  };
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
  return normalizeMetricsHistory(data.history);
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
          pricing: {
            input_per_1k?: number | null;
            output_per_1k?: number | null;
            source?: string;
          };
        };
        embedding: {
          model_id: string;
          pricing: { input_per_1k?: number | null; source?: string };
          dimension?: number | null;
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
      pricing?: {
        storage_per_gb_month?: number | null;
        get_per_1k?: number | null;
        put_per_1k?: number | null;
        source?: string;
      };
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
      pricing?: {
        read_per_million?: number | null;
        write_per_million?: number | null;
        storage_per_gb_month?: number | null;
        source?: string;
      };
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
      bedrock_invocations?: number | null;
      bedrock_input_tokens?: number | null;
      bedrock_output_tokens?: number | null;
      bedrock_invocation_latency_ms?: number | null;
      note?: string;
    };
  };
  costs: {
    daily: {
      date: string;
      total_cost_usd?: number | null;
      total_tokens?: number | null;
      entries?: number | null;
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

export async function trackChatShareAction({
  token,
  sessionId,
  channel,
  shareId,
}: {
  token: string;
  sessionId: string;
  channel: "copy_link" | "x" | "linkedin" | "reddit" | "whatsapp" | "email" | "native_share";
  shareId?: string | null;
}): Promise<{ success: boolean }> {
  return postJSON<{ success: boolean }>({
    path: `/chat/sessions/${sessionId}/share-events`,
    body: { channel, share_id: shareId ?? undefined },
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
  courseId,
}: {
  token: string;
  sessionId: string;
  messageIndex: number;
  feedbackType: MessageFeedbackType;
  reason?: string;
  courseId?: string;
}): Promise<MessageFeedbackResponse> {
  return postJSON<MessageFeedbackResponse>({
    path: `/chat/sessions/${sessionId}/messages/${messageIndex}/feedback`,
    body: { type: feedbackType, reason, course_id: courseId },
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
  total_message_likes: number;
  total_message_dislikes: number;
  total_message_reports: number;
  total_chat_shares: number;
  active_announcements: number;
  admin_users: number;
  pending_appointments: number;
  storage_readiness: {
    ready: boolean;
    environment: string;
    user_data_root: string;
    path_exists: boolean;
    shared_storage_configured: boolean;
    path_looks_persistent: boolean;
    path_is_mount?: boolean;
    warning?: string | null;
  };
  error?: string;
};

export type AdminUser = {
  username: string;
  email: string;
  role: string;
  display_name?: string;
  last_login?: string;
  created_at?: string;
};

export type AdminAppointmentEntry = AppointmentRecord & {
  user_id: string;
};

function normalizeAdminStats(stats?: Partial<AdminStats> | null): AdminStats {
  return {
    total_users: toFiniteNumber(stats?.total_users),
    total_queries: toFiniteNumber(stats?.total_queries),
    total_feedback: toFiniteNumber(stats?.total_feedback),
    new_feedback: toFiniteNumber(stats?.new_feedback),
    total_message_likes: toFiniteNumber(stats?.total_message_likes),
    total_message_dislikes: toFiniteNumber(stats?.total_message_dislikes),
    total_message_reports: toFiniteNumber(stats?.total_message_reports),
    total_chat_shares: toFiniteNumber(stats?.total_chat_shares),
    active_announcements: toFiniteNumber(stats?.active_announcements),
    admin_users: toFiniteNumber(stats?.admin_users),
    pending_appointments: toFiniteNumber(stats?.pending_appointments),
    storage_readiness: {
      ready: Boolean(stats?.storage_readiness?.ready),
      environment:
        typeof stats?.storage_readiness?.environment === "string"
          ? stats.storage_readiness.environment
          : "",
      user_data_root:
        typeof stats?.storage_readiness?.user_data_root === "string"
          ? stats.storage_readiness.user_data_root
          : "",
      path_exists: Boolean(stats?.storage_readiness?.path_exists),
      shared_storage_configured: Boolean(
        stats?.storage_readiness?.shared_storage_configured
      ),
      path_looks_persistent: Boolean(
        stats?.storage_readiness?.path_looks_persistent
      ),
      path_is_mount: Boolean(stats?.storage_readiness?.path_is_mount),
      warning:
        typeof stats?.storage_readiness?.warning === "string"
          ? stats.storage_readiness.warning
          : undefined,
    },
    error: stats?.error,
  };
}

function normalizeAdminUser(user?: Partial<AdminUser> | null): AdminUser {
  const email = typeof user?.email === "string" ? user.email : "";
  const username =
    typeof user?.username === "string" && user.username.trim()
      ? user.username
      : email || "Unknown user";

  return {
    username,
    email,
    role: typeof user?.role === "string" && user.role.trim() ? user.role : "User",
    display_name: typeof user?.display_name === "string" ? user.display_name : undefined,
    last_login: typeof user?.last_login === "string" ? user.last_login : undefined,
    created_at: typeof user?.created_at === "string" ? user.created_at : undefined,
  };
}

function normalizeAppointmentRecord(
  appointment?: Partial<AppointmentRecord & { user_id?: string }> | null
): AdminAppointmentEntry {
  return {
    id: typeof appointment?.id === "string" ? appointment.id : "",
    user_id: typeof appointment?.user_id === "string" ? appointment.user_id : "",
    user_name: typeof appointment?.user_name === "string" ? appointment.user_name : "",
    user_email: typeof appointment?.user_email === "string" ? appointment.user_email : "",
    appointment_with:
      typeof appointment?.appointment_with === "string"
        ? appointment.appointment_with
        : "",
    preferred_date:
      typeof appointment?.preferred_date === "string"
        ? appointment.preferred_date
        : "",
    preferred_time:
      typeof appointment?.preferred_time === "string"
        ? appointment.preferred_time
        : "",
    primary_reason:
      typeof appointment?.primary_reason === "string"
        ? appointment.primary_reason
        : "",
    additional_details:
      typeof appointment?.additional_details === "string"
        ? appointment.additional_details
        : "",
    status: typeof appointment?.status === "string" ? appointment.status : "pending",
    requested_at:
      typeof appointment?.requested_at === "string" ? appointment.requested_at : "",
  };
}

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
  type: "feedback" | "bug" | "report";
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
  // message report fields
  reason?: string;
  session_id?: string;
  message_index?: number;
  course_id?: string | null;
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
    popular_topics: Array.isArray(metrics?.popular_topics)
      ? metrics.popular_topics.map((topic) => ({
          folder: typeof topic?.folder === "string" ? topic.folder : "Unknown",
          quiz_count: toFiniteNumber(topic?.quiz_count),
        }))
      : [],
    recent_activity: Array.isArray(metrics?.recent_activity)
      ? metrics.recent_activity.map((entry) => ({
          date: typeof entry?.date === "string" ? entry.date : "",
          count: toFiniteNumber(entry?.count),
          avg_score: toFiniteNumber(entry?.avg_score),
        }))
      : [],
    top_performers: Array.isArray(metrics?.top_performers)
      ? metrics.top_performers.map((performer) => ({
          username: typeof performer?.username === "string" ? performer.username : "Unknown",
          quizzes_taken: toFiniteNumber(performer?.quizzes_taken),
          avg_score: toFiniteNumber(performer?.avg_score),
        }))
      : [],
    error: metrics?.error,
  };
}

// ==================== ADMIN API FUNCTIONS ====================

export async function fetchAdminStats(token: string): Promise<AdminStats> {
  const data = await adminRequest<{ stats: AdminStats }>("/admin/stats", { authToken: token });
  return normalizeAdminStats(data.stats);
}

export async function fetchQuizMetrics(token: string): Promise<QuizMetrics> {
  const data = await adminRequest<{ quiz_metrics: QuizMetrics }>("/admin/quiz-metrics", { authToken: token });
  return normalizeQuizMetrics(data.quiz_metrics);
}

export async function fetchAdminUsers(token: string): Promise<AdminUser[]> {
  const data = await adminRequest<{ users: AdminUser[] }>("/admin/users", { authToken: token });
  return (data.users ?? []).map(normalizeAdminUser);
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
  limit?: number,
  courseId?: string
): Promise<{ feedback: AdminFeedbackEntry[]; total: number }> {
  const params = new URLSearchParams();
  if (feedbackType) params.set("feedback_type", feedbackType);
  if (limit) params.set("limit", String(limit));
  if (courseId) params.set("course_id", courseId);
  const query = params.toString() ? `?${params.toString()}` : "";
  return adminRequest<{ feedback: AdminFeedbackEntry[]; total: number }>(`/admin/feedback${query}`, { authToken: token });
}

export async function fetchAdminAppointments(
  token: string,
  appointmentStatus?: string,
  limit?: number
): Promise<{ appointments: AdminAppointmentEntry[]; total: number }> {
  const params = new URLSearchParams();
  if (appointmentStatus) params.set("status", appointmentStatus);
  if (limit) params.set("limit", String(limit));
  const query = params.toString() ? `?${params.toString()}` : "";
  const data = await adminRequest<{ appointments: AdminAppointmentEntry[]; total: number }>(
    `/admin/appointments${query}`,
    { authToken: token }
  );
  return {
    appointments: Array.isArray(data.appointments)
      ? data.appointments.map(normalizeAppointmentRecord)
      : [],
    total: toFiniteNumber(data.total),
  };
}

export async function updateAdminAppointmentStatus(
  token: string,
  appointmentId: string,
  newStatus: string
): Promise<{ success: boolean; appointment: AdminAppointmentEntry }> {
  const data = await adminRequest<{ success: boolean; appointment: AdminAppointmentEntry }>(
    `/admin/appointments/${encodeURIComponent(appointmentId)}`,
    {
      method: "PUT",
      body: JSON.stringify({ status: newStatus }),
      authToken: token,
    }
  );
  return {
    success: Boolean(data.success),
    appointment: normalizeAppointmentRecord(data.appointment),
  };
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
    agent_distribution: Object.fromEntries(
      Object.entries(metrics?.agent_distribution ?? {}).map(([agent, count]) => [agent, toFiniteNumber(count)])
    ),
    avg_response_time_ms: Number(metrics?.avg_response_time_ms ?? 0),
    response_time_by_agent: Object.fromEntries(
      Object.entries(metrics?.response_time_by_agent ?? {}).map(([agent, value]) => [agent, toFiniteNumber(value)])
    ),
    daily_usage: Array.isArray(metrics?.daily_usage)
      ? metrics.daily_usage.map((entry) => ({
          date: entry?.date ?? "",
          count: toFiniteNumber(entry?.count),
          unique_users: toFiniteNumber(entry?.unique_users),
        }))
      : [],
    top_query_types: Array.isArray(metrics?.top_query_types)
      ? metrics.top_query_types.map((entry) => ({
          type: entry?.type ?? "unknown",
          count: toFiniteNumber(entry?.count),
        }))
      : [],
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
    nodes_by_type: Object.fromEntries(
      Object.entries(metrics?.nodes_by_type ?? {}).map(([type, count]) => [type, toFiniteNumber(count)])
    ),
    relationships_by_type: Object.fromEntries(
      Object.entries(metrics?.relationships_by_type ?? {}).map(([type, count]) => [type, toFiniteNumber(count)])
    ),
    most_struggled_concepts: Array.isArray(metrics?.most_struggled_concepts)
      ? metrics.most_struggled_concepts.map((item) => ({
          concept: item?.concept ?? "Unknown",
          students: toFiniteNumber(item?.students),
        }))
      : [],
    most_studied_topics: Array.isArray(metrics?.most_studied_topics)
      ? metrics.most_studied_topics.map((item) => ({
          topic: item?.topic ?? "Unknown",
          study_count: toFiniteNumber(item?.study_count),
        }))
      : [],
    student_engagement: Array.isArray(metrics?.student_engagement)
      ? metrics.student_engagement.map((item) => ({
          username: item?.username ?? "Unknown",
          queries: toFiniteNumber(item?.queries),
          sessions: toFiniteNumber(item?.sessions),
          doubts: toFiniteNumber(item?.doubts),
        }))
      : [],
    feedback_sentiment_overview: Object.fromEntries(
      Object.entries(metrics?.feedback_sentiment_overview ?? {}).map(([sentiment, count]) => [sentiment, toFiniteNumber(count)])
    ),
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
