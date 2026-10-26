"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  clearEvaluationLogs,
  EvaluationAnalysis,
  EvaluationCase,
  EvaluationLogSummary,
  EvaluationResult,
  fetchEvaluationCases,
  fetchEvaluationLogSummary,
  runEvaluationSuite,
  getApiBaseUrl,
  fetchAWSMetrics,
  AWSMetrics,
  fetchRealtimeRAGMetrics,
  RealtimeRAGMetrics,
  fetchMetricsHistory,
  MetricsHistory,
  getMetricsExportUrl,
  runBatchQuality,
  BatchQualityResult,
  QualitySummary,
  fetchEvaluationRuns,
  EvaluationRunRecord,
  fetchQuizMetrics,
  QuizMetrics,
  fetchAgentMetrics,
  AgentMetrics,
  fetchKnowledgeGraphMetrics,
  KnowledgeGraphMetrics,
  runDatasetQuality,
  DatasetQualityResult,
} from "@/lib/api";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useAuthToken } from "@/hooks/useAuthToken";
import { useUser } from "@/hooks/useUser";
import { PageShell } from "@/components/page-shell";
import {
  BarChart3, Play, RotateCcw, Filter, Clock, Target, Brain, Trash2,
  Zap, Database, Server, Activity, TrendingUp, AlertTriangle, CheckCircle,
  Cpu, HardDrive, Gauge, RefreshCw, Cloud, Box, Key, DollarSign,
  FileText, Layers, Shield, Info, Download, Calendar, ShieldAlert,
  Lock, GitBranch, Users
} from "lucide-react";

// Recharts tooltips follow the theme: surface card, 1px border, theme text.
const CHART_TOOLTIP_STYLE = {
  backgroundColor: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  borderRadius: "12px",
  color: "var(--color-text)",
};

// Types for metrics
interface PrometheusMetric {
  name: string;
  value: number;
  labels?: Record<string, string>;
}

interface WebsiteMetrics {
  totalRequests: number;
  avgResponseTime: number;
  errorRate: number;
  activeConnections: number;
  cacheHitRate: number;
  ragQueriesTotal: number;
  ragAvgLatency: number;
  embeddingRequests: number;
  tokensProcessed: number;
  totalCost: number;
}

export function EvaluationContent() {
  const { token } = useAuthToken();
  const [cases, setCases] = useState<EvaluationCase[]>([]);
  const [analysis, setAnalysis] = useState<EvaluationAnalysis | null>(null);
  const [results, setResults] = useState<EvaluationResult[]>([]);
  const [logSummary, setLogSummary] = useState<EvaluationLogSummary | null>(null);
  const [evaluationRuns, setEvaluationRuns] = useState<EvaluationRunRecord[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [runLimit, setRunLimit] = useState(5);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedDifficulties, setSelectedDifficulties] = useState<string[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logMessage, setLogMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"rag" | "website" | "aws" | "tests" | "quiz" | "agents" | "graph">("rag");
  const [quizMetrics, setQuizMetrics] = useState<QuizMetrics | null>(null);
  const [quizMetricsLoading, setQuizMetricsLoading] = useState(false);
  const [agentMetrics, setAgentMetrics] = useState<AgentMetrics | null>(null);
  const [agentMetricsLoading, setAgentMetricsLoading] = useState(false);
  const [graphMetrics, setGraphMetrics] = useState<KnowledgeGraphMetrics | null>(null);
  const [graphMetricsLoading, setGraphMetricsLoading] = useState(false);
  const [websiteMetrics, setWebsiteMetrics] = useState<WebsiteMetrics | null>(null);
  const [websiteMetricsError, setWebsiteMetricsError] = useState<string | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [awsMetrics, setAwsMetrics] = useState<AWSMetrics | null>(null);
  const [awsLoading, setAwsLoading] = useState(false);
  const [realtimeMetrics, setRealtimeMetrics] = useState<RealtimeRAGMetrics | null>(null);
  const [realtimeLoading, setRealtimeLoading] = useState(false);
  const [metricsHistory, setMetricsHistory] = useState<MetricsHistory | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyHours, setHistoryHours] = useState(24);
  const [historyGranularity, setHistoryGranularity] = useState<"minute" | "hour" | "day">("hour");
  const [qualityResult, setQualityResult] = useState<BatchQualityResult | null>(null);
  const [qualityLoading, setQualityLoading] = useState(false);
  const [qualityError, setQualityError] = useState<string | null>(null);
  const [datasetResult, setDatasetResult] = useState<DatasetQualityResult | null>(null);
  const [datasetLoading, setDatasetLoading] = useState(false);
  const [datasetError, setDatasetError] = useState<string | null>(null);
  const [datasetLimit, setDatasetLimit] = useState(10);
  const [agentMetricsError, setAgentMetricsError] = useState<string | null>(null);
  const [graphMetricsError, setGraphMetricsError] = useState<string | null>(null);

  // Fetch evaluation data
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    setRunsLoading(true);
    setRunsError(null);
    Promise.all([
      fetchEvaluationCases({ token }),
      fetchEvaluationLogSummary(token),
      fetchEvaluationRuns(token, 10),
    ])
      .then(([casesData, summaryData, runsData]) => {
        if (!cancelled) {
          setCases(casesData);
          setLogSummary(summaryData);
          setEvaluationRuns(runsData);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to load evaluation data");
          setRunsError(err instanceof Error ? err.message : "Unable to load evaluation runs");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          setRunsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  // Fetch Prometheus metrics
  const fetchPrometheusMetrics = async () => {
    setMetricsLoading(true);
    setWebsiteMetricsError(null);
    try {
      const apiBaseUrl = getApiBaseUrl();
      const response = await fetch(`${apiBaseUrl}/metrics`, {
        credentials: "include",
      });
      if (!response.ok) throw new Error("Failed to fetch metrics");
      const text = await response.text();

      // Parse Prometheus text format
      const metrics = parsePrometheusMetrics(text);
      setWebsiteMetrics(metrics);
    } catch (err) {
      console.error("Failed to fetch Prometheus metrics:", err);
      setWebsiteMetrics(null);
      setWebsiteMetricsError(err instanceof Error ? err.message : "Failed to fetch website metrics");
    } finally {
      setMetricsLoading(false);
    }
  };

  // Parse Prometheus text format
  const parsePrometheusMetrics = (text: string): WebsiteMetrics => {
    const lines = text.split("\n");
    const metrics: Record<string, number> = {};

    for (const line of lines) {
      if (line.startsWith("#") || !line.trim()) continue;

      // Parse metric lines like: metric_name{labels} value
      const match = line.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*)\{?[^}]*\}?\s+([0-9.eE+-]+)/);
      if (match) {
        const [, name, value] = match;
        const numValue = parseFloat(value);
        if (!isNaN(numValue)) {
          // Sum up metrics with same name
          metrics[name] = (metrics[name] || 0) + numValue;

          // Track 5xx errors by extracting the status label from http_requests_total lines
          if (name === "http_requests_total") {
            const statusMatch = line.match(/status="([^"]+)"/);
            if (statusMatch && statusMatch[1].startsWith("5")) {
              metrics["http_5xx_total"] = (metrics["http_5xx_total"] || 0) + numValue;
            }
          }
        }
      }
    }

    return {
      totalRequests: metrics["http_requests_total"] || 0,
      avgResponseTime: metrics["http_request_duration_seconds_sum"] / Math.max(1, metrics["http_request_duration_seconds_count"]) || 0,
      errorRate: (metrics["http_5xx_total"] || 0) / Math.max(1, metrics["http_requests_total"]) * 100,
      activeConnections: metrics["http_requests_in_progress"] || 0,
      cacheHitRate: (metrics["rag_cache_hits_total"] || 0) / Math.max(1, (metrics["rag_cache_hits_total"] || 0) + (metrics["rag_cache_misses_total"] || 0)) * 100,
      ragQueriesTotal: metrics["rag_query_total"] || 0,
      ragAvgLatency: metrics["rag_query_duration_seconds_sum"] / Math.max(1, metrics["rag_query_duration_seconds_count"]) || 0,
      embeddingRequests: metrics["rag_embedding_requests_total"] || 0,
      tokensProcessed: metrics["rag_tokens_processed_total"] || 0,
      totalCost: metrics["rag_total_cost_dollars"] || 0,
    };
  };

  // Auto-refresh metrics
  useEffect(() => {
    fetchPrometheusMetrics();
    const interval = setInterval(fetchPrometheusMetrics, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  // Fetch AWS metrics
  const fetchAWSMetricsData = async () => {
    if (!token) return;
    setAwsLoading(true);
    try {
      const data = await fetchAWSMetrics(token);
      setAwsMetrics(data);
    } catch (err) {
      console.error("Failed to fetch AWS metrics:", err);
    } finally {
      setAwsLoading(false);
    }
  };

  useEffect(() => {
    if (token && activeTab === "aws") {
      fetchAWSMetricsData();
    }
  }, [token, activeTab]);

  // Fetch quiz metrics
  const fetchQuizMetricsData = async () => {
    if (!token) return;
    setQuizMetricsLoading(true);
    try {
      const data = await fetchQuizMetrics(token);
      setQuizMetrics(data);
    } catch (err) {
      console.error("Failed to fetch quiz metrics:", err);
      setQuizMetrics({ error: err instanceof Error ? err.message : "Failed to load quiz metrics" } as QuizMetrics);
    } finally {
      setQuizMetricsLoading(false);
    }
  };

  useEffect(() => {
    if (token && activeTab === "quiz") {
      fetchQuizMetricsData();
    }
  }, [token, activeTab]);

  // Fetch agent metrics
  const fetchAgentMetricsData = async () => {
    if (!token) return;
    setAgentMetricsLoading(true);
    setAgentMetricsError(null);
    try {
      const data = await fetchAgentMetrics(token);
      setAgentMetrics(data);
      setAgentMetricsError(data.error ?? null);
    } catch (err) {
      console.error("Failed to fetch agent metrics:", err);
      setAgentMetrics(null);
      setAgentMetricsError(err instanceof Error ? err.message : "Failed to load agent metrics");
    } finally {
      setAgentMetricsLoading(false);
    }
  };

  useEffect(() => {
    if (token && activeTab === "agents") {
      fetchAgentMetricsData();
    }
  }, [token, activeTab]);

  // Fetch knowledge graph metrics
  const fetchGraphMetricsData = async () => {
    if (!token) return;
    setGraphMetricsLoading(true);
    setGraphMetricsError(null);
    try {
      const data = await fetchKnowledgeGraphMetrics(token);
      setGraphMetrics(data);
      setGraphMetricsError(data.error ?? null);
    } catch (err) {
      console.error("Failed to fetch knowledge graph metrics:", err);
      setGraphMetrics(null);
      setGraphMetricsError(err instanceof Error ? err.message : "Failed to load knowledge graph metrics");
    } finally {
      setGraphMetricsLoading(false);
    }
  };

  useEffect(() => {
    if (token && activeTab === "graph") {
      fetchGraphMetricsData();
    }
  }, [token, activeTab]);

  // Fetch real-time RAG metrics
  const fetchRealtimeMetricsData = async () => {
    if (!token) return;
    setRealtimeLoading(true);
    try {
      const data = await fetchRealtimeRAGMetrics(token, 100);
      setRealtimeMetrics(data);
    } catch (err) {
      console.error("Failed to fetch real-time RAG metrics:", err);
    } finally {
      setRealtimeLoading(false);
    }
  };

  // Run dataset quality evaluation (manual trigger — runs full pipeline)
  const handleRunDatasetQuality = async () => {
    if (!token) return;
    setDatasetLoading(true);
    setDatasetError(null);
    try {
      const result = await runDatasetQuality(token, datasetLimit);
      setDatasetResult(result);
    } catch (err) {
      setDatasetError(err instanceof Error ? err.message : "Dataset evaluation failed");
    } finally {
      setDatasetLoading(false);
    }
  };

  useEffect(() => {
    if (token && activeTab === "rag") {
      fetchRealtimeMetricsData();
      fetchHistoryData();
    }
  }, [token, activeTab]);

  // Fetch metrics history for charts
  const fetchHistoryData = async () => {
    if (!token) return;
    setHistoryLoading(true);
    try {
      const data = await fetchMetricsHistory(token, historyHours, historyGranularity);
      setMetricsHistory(data);
    } catch (err) {
      console.error("Failed to fetch metrics history:", err);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (token && activeTab === "rag" && (historyHours || historyGranularity)) {
      fetchHistoryData();
    }
  }, [historyHours, historyGranularity]);

  // Export handlers
  const handleExport = (format: "json" | "csv") => {
    const url = getMetricsExportUrl(format);
    window.open(url, "_blank");
  };

  const handleExportAWS = () => {
    if (!awsMetrics) return;
    const dataStr = JSON.stringify(awsMetrics, null, 2);
    const blob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `aws_metrics_${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportWebsite = () => {
    if (!websiteMetrics) return;
    const dataStr = JSON.stringify(websiteMetrics, null, 2);
    const blob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `website_metrics_${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const categoryOptions = useMemo(
    () => Array.from(new Set(cases.map((c) => c.category).filter((c): c is string => Boolean(c)))).sort(),
    [cases]
  );

  const difficultyOptions = useMemo(
    () => Array.from(new Set(cases.map((c) => c.difficulty).filter((c): c is string => Boolean(c)))).sort(),
    [cases]
  );

  const toggleSelection = (option: string, list: string[], setter: (next: string[]) => void) => {
    setter(list.includes(option) ? list.filter((item) => item !== option) : [...list, option]);
  };

  async function handleRunSuite(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    setIsRunning(true);
    setError(null);
    try {
      const payload = await runEvaluationSuite({
        token,
        limit: runLimit,
        categories: selectedCategories,
        difficulties: selectedDifficulties,
      });
      setAnalysis(payload.analysis);
      setResults(payload.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run evaluation");
    } finally {
      setIsRunning(false);
    }
  }

  async function handleRefreshSummary() {
    if (!token) return;
    setLogMessage(null);
    try {
      const summary = await fetchEvaluationLogSummary(token);
      setLogSummary(summary);
    } catch (err) {
      setLogSummary({ error: err instanceof Error ? err.message : "Unable to refresh" });
    }
  }

  async function handleRefreshRuns() {
    if (!token) return;
    setRunsLoading(true);
    setRunsError(null);
    try {
      const runs = await fetchEvaluationRuns(token, 10);
      setEvaluationRuns(runs);
    } catch (err) {
      setRunsError(err instanceof Error ? err.message : "Unable to refresh runs");
    } finally {
      setRunsLoading(false);
    }
  }

  async function handleClearLogs() {
    if (!token) return;
    setLogMessage(null);
    try {
      await clearEvaluationLogs(token);
      setLogMessage("Logs cleared");
      await handleRefreshSummary();
    } catch (err) {
      setLogMessage(err instanceof Error ? err.message : "Unable to clear logs");
    }
  }

  // Run batch quality evaluation
  const handleRunQualityEval = async () => {
    if (!token) return;
    setQualityLoading(true);
    setQualityError(null);
    try {
      const result = await runBatchQuality(token, 20);
      setQualityResult(result);
    } catch (err) {
      setQualityError(err instanceof Error ? err.message : "Quality evaluation failed");
    } finally {
      setQualityLoading(false);
    }
  };

  // Resolve quality summary: from batch result or from realtime metrics
  const activeQualitySummary: QualitySummary | null =
    qualityResult?.quality_summary ?? realtimeMetrics?.quality_summary ?? null;

  // Radar chart data
  const radarData = activeQualitySummary
    ? [
        { dimension: "Faithfulness", value: activeQualitySummary.avg_faithfulness, fullMark: 1 },
        { dimension: "Relevance", value: activeQualitySummary.avg_answer_relevance, fullMark: 1 },
        { dimension: "Ctx Precision", value: activeQualitySummary.avg_context_precision, fullMark: 1 },
        { dimension: "Ctx Recall", value: activeQualitySummary.avg_context_recall, fullMark: 1 },
        { dimension: "Correctness", value: activeQualitySummary.avg_correctness, fullMark: 1 },
      ]
    : [];

  const isFiniteMetric = (value: unknown): value is number =>
    typeof value === "number" && Number.isFinite(value);

  const formatMetric = (
    value: number | null | undefined,
    digits: number,
    suffix: string = "",
    fallback: string = "N/A"
  ) => (isFiniteMetric(value) ? `${value.toFixed(digits)}${suffix}` : fallback);

  const formatOptionalMetric = (
    value: number | null | undefined,
    digits: number = 0,
    suffix: string = "",
    fallback: string = "Unavailable"
  ) => (isFiniteMetric(value) ? `${value.toFixed(digits)}${suffix}` : fallback);

  const formatOptionalInteger = (
    value: number | null | undefined,
    fallback: string = "Unavailable"
  ) => (isFiniteMetric(value) ? value.toLocaleString() : fallback);

  const formatOptionalText = (
    value: string | null | undefined,
    fallback: string = "Unavailable"
  ) => (value && value.trim() ? value : fallback);

  // Color helper for quality scores
  const qualityColor = (score: number | null | undefined) =>
    !isFiniteMetric(score)
      ? "text-muted"
      : score >= 0.7
      ? "text-success"
      : score >= 0.4
      ? "text-warning"
      : "text-danger";

  const qualityBg = (score: number | null | undefined) =>
    !isFiniteMetric(score)
      ? "bg-surface-2"
      : score >= 0.7
      ? "bg-success-bg"
      : score >= 0.4
      ? "bg-warning-bg"
      : "bg-danger-bg";

  const driftColor = (score: number | null | undefined) =>
    !isFiniteMetric(score)
      ? "text-muted"
      : score < 1.5
      ? "text-success"
      : score < 2.5
      ? "text-warning"
      : "text-danger";

  // Metric Card Component
  const MetricCard = ({
    title,
    value,
    subtitle,
    icon: Icon,
    trend,
    color = "indigo"
  }: {
    title: string;
    value: string | number;
    subtitle?: string;
    icon: typeof Activity;
    trend?: "up" | "down" | "neutral";
    color?: "indigo" | "emerald" | "amber" | "red" | "blue";
  }) => {
    const colorClasses = {
      indigo: "bg-primary-bg text-primary",
      emerald: "bg-success-bg text-success",
      amber: "bg-warning-bg text-warning",
      red: "bg-danger-bg text-danger",
      blue: "bg-primary-bg text-primary",
    };

    return (
      <div className="rounded-2xl border border-line bg-surface p-5 shadow-sm">
        <div className="flex items-start justify-between">
          <div className={`rounded-xl p-2.5 ${colorClasses[color]}`}>
            <Icon className="h-5 w-5" />
          </div>
          {trend && (
            <div className={`flex items-center gap-1 text-xs font-medium ${
              trend === "up" ? "text-success" : trend === "down" ? "text-danger" : "text-muted"
            }`}>
              <TrendingUp className={`h-3 w-3 ${trend === "down" ? "rotate-180" : ""}`} />
              {trend === "up" ? "Good" : trend === "down" ? "Needs attention" : "Stable"}
            </div>
          )}
        </div>
        <p className="mt-4 text-2xl font-bold text-foreground">{value}</p>
        <p className="text-xs uppercase tracking-wide text-muted">{title}</p>
        {subtitle && <p className="mt-1 text-xs text-muted">{subtitle}</p>}
      </div>
    );
  };

  // Progress Bar Component
  const ProgressBar = ({ value, max, label, color = "indigo" }: { value: number; max: number; label: string; color?: string }) => {
    const percentage = Math.min(100, (value / max) * 100);
    return (
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-muted">{label}</span>
          <span className="font-medium text-foreground">{value.toFixed(1)}%</span>
        </div>
        <div className="h-2 rounded-full bg-line overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              color === "emerald" ? "bg-success-solid" :
              color === "amber" ? "bg-warning" :
              color === "red" ? "bg-danger-solid" : "bg-primary-solid"
            }`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
    );
  };

  return (
    <PageShell className="max-w-7xl" contentClassName="gap-6" noCard>
      {/* Header */}
      <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Evaluation Dashboard</h1>
          <p className="mt-1 text-muted">Monitor RAG pipeline performance and website metrics</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchPrometheusMetrics}
            disabled={metricsLoading}
            className="flex items-center gap-2 rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-surface-2 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${metricsLoading ? "animate-spin" : ""}`} />
            Refresh Metrics
          </button>
        </div>
      </header>

      {/* Tab Navigation */}
      <div className="overflow-x-auto rounded-xl bg-surface-2">
        <div className="flex gap-1 p-1 min-w-max">
          {[
            { id: "rag", label: "RAG Pipeline", icon: Brain },
            { id: "agents", label: "Agent Analytics", icon: Zap },
            { id: "graph", label: "Knowledge Graph", icon: GitBranch },
            { id: "website", label: "Website Metrics", icon: Server },
            { id: "aws", label: "AWS Services", icon: Cloud },
            { id: "tests", label: "Test Suite", icon: BarChart3 },
            { id: "quiz", label: "Quiz Analytics", icon: Target },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`flex items-center justify-center gap-1.5 rounded-lg px-3 py-2.5 text-sm font-medium transition whitespace-nowrap sm:px-4 sm:gap-2 ${
                activeTab === tab.id
                  ? "bg-surface text-foreground shadow-sm"
                  : "text-muted hover:text-foreground"
              }`}
            >
              <tab.icon className="h-4 w-4 flex-shrink-0" />
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* RAG Pipeline Tab - Real-time Metrics */}
      {activeTab === "rag" && (
        <div className="space-y-6 animate-fade-in-up">
          {/* Header with Refresh and Export */}
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-primary-bg p-2.5">
                <Brain className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground">Real-time Pipeline Metrics</h3>
                <p className="text-xs text-muted">
                  Live data from actual chat queries • {realtimeMetrics?.summary?.total_queries_analyzed || 0} queries analyzed
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {/* Export Dropdown */}
              <div className="relative group">
                <button className="flex items-center gap-2 rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-surface-2">
                  <Download className="h-4 w-4" />
                  Export
                </button>
                <div className="absolute right-0 top-full mt-1 hidden group-hover:block w-32 rounded-lg border border-line bg-surface shadow-lg z-10">
                  <button
                    onClick={() => handleExport("json")}
                    className="w-full px-4 py-2 text-left text-sm text-foreground hover:bg-surface-2 rounded-t-lg"
                  >
                    Export JSON
                  </button>
                  <button
                    onClick={() => handleExport("csv")}
                    className="w-full px-4 py-2 text-left text-sm text-foreground hover:bg-surface-2 rounded-b-lg"
                  >
                    Export CSV
                  </button>
                </div>
              </div>
              <button
                onClick={() => { fetchRealtimeMetricsData(); fetchHistoryData(); }}
                disabled={realtimeLoading || historyLoading}
                className="flex items-center gap-2 rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-surface-2 disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${realtimeLoading || historyLoading ? "animate-spin" : ""}`} />
                Refresh
              </button>
            </div>
          </div>

          {realtimeLoading && !realtimeMetrics ? (
            <div className="flex items-center justify-center py-16">
              <RefreshCw className="h-8 w-8 text-muted animate-spin" />
            </div>
          ) : realtimeMetrics?.status === "no_data" ? (
            <div className="flex flex-col items-center justify-center py-16 text-center rounded-2xl border border-line bg-surface">
              <Brain className="h-16 w-16 text-muted/40 mb-4" />
              <h3 className="text-lg font-semibold text-foreground mb-2">No Data Yet</h3>
              <p className="text-muted max-w-md">
                {realtimeMetrics.message || "Start chatting with the AI to see real-time pipeline metrics!"}
              </p>
            </div>
          ) : realtimeMetrics?.summary ? (
            <>
              {/* Section 1: Quality Metrics Cards */}
              <section>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="rounded-xl bg-lavender/15 p-2.5">
                      <Shield className="h-5 w-5 text-violet-700 dark:text-lavender" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground">Quality Metrics</h3>
                      <p className="text-xs text-muted">
                        {activeQualitySummary
                          ? `${activeQualitySummary.evaluated_count} queries evaluated`
                          : "Run evaluation to see quality scores"}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={handleRunQualityEval}
                    disabled={qualityLoading}
                    className="flex items-center gap-2 rounded-lg bg-primary-solid px-4 py-2 text-sm font-medium text-white transition hover:brightness-110 disabled:opacity-50"
                  >
                    {qualityLoading ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        Evaluating...
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4" />
                        Run Quality Evaluation
                      </>
                    )}
                  </button>
                </div>

                {qualityError && (
                  <div className="mb-4 rounded-xl border border-danger/30 bg-danger-bg p-3 text-sm text-danger">
                    {qualityError}
                  </div>
                )}

                {activeQualitySummary ? (
                  <div className="grid gap-4 md:grid-cols-5">
                    {[
                      { label: "Faithfulness", value: activeQualitySummary.avg_faithfulness, icon: Shield },
                      { label: "Answer Relevance", value: activeQualitySummary.avg_answer_relevance, icon: Target },
                      { label: "Context Precision", value: activeQualitySummary.avg_context_precision, icon: Layers },
                      { label: "Context Recall", value: activeQualitySummary.avg_context_recall, icon: Database },
                      { label: "Correctness", value: activeQualitySummary.avg_correctness, icon: CheckCircle },
                    ].map((metric) => (
                      <div
                        key={metric.label}
                        className={`rounded-2xl border border-line p-5 shadow-sm ${qualityBg(metric.value)}`}
                      >
                        <div className="flex items-center gap-2 mb-3">
                          <metric.icon className={`h-4 w-4 ${qualityColor(metric.value)}`} />
                          <span className="text-xs font-medium text-muted">{metric.label}</span>
                        </div>
                        <p className={`text-2xl font-bold ${qualityColor(metric.value)}`}>
                          {metric.value.toFixed(2)}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="grid gap-4 md:grid-cols-5">
                    {["Faithfulness", "Answer Relevance", "Context Precision", "Context Recall", "Correctness"].map(
                      (label) => (
                        <div
                          key={label}
                          className="rounded-2xl border border-line bg-surface-2 p-5 shadow-sm"
                        >
                          <span className="text-xs font-medium text-muted">{label}</span>
                          <p className="mt-2 text-2xl font-bold text-muted/40">N/A</p>
                        </div>
                      )
                    )}
                  </div>
                )}
              </section>

              {/* Section 2: Radar Chart + Summary Cards */}
              <section className="grid gap-6 lg:grid-cols-2">
                {/* Radar Chart */}
                <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="rounded-xl bg-primary-bg p-2.5">
                      <Gauge className="h-5 w-5 text-primary" />
                    </div>
                    <h3 className="font-semibold text-foreground">Quality Radar</h3>
                  </div>
                  {radarData.length > 0 ? (
                    <div className="h-72">
                      <ResponsiveContainer width="100%" height="100%">
                        <RadarChart outerRadius="70%" data={radarData}>
                          <PolarGrid stroke="var(--color-border)" />
                          <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                          <PolarRadiusAxis angle={90} domain={[0, 1]} tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} />
                          <Radar
                            name="Quality"
                            dataKey="value"
                            stroke="var(--color-primary)"
                            fill="var(--color-primary)"
                            fillOpacity={0.3}
                            strokeWidth={2}
                          />
                        </RadarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center h-72 text-center">
                      <Gauge className="h-12 w-12 text-muted/40 mb-3" />
                      <p className="text-sm text-muted">Run quality evaluation to see the radar chart</p>
                    </div>
                  )}
                </div>

                {/* Summary Cards */}
                <div className="grid gap-4 grid-cols-2 content-start">
                  <MetricCard
                    title="Total Queries"
                    value={realtimeMetrics.summary.total_queries_analyzed}
                    subtitle="From actual chats"
                    icon={Database}
                    color="indigo"
                  />
                  <MetricCard
                    title="Avg Latency"
                    value={`${realtimeMetrics.summary.avg_total_time_seconds.toFixed(2)}s`}
                    subtitle={`p95: ${realtimeMetrics.summary.p95_total_time_seconds.toFixed(2)}s`}
                    icon={Clock}
                    trend={realtimeMetrics.summary.avg_total_time_seconds < 3 ? "up" : "down"}
                    color="blue"
                  />
                  <MetricCard
                    title="Avg Relevance"
                    value={realtimeMetrics.summary.avg_relevance_score.toFixed(2)}
                    subtitle={`Range: ${realtimeMetrics.summary.min_relevance_score.toFixed(2)} - ${realtimeMetrics.summary.max_relevance_score.toFixed(2)}`}
                    icon={Target}
                    trend={realtimeMetrics.summary.avg_relevance_score > 0.7 ? "up" : "neutral"}
                    color="emerald"
                  />
                  <MetricCard
                    title="Avg Docs Retrieved"
                    value={realtimeMetrics.summary.avg_docs_retrieved.toFixed(1)}
                    subtitle={`Avg ${realtimeMetrics.summary.avg_response_length_words} words/response`}
                    icon={FileText}
                    color="amber"
                  />
                </div>
              </section>

              {/* Section 3: Retrieval Evaluation */}
              <section className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
                <div className="flex items-center gap-3 mb-6">
                  <div className="rounded-xl bg-success-bg p-2.5">
                    <Target className="h-5 w-5 text-success" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground">Retrieval Evaluation</h3>
                    <p className="text-xs text-muted">Document retrieval quality and distribution</p>
                  </div>
                </div>
                <div className="grid gap-6 lg:grid-cols-2">
                  {/* Retrieval Stats */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <span className="text-sm text-muted">Avg Docs Retrieved</span>
                      <span className="text-lg font-bold text-foreground">
                        {realtimeMetrics.summary.avg_docs_retrieved.toFixed(1)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <span className="text-sm text-muted">Avg Relevance Score</span>
                      <span className={`text-lg font-bold ${qualityColor(realtimeMetrics.summary.avg_relevance_score)}`}>
                        {realtimeMetrics.summary.avg_relevance_score.toFixed(3)}
                      </span>
                    </div>
                    {activeQualitySummary && (
                      <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                        <span className="text-sm text-muted">Context Precision</span>
                        <span className={`text-lg font-bold ${qualityColor(activeQualitySummary.avg_context_precision)}`}>
                          {activeQualitySummary.avg_context_precision.toFixed(3)}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Relevance Distribution */}
                  {realtimeMetrics.performance && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between p-3 rounded-xl bg-success-bg">
                        <div className="flex items-center gap-3">
                          <CheckCircle className="h-5 w-5 text-success" />
                          <span className="text-sm text-muted">High (&gt;0.7)</span>
                        </div>
                        <span className="text-lg font-bold text-success">
                          {realtimeMetrics.performance.relevance_distribution.high_relevance_percentage}%
                        </span>
                      </div>
                      <div className="flex items-center justify-between p-3 rounded-xl bg-warning-bg">
                        <div className="flex items-center gap-3">
                          <Target className="h-5 w-5 text-warning" />
                          <span className="text-sm text-muted">Medium (0.4-0.7)</span>
                        </div>
                        <span className="text-lg font-bold text-warning">
                          {realtimeMetrics.performance.relevance_distribution.medium_0_4_to_0_7}
                        </span>
                      </div>
                      <div className="flex items-center justify-between p-3 rounded-xl bg-danger-bg">
                        <div className="flex items-center gap-3">
                          <AlertTriangle className="h-5 w-5 text-danger" />
                          <span className="text-sm text-muted">Low (&lt;0.4)</span>
                        </div>
                        <span className="text-lg font-bold text-danger">
                          {realtimeMetrics.performance.relevance_distribution.low_below_0_4}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </section>

              {/* Section 4: Generation Evaluation */}
              <section className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
                <div className="flex items-center gap-3 mb-6">
                  <div className="rounded-xl bg-lavender/15 p-2.5">
                    <Brain className="h-5 w-5 text-violet-700 dark:text-lavender" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground">Generation Evaluation</h3>
                    <p className="text-xs text-muted">Answer quality and response characteristics</p>
                  </div>
                </div>
                <div className="grid gap-6 lg:grid-cols-2">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <span className="text-sm text-muted">Avg Response Length</span>
                      <span className="text-lg font-bold text-foreground">
                        {realtimeMetrics.summary.avg_response_length_words} words
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <span className="text-sm text-muted">Avg Generation Time</span>
                      <span className="text-lg font-bold text-foreground">
                        {realtimeMetrics.summary.avg_generation_time_seconds.toFixed(2)}s
                      </span>
                    </div>
                  </div>
                  <div className="space-y-4">
                    {activeQualitySummary ? (
                      <>
                        <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                          <span className="text-sm text-muted">Faithfulness</span>
                          <span className={`text-lg font-bold ${qualityColor(activeQualitySummary.avg_faithfulness)}`}>
                            {activeQualitySummary.avg_faithfulness.toFixed(3)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                          <span className="text-sm text-muted">Answer Relevance</span>
                          <span className={`text-lg font-bold ${qualityColor(activeQualitySummary.avg_answer_relevance)}`}>
                            {activeQualitySummary.avg_answer_relevance.toFixed(3)}
                          </span>
                        </div>
                      </>
                    ) : (
                      <div className="flex items-center justify-center p-6 rounded-xl bg-surface-2 text-center">
                        <p className="text-sm text-muted">Run quality evaluation to see faithfulness & relevance scores</p>
                      </div>
                    )}
                  </div>
                </div>
              </section>

              {/* Section 5: End-to-End Performance */}
              <section className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
                <div className="flex items-center gap-3 mb-6">
                  <div className="rounded-xl bg-primary-bg p-2.5">
                    <Clock className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground">End-to-End Performance</h3>
                    <p className="text-xs text-muted">Total latency with percentile breakdown</p>
                  </div>
                </div>
                <div className="grid gap-6 lg:grid-cols-2">
                  {/* Percentile Cards */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="rounded-xl bg-surface-2 p-4 text-center">
                      <p className="text-xs text-muted mb-1">p50</p>
                      <p className="text-xl font-bold text-foreground">
                        {realtimeMetrics.summary.p50_total_time_seconds.toFixed(2)}s
                      </p>
                    </div>
                    <div className="rounded-xl bg-surface-2 p-4 text-center">
                      <p className="text-xs text-muted mb-1">p95</p>
                      <p className="text-xl font-bold text-warning">
                        {realtimeMetrics.summary.p95_total_time_seconds.toFixed(2)}s
                      </p>
                    </div>
                    <div className="rounded-xl bg-surface-2 p-4 text-center">
                      <p className="text-xs text-muted mb-1">p99</p>
                      <p className="text-xl font-bold text-danger">
                        {realtimeMetrics.summary.p99_total_time_seconds.toFixed(2)}s
                      </p>
                    </div>
                  </div>

                  {/* Latency Distribution */}
                  {realtimeMetrics.performance && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between p-3 rounded-xl bg-success-bg">
                        <div className="flex items-center gap-3">
                          <Zap className="h-5 w-5 text-success" />
                          <span className="text-sm text-muted">Fast (&lt;2s)</span>
                        </div>
                        <div className="text-right">
                          <span className="text-lg font-bold text-success">
                            {realtimeMetrics.performance.latency_distribution.fast_percentage}%
                          </span>
                          <span className="text-xs text-muted ml-2">
                            ({realtimeMetrics.performance.latency_distribution.fast_under_2s})
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center justify-between p-3 rounded-xl bg-warning-bg">
                        <div className="flex items-center gap-3">
                          <Clock className="h-5 w-5 text-warning" />
                          <span className="text-sm text-muted">Medium (2-5s)</span>
                        </div>
                        <span className="text-lg font-bold text-warning">
                          {realtimeMetrics.performance.latency_distribution.medium_2_to_5s}
                        </span>
                      </div>
                      <div className="flex items-center justify-between p-3 rounded-xl bg-danger-bg">
                        <div className="flex items-center gap-3">
                          <AlertTriangle className="h-5 w-5 text-danger" />
                          <span className="text-sm text-muted">Slow (&gt;5s)</span>
                        </div>
                        <span className="text-lg font-bold text-danger">
                          {realtimeMetrics.performance.latency_distribution.slow_over_5s}
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Historical Latency Trend */}
                {metricsHistory?.data_points && metricsHistory.data_points.length > 0 && (
                  <div className="mt-6">
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="text-sm font-medium text-foreground">Historical Latency Trend</h4>
                      <div className="flex items-center gap-2">
                        <select
                          value={historyHours}
                          onChange={(e) => setHistoryHours(Number(e.target.value))}
                          className="rounded-lg border border-line bg-surface px-3 py-1.5 text-xs text-foreground"
                        >
                          <option value={1}>1h</option>
                          <option value={6}>6h</option>
                          <option value={24}>24h</option>
                          <option value={72}>3d</option>
                          <option value={168}>7d</option>
                        </select>
                        <select
                          value={historyGranularity}
                          onChange={(e) => setHistoryGranularity(e.target.value as "minute" | "hour" | "day")}
                          className="rounded-lg border border-line bg-surface px-3 py-1.5 text-xs text-foreground"
                        >
                          <option value="minute">Min</option>
                          <option value="hour">Hour</option>
                          <option value="day">Day</option>
                        </select>
                      </div>
                    </div>
                    <div className="h-48">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={metricsHistory.data_points}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                          <XAxis
                            dataKey="timestamp"
                            tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
                            tickFormatter={(value) => {
                              const parts = value.split(" ");
                              return parts[1] || parts[0];
                            }}
                          />
                          <YAxis tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} tickFormatter={(value) => `${value}s`} />
                          <Tooltip
                            contentStyle={CHART_TOOLTIP_STYLE}
                            formatter={(value) => [`${(value as number)?.toFixed(3) ?? 0}s`, ""]}
                          />
                          <Legend />
                          <Area
                            type="monotone"
                            dataKey="avg_retrieval_latency"
                            name="Retrieval"
                            stackId="1"
                            stroke="var(--color-primary)"
                            fill="var(--color-primary)"
                            fillOpacity={0.6}
                          />
                          <Area
                            type="monotone"
                            dataKey="avg_generation_latency"
                            name="Generation"
                            stackId="1"
                            stroke="var(--color-lavender)"
                            fill="var(--color-lavender)"
                            fillOpacity={0.6}
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}
              </section>

              {/* Section 6: Recent Queries */}
              {realtimeMetrics.recent_queries.length > 0 && (
                <section className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="rounded-xl bg-lavender/15 p-2.5">
                      <Activity className="h-5 w-5 text-violet-700 dark:text-lavender" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground">Recent Queries</h3>
                      <p className="text-xs text-muted">Last {realtimeMetrics.recent_queries.length} queries from chat</p>
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-line">
                          <th className="pb-3 text-left font-medium text-muted">Query</th>
                          <th className="pb-3 text-center font-medium text-muted">Latency</th>
                          <th className="pb-3 text-center font-medium text-muted">Relevance</th>
                          <th className="pb-3 text-center font-medium text-muted">Docs</th>
                          <th className="pb-3 text-center font-medium text-muted">Quality</th>
                          <th className="pb-3 text-center font-medium text-muted">Mode</th>
                        </tr>
                      </thead>
                      <tbody>
                        {realtimeMetrics.recent_queries.map((query, idx) => (
                          <tr key={idx} className="border-b border-line last:border-0">
                            <td className="py-3 pr-4 max-w-[300px]">
                              <p className="font-medium text-foreground truncate">{query.query}</p>
                              <p className="text-xs text-muted">
                                {query.timestamp ? new Date(query.timestamp).toLocaleString() : ""}
                              </p>
                            </td>
                            <td className="py-3 text-center">
                              <span className="font-bold text-foreground">
                                {query.total_time.toFixed(2)}s
                              </span>
                            </td>
                            <td className="py-3 text-center">
                              <span className={`font-bold ${
                                isFiniteMetric(query.relevance_score)
                                  ? query.relevance_score > 0.7
                                    ? "text-success"
                                    : query.relevance_score > 0.4
                                    ? "text-warning"
                                    : "text-danger"
                                  : "text-muted"
                              }`}>
                                {formatMetric(query.relevance_score, 2)}
                              </span>
                            </td>
                            <td className="py-3 text-center font-bold text-foreground">
                              {query.docs_retrieved}
                            </td>
                            <td className="py-3 text-center">
                              {query.quality_scores && isFiniteMetric(query.quality_scores.correctness) ? (
                                <span className={`font-bold ${qualityColor(query.quality_scores.correctness)}`}>
                                  {formatMetric(query.quality_scores.correctness, 2)}
                                </span>
                              ) : (
                                <span className="text-muted text-xs">—</span>
                              )}
                            </td>
                            <td className="py-3 text-center">
                              <span className="inline-flex items-center rounded-full bg-primary-bg px-2 py-0.5 text-xs font-medium text-primary">
                                {query.mode}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              {/* Section 7: Dataset Pipeline Evaluation */}
              <section className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <div className="rounded-xl bg-success-bg p-2.5">
                      <FileText className="h-5 w-5 text-success" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground">Dataset Pipeline Evaluation</h3>
                      <p className="text-xs text-muted">
                        Run evaluation dataset through the live RAG pipeline (retrieve → generate → judge)
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      value={datasetLimit}
                      onChange={(e) => setDatasetLimit(Number(e.target.value))}
                      className="rounded-lg border border-line bg-surface px-3 py-2 text-sm text-foreground"
                    >
                      <option value={5}>5 questions</option>
                      <option value={10}>10 questions</option>
                      <option value={20}>20 questions</option>
                      <option value={40}>40 questions</option>
                      <option value={64}>All 64 questions</option>
                    </select>
                    <button
                      onClick={handleRunDatasetQuality}
                      disabled={datasetLoading}
                      className="flex items-center gap-2 rounded-lg bg-success-solid px-4 py-2 text-sm font-medium text-white transition hover:brightness-110 disabled:opacity-50"
                    >
                      {datasetLoading ? (
                        <>
                          <RefreshCw className="h-4 w-4 animate-spin" />
                          Running...
                        </>
                      ) : (
                        <>
                          <Play className="h-4 w-4" />
                          Run Dataset Evaluation
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {datasetError && (
                  <div className="mb-4 rounded-xl border border-danger/30 bg-danger-bg p-3 text-sm text-danger">
                    {datasetError}
                  </div>
                )}

                {datasetLoading && !datasetResult ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <RefreshCw className="h-8 w-8 text-success animate-spin mb-3" />
                    <p className="text-sm text-muted">Running {datasetLimit} questions through the RAG pipeline...</p>
                    <p className="text-xs text-muted mt-1">This may take a few minutes</p>
                  </div>
                ) : datasetResult ? (
                  <div className="space-y-6">
                    {datasetResult.message && !datasetResult.quality_summary && (
                      <div className="rounded-xl bg-warning-bg p-3 text-sm text-warning">
                        {datasetResult.message}
                      </div>
                    )}

                    {/* Quality Score Cards */}
                    {datasetResult.quality_summary && (
                      <div className="grid gap-4 md:grid-cols-5">
                        {[
                          { label: "Faithfulness", value: datasetResult.quality_summary.avg_faithfulness, icon: Shield },
                          { label: "Answer Relevance", value: datasetResult.quality_summary.avg_answer_relevance, icon: Target },
                          { label: "Context Precision", value: datasetResult.quality_summary.avg_context_precision, icon: Layers },
                          { label: "Context Recall", value: datasetResult.quality_summary.avg_context_recall, icon: Database },
                          { label: "Correctness", value: datasetResult.quality_summary.avg_correctness, icon: CheckCircle },
                        ].map((metric) => (
                          <div
                            key={metric.label}
                            className={`rounded-2xl border border-line p-5 shadow-sm ${qualityBg(metric.value)}`}
                          >
                            <div className="flex items-center gap-2 mb-3">
                              <metric.icon className={`h-4 w-4 ${qualityColor(metric.value)}`} />
                              <span className="text-xs font-medium text-muted">{metric.label}</span>
                            </div>
                            <p className={`text-2xl font-bold ${qualityColor(metric.value)}`}>
                              {metric.value.toFixed(2)}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Summary Stats + Radar Chart */}
                    {datasetResult.quality_summary && (
                      <div className="grid gap-6 lg:grid-cols-2">
                        {/* Radar Chart */}
                        <div className="rounded-xl border border-line bg-surface-2 p-4">
                          <h4 className="text-sm font-medium text-foreground mb-3">Quality Radar</h4>
                          <div className="h-56">
                            <ResponsiveContainer width="100%" height="100%">
                              <RadarChart
                                outerRadius="70%"
                                data={[
                                  { dimension: "Faithfulness", value: datasetResult.quality_summary.avg_faithfulness, fullMark: 1 },
                                  { dimension: "Relevance", value: datasetResult.quality_summary.avg_answer_relevance, fullMark: 1 },
                                  { dimension: "Ctx Precision", value: datasetResult.quality_summary.avg_context_precision, fullMark: 1 },
                                  { dimension: "Ctx Recall", value: datasetResult.quality_summary.avg_context_recall, fullMark: 1 },
                                  { dimension: "Correctness", value: datasetResult.quality_summary.avg_correctness, fullMark: 1 },
                                ]}
                              >
                                <PolarGrid stroke="var(--color-border)" />
                                <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                                <PolarRadiusAxis angle={90} domain={[0, 1]} tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} />
                                <Radar name="Dataset" dataKey="value" stroke="var(--color-secondary)" fill="var(--color-secondary)" fillOpacity={0.3} strokeWidth={2} />
                              </RadarChart>
                            </ResponsiveContainer>
                          </div>
                        </div>

                        {/* Summary Cards */}
                        <div className="grid grid-cols-2 gap-4 content-start">
                          <div className="rounded-xl bg-surface-2 p-4">
                            <p className="text-xs text-muted mb-1">Questions Evaluated</p>
                            <p className="text-xl font-bold text-foreground">
                              {datasetResult.total_evaluated}/{datasetResult.total_dataset_questions || datasetResult.total_evaluated}
                            </p>
                          </div>
                          <div className="rounded-xl bg-surface-2 p-4">
                            <p className="text-xs text-muted mb-1">Avg Latency</p>
                            <p className="text-xl font-bold text-foreground">
                              {datasetResult.avg_latency?.toFixed(2) || "—"}s
                            </p>
                          </div>
                          <div className="rounded-xl bg-surface-2 p-4">
                            <p className="text-xs text-muted mb-1">Avg Correctness</p>
                            <p className={`text-xl font-bold ${qualityColor(datasetResult.quality_summary.avg_correctness)}`}>
                              {(datasetResult.quality_summary.avg_correctness * 100).toFixed(1)}%
                            </p>
                          </div>
                          <div className="rounded-xl bg-surface-2 p-4">
                            <p className="text-xs text-muted mb-1">Avg Faithfulness</p>
                            <p className={`text-xl font-bold ${qualityColor(datasetResult.quality_summary.avg_faithfulness)}`}>
                              {(datasetResult.quality_summary.avg_faithfulness * 100).toFixed(1)}%
                            </p>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Individual Results Table */}
                    {datasetResult.individual_results.length > 0 && (
                      <div>
                        <div className="flex items-center gap-2 mb-3">
                          <Activity className="h-4 w-4 text-success" />
                          <h4 className="text-sm font-semibold text-foreground">
                            Per-Question Results ({datasetResult.individual_results.length})
                          </h4>
                        </div>
                        <div className="overflow-x-auto max-h-96 overflow-y-auto rounded-xl border border-line">
                          <table className="w-full text-sm">
                            <thead className="sticky top-0 bg-surface-2">
                              <tr className="border-b border-line">
                                <th className="px-3 py-2 text-left font-medium text-muted">Question</th>
                                <th className="px-3 py-2 text-center font-medium text-muted">Faithful</th>
                                <th className="px-3 py-2 text-center font-medium text-muted">Relevance</th>
                                <th className="px-3 py-2 text-center font-medium text-muted">Recall</th>
                                <th className="px-3 py-2 text-center font-medium text-muted">Correct</th>
                                <th className="px-3 py-2 text-center font-medium text-muted">Latency</th>
                              </tr>
                            </thead>
                            <tbody>
                              {datasetResult.individual_results.map((item, idx) => (
                                <tr key={idx} className="border-b border-line last:border-0">
                                  <td className="px-3 py-2 max-w-[280px]">
                                    <p className="font-medium text-foreground truncate">{item.query}</p>
                                    {item.reasoning && (
                                      <p className="text-xs text-muted truncate mt-0.5">{item.reasoning}</p>
                                    )}
                                  </td>
                                  <td className="px-3 py-2 text-center">
                                    <span className={`font-bold ${qualityColor(item.faithfulness)}`}>
                                      {formatMetric(item.faithfulness, 2)}
                                    </span>
                                  </td>
                                  <td className="px-3 py-2 text-center">
                                    <span className={`font-bold ${qualityColor(item.answer_relevance)}`}>
                                      {formatMetric(item.answer_relevance, 2)}
                                    </span>
                                  </td>
                                  <td className="px-3 py-2 text-center">
                                    <span className={`font-bold ${qualityColor(item.context_recall)}`}>
                                      {formatMetric(item.context_recall, 2)}
                                    </span>
                                  </td>
                                  <td className="px-3 py-2 text-center">
                                    <span className={`font-bold ${qualityColor(item.correctness)}`}>
                                      {formatMetric(item.correctness, 2)}
                                    </span>
                                  </td>
                                  <td className="px-3 py-2 text-center text-muted">
                                    {formatMetric(item.latency, 1, "s")}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <FileText className="h-12 w-12 text-muted/40 mb-3" />
                    <p className="text-sm text-muted">Click &quot;Run Dataset Evaluation&quot; to test {datasetLimit} questions from the evaluation dataset</p>
                    <p className="text-xs text-muted mt-1">Each question will be sent through the full RAG pipeline and scored by LLM-as-judge</p>
                  </div>
                )}
              </section>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Brain className="h-16 w-16 text-muted/40 mb-4" />
              <p className="text-muted">Unable to load RAG metrics</p>
              <button
                onClick={fetchRealtimeMetricsData}
                className="mt-4 text-sm text-primary hover:text-primary"
              >
                Try again
              </button>
            </div>
          )}
        </div>
      )}

      {/* Website Metrics Tab */}
      {activeTab === "website" && (
        <div className="space-y-6 animate-fade-in-up">
          {/* Website Header with Refresh and Export */}
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-primary-bg p-2.5">
                <Server className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground">Website Performance</h3>
                <p className="text-xs text-muted">
                  Prometheus metrics • Auto-refreshes every 30s
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleExportWebsite}
                disabled={!websiteMetrics}
                className="flex items-center gap-2 rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-surface-2 disabled:opacity-50"
              >
                <Download className="h-4 w-4" />
                Export
              </button>
              <button
                onClick={fetchPrometheusMetrics}
                disabled={metricsLoading}
                className="flex items-center gap-2 rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-surface-2 disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${metricsLoading ? "animate-spin" : ""}`} />
                Refresh
              </button>
            </div>
          </div>

          {metricsLoading && !websiteMetrics ? (
            <div className="flex items-center justify-center py-16">
              <RefreshCw className="h-8 w-8 text-muted animate-spin" />
            </div>
          ) : websiteMetrics ? (
            <>
              <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  title="Total Requests"
                  value={websiteMetrics.totalRequests.toLocaleString()}
                  subtitle="HTTP requests processed"
                  icon={Server}
                  color="indigo"
                />
                <MetricCard
                  title="Avg Response Time"
                  value={`${(websiteMetrics.avgResponseTime * 1000).toFixed(0)}ms`}
                  subtitle="API endpoint latency"
                  icon={Clock}
                  trend={websiteMetrics.avgResponseTime < 0.5 ? "up" : "down"}
                  color="blue"
                />
                <MetricCard
                  title="Error Rate"
                  value={`${websiteMetrics.errorRate.toFixed(2)}%`}
                  subtitle="HTTP 5xx errors"
                  icon={AlertTriangle}
                  trend={websiteMetrics.errorRate < 1 ? "up" : "down"}
                  color={websiteMetrics.errorRate < 1 ? "emerald" : "red"}
                />
                <MetricCard
                  title="Active Connections"
                  value={websiteMetrics.activeConnections}
                  subtitle="Currently processing"
                  icon={Activity}
                  color="amber"
                />
              </section>

              <section className="grid gap-6 lg:grid-cols-2">
                <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="rounded-xl bg-success-bg p-2.5">
                      <Gauge className="h-5 w-5 text-success" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground">API Performance</h3>
                      <p className="text-xs text-muted">Request processing metrics</p>
                    </div>
                  </div>

                  <div className="space-y-6">
                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <div className="flex items-center gap-3">
                        <CheckCircle className="h-5 w-5 text-success" />
                        <span className="text-sm text-muted">Successful Requests</span>
                      </div>
                      <span className="text-lg font-bold text-foreground">
                        {((1 - websiteMetrics.errorRate / 100) * 100).toFixed(1)}%
                      </span>
                    </div>

                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <div className="flex items-center gap-3">
                        <Zap className="h-5 w-5 text-warning" />
                        <span className="text-sm text-muted">Cache Hit Rate</span>
                      </div>
                      <span className="text-lg font-bold text-foreground">
                        {websiteMetrics.cacheHitRate.toFixed(1)}%
                      </span>
                    </div>

                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <div className="flex items-center gap-3">
                        <Database className="h-5 w-5 text-primary" />
                        <span className="text-sm text-muted">RAG Queries</span>
                      </div>
                      <span className="text-lg font-bold text-foreground">
                        {websiteMetrics.ragQueriesTotal}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="rounded-xl bg-warning-bg p-2.5">
                      <Cpu className="h-5 w-5 text-warning" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground">Resource Usage</h3>
                      <p className="text-xs text-muted">Tokens and cost tracking</p>
                    </div>
                  </div>

                  <div className="space-y-6">
                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <div className="flex items-center gap-3">
                        <HardDrive className="h-5 w-5 text-violet-700 dark:text-lavender" />
                        <span className="text-sm text-muted">Tokens Processed</span>
                      </div>
                      <span className="text-lg font-bold text-foreground">
                        {websiteMetrics.tokensProcessed.toLocaleString()}
                      </span>
                    </div>

                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <div className="flex items-center gap-3">
                        <Brain className="h-5 w-5 text-primary" />
                        <span className="text-sm text-muted">Embedding Requests</span>
                      </div>
                      <span className="text-lg font-bold text-foreground">
                        {websiteMetrics.embeddingRequests}
                      </span>
                    </div>

                    <div className="flex items-center justify-between p-3 rounded-xl bg-success-bg">
                      <div className="flex items-center gap-3">
                        <TrendingUp className="h-5 w-5 text-success" />
                        <span className="text-sm text-muted">Estimated Cost</span>
                      </div>
                      <span className="text-lg font-bold text-success">
                        ${websiteMetrics.totalCost.toFixed(4)}
                      </span>
                    </div>
                  </div>
                </div>
              </section>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Server className="h-16 w-16 text-muted/40 mb-4" />
              <p className="text-muted">
                {websiteMetricsError || "Website metrics are unavailable right now."}
              </p>
              <button
                onClick={fetchPrometheusMetrics}
                className="mt-4 text-sm text-primary hover:text-primary"
              >
                Try again
              </button>
            </div>
          )}
        </div>
      )}

      {/* AWS Services Tab */}
      {activeTab === "aws" && (
        <div className="space-y-6 animate-fade-in-up">
          {/* AWS Header with Refresh and Export */}
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-warning-bg p-2.5">
                <Cloud className="h-5 w-5 text-warning" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground">AWS Infrastructure</h3>
                <p className="text-xs text-muted">
                  Region: {formatOptionalText(awsMetrics?.region)} •
                  {isFiniteMetric(awsMetrics?.summary?.active_services) && isFiniteMetric(awsMetrics?.summary?.total_services)
                    ? `${awsMetrics.summary.active_services}/${awsMetrics.summary.total_services} Services Active`
                    : "Service summary unavailable"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleExportAWS}
                disabled={!awsMetrics}
                className="flex items-center gap-2 rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-surface-2 disabled:opacity-50"
              >
                <Download className="h-4 w-4" />
                Export
              </button>
              <button
                onClick={fetchAWSMetricsData}
                disabled={awsLoading}
                className="flex items-center gap-2 rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-surface-2 disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${awsLoading ? "animate-spin" : ""}`} />
                Refresh
              </button>
            </div>
          </div>

          {awsLoading && !awsMetrics ? (
            <div className="flex items-center justify-center py-16">
              <RefreshCw className="h-8 w-8 text-muted animate-spin" />
            </div>
          ) : awsMetrics ? (
            <>
              {/* AWS Summary Cards */}
              <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  title="Active Services"
                  value={
                    isFiniteMetric(awsMetrics.summary?.active_services) && isFiniteMetric(awsMetrics.summary?.total_services)
                      ? `${awsMetrics.summary.active_services}/${awsMetrics.summary.total_services}`
                      : "Unavailable"
                  }
                  subtitle="AWS services connected"
                  icon={CheckCircle}
                  color="emerald"
                />
                <MetricCard
                  title="Daily Cost"
                  value={
                    isFiniteMetric(awsMetrics.costs?.daily?.total_cost_usd)
                      ? `$${awsMetrics.costs.daily.total_cost_usd.toFixed(4)}`
                      : "Unavailable"
                  }
                  subtitle={formatOptionalText(awsMetrics.costs?.daily?.date)}
                  icon={DollarSign}
                  color="amber"
                />
                <MetricCard
                  title="Tokens Processed"
                  value={formatOptionalInteger(awsMetrics.costs?.daily?.total_tokens)}
                  subtitle="LLM & Embeddings"
                  icon={Cpu}
                  color="indigo"
                />
                <MetricCard
                  title="API Entries"
                  value={formatOptionalInteger(awsMetrics.costs?.daily?.entries)}
                  subtitle="Cost tracking entries"
                  icon={FileText}
                  color="blue"
                />
              </section>

              {/* AWS Services Grid */}
              <section className="grid gap-6 lg:grid-cols-2">
                {/* Bedrock Service */}
                <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                      <div className="rounded-xl bg-lavender/15 p-2.5">
                        <Brain className="h-5 w-5 text-violet-700 dark:text-lavender" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-foreground">Amazon Bedrock</h3>
                        <p className="text-xs text-muted">Foundation Models</p>
                      </div>
                    </div>
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      awsMetrics.services?.bedrock?.status === "active"
                        ? "bg-success-bg text-success"
                        : "bg-danger-bg text-danger"
                    }`}>
                      {awsMetrics.services?.bedrock?.status || "unknown"}
                    </span>
                  </div>

                  {awsMetrics.services?.bedrock?.models && (
                    <div className="space-y-4">
                      {/* LLM Model */}
                      <div className="rounded-xl bg-surface-2 p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-foreground">LLM Model</span>
                          <span className="text-xs text-muted">Primary</span>
                        </div>
                        <p className="text-xs text-muted font-mono truncate">
                          {formatOptionalText(awsMetrics.services.bedrock.models.llm?.model_id)}
                        </p>
                        <div className="mt-2 flex items-center gap-2 text-xs text-muted">
                          <span>
                            Input: {isFiniteMetric(awsMetrics.services.bedrock.models.llm?.pricing?.input_per_1k)
                              ? `$${awsMetrics.services.bedrock.models.llm.pricing.input_per_1k.toFixed(6)}`
                              : "Unavailable"}
                          </span>
                          <span>•</span>
                          <span>
                            Output: {isFiniteMetric(awsMetrics.services.bedrock.models.llm?.pricing?.output_per_1k)
                              ? `$${awsMetrics.services.bedrock.models.llm.pricing.output_per_1k.toFixed(6)}`
                              : "Unavailable"}
                          </span>
                        </div>
                        {awsMetrics.services.bedrock.models.llm?.pricing?.source && (
                          <div className="mt-2 text-[11px] text-muted">
                            Source: {awsMetrics.services.bedrock.models.llm.pricing.source}
                          </div>
                        )}
                      </div>

                      {/* Embedding Model */}
                      <div className="rounded-xl bg-surface-2 p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-foreground">Embedding Model</span>
                          <span className="text-xs text-muted">
                            {isFiniteMetric(awsMetrics.services.bedrock.models.embedding?.dimension)
                              ? `${awsMetrics.services.bedrock.models.embedding.dimension}d`
                              : "Unavailable"}
                          </span>
                        </div>
                        <p className="text-xs text-muted font-mono truncate">
                          {formatOptionalText(awsMetrics.services.bedrock.models.embedding?.model_id)}
                        </p>
                        <div className="mt-2 text-xs text-muted">
                          Input: {isFiniteMetric(awsMetrics.services.bedrock.models.embedding?.pricing?.input_per_1k)
                            ? `$${awsMetrics.services.bedrock.models.embedding.pricing.input_per_1k.toFixed(6)}`
                            : "Unavailable"}
                        </div>
                        {awsMetrics.services.bedrock.models.embedding?.pricing?.source && (
                          <div className="mt-2 text-[11px] text-muted">
                            Source: {awsMetrics.services.bedrock.models.embedding.pricing.source}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* S3 Service */}
                <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                      <div className="rounded-xl bg-success-bg p-2.5">
                        <Box className="h-5 w-5 text-success" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-foreground">Amazon S3</h3>
                        <p className="text-xs text-muted">Object Storage</p>
                      </div>
                    </div>
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      awsMetrics.services?.s3?.status === "active"
                        ? "bg-success-bg text-success"
                        : "bg-warning-bg text-warning"
                    }`}>
                      {awsMetrics.services?.s3?.status || "unknown"}
                    </span>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <span className="text-sm text-muted">Bucket</span>
                      <span className="text-sm font-medium text-foreground font-mono truncate max-w-[200px]">
                        {formatOptionalText(awsMetrics.services?.s3?.bucket)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <span className="text-sm text-muted">Total Objects</span>
                      <span className="text-sm font-medium text-foreground">
                        {formatOptionalInteger(awsMetrics.services?.s3?.total_objects)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <span className="text-sm text-muted">Total Size</span>
                      <span className="text-sm font-medium text-foreground">
                        {formatOptionalMetric(awsMetrics.services?.s3?.total_size_mb, 2, " MB")}
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <span className="text-sm text-muted">Storage Cost</span>
                      <span className="text-sm font-medium text-foreground">
                        {isFiniteMetric(awsMetrics.services?.s3?.pricing?.storage_per_gb_month)
                          ? `$${awsMetrics.services.s3.pricing.storage_per_gb_month.toFixed(6)}/GB/mo`
                          : "Unavailable"}
                      </span>
                    </div>
                    {awsMetrics.services?.s3?.pricing?.source && (
                      <div className="px-1 text-[11px] text-muted">
                        Source: {awsMetrics.services.s3.pricing.source}
                      </div>
                    )}
                  </div>
                </div>

                {/* DynamoDB Service */}
                <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                      <div className="rounded-xl bg-primary-bg p-2.5">
                        <Database className="h-5 w-5 text-primary" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-foreground">Amazon DynamoDB</h3>
                        <p className="text-xs text-muted">NoSQL Database</p>
                      </div>
                    </div>
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      awsMetrics.services?.dynamodb?.status === "active"
                        ? "bg-success-bg text-success"
                        : "bg-warning-bg text-warning"
                    }`}>
                      {awsMetrics.services?.dynamodb?.status || "unknown"}
                    </span>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <span className="text-sm text-muted">Table Name</span>
                      <span className="text-sm font-medium text-foreground font-mono truncate max-w-[200px]">
                        {formatOptionalText(awsMetrics.services?.dynamodb?.table_name)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <span className="text-sm text-muted">Item Count</span>
                      <span className="text-sm font-medium text-foreground">
                        {formatOptionalInteger(awsMetrics.services?.dynamodb?.item_count)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <span className="text-sm text-muted">Table Size</span>
                      <span className="text-sm font-medium text-foreground">
                        {formatOptionalMetric(awsMetrics.services?.dynamodb?.size_mb, 2, " MB")}
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl bg-surface-2">
                      <span className="text-sm text-muted">Billing Mode</span>
                      <span className="text-sm font-medium text-foreground">
                        {formatOptionalText(awsMetrics.services?.dynamodb?.billing_mode)}
                      </span>
                    </div>
                    {awsMetrics.services?.dynamodb?.pricing?.source && (
                      <div className="px-1 text-[11px] text-muted">
                        Source: {awsMetrics.services.dynamodb.pricing.source}
                      </div>
                    )}
                  </div>
                </div>

                {/* STS & CloudWatch */}
                <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="rounded-xl bg-primary-bg p-2.5">
                      <Shield className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground">Identity & Monitoring</h3>
                      <p className="text-xs text-muted">STS & CloudWatch</p>
                    </div>
                  </div>

                  <div className="space-y-4">
                    {/* STS Info */}
                    <div className="rounded-xl bg-surface-2 p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-foreground">AWS Identity</span>
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          awsMetrics.services?.sts?.status === "active"
                            ? "bg-success-bg text-success"
                            : "bg-danger-bg text-danger"
                        }`}>
                          {awsMetrics.services?.sts?.status || "unknown"}
                        </span>
                      </div>
                      <div className="space-y-1 text-xs text-muted">
                        <p>Account: {formatOptionalText(awsMetrics.services?.sts?.account_id)}</p>
                        <p>User: {formatOptionalText(awsMetrics.services?.sts?.arn_suffix)}</p>
                      </div>
                    </div>

                    {/* CloudWatch Info */}
                    <div className="rounded-xl bg-surface-2 p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-foreground">CloudWatch Metrics</span>
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          awsMetrics.services?.cloudwatch?.status === "active"
                            ? "bg-success-bg text-success"
                            : "bg-warning-bg text-warning"
                        }`}>
                          {awsMetrics.services?.cloudwatch?.status || "unknown"}
                        </span>
                      </div>
                      <div className="text-xs text-muted">
                        <p>Bedrock Invocations: {formatOptionalInteger(awsMetrics.services?.cloudwatch?.bedrock_invocations)}</p>
                        <p>Input Tokens: {formatOptionalInteger(awsMetrics.services?.cloudwatch?.bedrock_input_tokens)}</p>
                        <p>Output Tokens: {formatOptionalInteger(awsMetrics.services?.cloudwatch?.bedrock_output_tokens)}</p>
                        <p>Invocation Latency: {formatOptionalMetric(awsMetrics.services?.cloudwatch?.bedrock_invocation_latency_ms, 0, " ms")}</p>
                        {awsMetrics.services?.cloudwatch?.note && (
                          <p className="mt-1 text-warning">{awsMetrics.services?.cloudwatch?.note}</p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              {/* Errors Section */}
              {awsMetrics.errors && awsMetrics.errors.length > 0 && (
                <section className="rounded-2xl border border-danger/30 bg-danger-bg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <AlertTriangle className="h-5 w-5 text-danger" />
                    <h3 className="font-semibold text-danger">AWS Errors</h3>
                  </div>
                  <ul className="space-y-2">
                    {awsMetrics.errors.map((error, idx) => (
                      <li key={idx} className="text-sm text-danger font-mono">
                        {error}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Last Updated */}
              <p className="text-xs text-muted text-center">
                Last updated: {awsMetrics.timestamp ? new Date(awsMetrics.timestamp).toLocaleString() : "N/A"}
              </p>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Cloud className="h-16 w-16 text-muted/40 mb-4" />
              <p className="text-muted">Unable to load AWS metrics</p>
              <button
                onClick={fetchAWSMetricsData}
                className="mt-4 text-sm text-primary hover:text-primary"
              >
                Try again
              </button>
            </div>
          )}
        </div>
      )}

      {/* Test Suite Tab */}
      {activeTab === "tests" && (
        <div className="space-y-6 animate-fade-in-up">
          {/* Summary Cards */}
          {analysis && (
            <section className="grid gap-4 md:grid-cols-3">
              <MetricCard
                title="Avg Response Time"
                value={`${analysis.avg_response_time.toFixed(2)}s`}
                subtitle={`p95: ${analysis.p95_response_time.toFixed(2)}s`}
                icon={Clock}
                color="blue"
              />
              <MetricCard
                title="Topic Coverage"
                value={`${Math.round(analysis.avg_topic_coverage * 100)}%`}
                subtitle={`${Math.round(analysis.coverage_above_80 * 100)}% ≥ 80%`}
                icon={Target}
                color="emerald"
              />
              <MetricCard
                title="Hallucination Rate"
                value={`${Math.round(analysis.generation_summary.hallucination_rate * 100)}%`}
                subtitle={`${analysis.total_tests} tests run`}
                icon={AlertTriangle}
                color={analysis.generation_summary.hallucination_rate > 0.3 ? "red" : "emerald"}
              />
            </section>
          )}

          {/* Test Configuration */}
          <section className="grid gap-6 lg:grid-cols-2">
            <form onSubmit={handleRunSuite} className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
              <div className="flex items-center gap-3 mb-6">
                <div className="rounded-xl bg-primary-bg p-2.5">
                  <Play className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">Run Test Suite</h3>
                  <p className="text-xs text-muted">Configure and execute evaluation tests</p>
                </div>
              </div>

              {loading ? (
                <div className="space-y-4">
                  <div className="h-10 w-full bg-line rounded animate-pulse" />
                  <div className="h-8 w-32 bg-line rounded animate-pulse" />
                </div>
              ) : cases.length === 0 ? (
                <div className="flex flex-col items-center py-8 text-center">
                  <BarChart3 className="h-12 w-12 text-muted/40 mb-3" />
                  <p className="text-sm text-muted">No test cases available</p>
                </div>
              ) : (
                <>
                  <label className="block text-sm font-medium text-foreground mb-4">
                    Number of tests
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={runLimit}
                      onChange={(e) => setRunLimit(Number(e.target.value))}
                      className="mt-2 w-full rounded-xl border border-line bg-surface px-4 py-2.5 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 text-foreground"
                    />
                  </label>

                  {categoryOptions.length > 0 && (
                    <div className="mb-4">
                      <p className="text-sm font-medium text-foreground mb-2">Categories</p>
                      <div className="flex flex-wrap gap-2">
                        {categoryOptions.map((cat) => (
                          <button
                            type="button"
                            key={cat}
                            onClick={() => toggleSelection(cat, selectedCategories, setSelectedCategories)}
                            className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                              selectedCategories.includes(cat)
                                ? "bg-primary-solid text-white"
                                : "bg-surface-2 text-foreground hover:bg-line"
                            }`}
                          >
                            {cat}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {difficultyOptions.length > 0 && (
                    <div className="mb-6">
                      <p className="text-sm font-medium text-foreground mb-2">Difficulty</p>
                      <div className="flex flex-wrap gap-2">
                        {difficultyOptions.map((diff) => (
                          <button
                            type="button"
                            key={diff}
                            onClick={() => toggleSelection(diff, selectedDifficulties, setSelectedDifficulties)}
                            className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                              selectedDifficulties.includes(diff)
                                ? "bg-primary-solid text-white"
                                : "bg-surface-2 text-foreground hover:bg-line"
                            }`}
                          >
                            {diff}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}

              {error && <p className="mb-4 text-sm text-danger">{error}</p>}

              <div className="flex gap-3">
                <button
                  type="submit"
                  disabled={isRunning || cases.length === 0}
                  className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-primary-solid px-4 py-2.5 text-sm font-medium text-white transition hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isRunning ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Running...
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4" />
                      Run Evaluation
                    </>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedCategories([]);
                    setSelectedDifficulties([]);
                    setRunLimit(5);
                  }}
                  className="rounded-xl border border-line bg-surface px-4 py-2.5 text-sm font-medium text-foreground transition hover:bg-surface-2"
                >
                  <RotateCcw className="h-4 w-4" />
                </button>
              </div>
            </form>

            {/* Dataset Preview */}
            <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
              <div className="flex items-center gap-3 mb-6">
                <div className="rounded-xl bg-lavender/15 p-2.5">
                  <Filter className="h-5 w-5 text-violet-700 dark:text-lavender" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">Dataset Preview</h3>
                  <p className="text-xs text-muted">First 5 test cases</p>
                </div>
              </div>

              <div className="space-y-3 max-h-[400px] overflow-y-auto">
                {cases.slice(0, 5).map((testCase) => (
                  <div key={testCase.id} className="rounded-xl border border-line bg-surface-2 p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="inline-flex items-center rounded-full bg-primary-bg px-2 py-0.5 text-xs font-medium text-primary">
                        {testCase.category || "general"}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-foreground">{testCase.query}</p>
                    <p className="mt-1 text-xs text-muted">
                      Topics: {testCase.expected_topics.slice(0, 3).join(", ")}
                      {testCase.expected_topics.length > 3 && ` +${testCase.expected_topics.length - 3} more`}
                    </p>
                  </div>
                ))}
                {cases.length === 0 && (
                  <p className="text-sm text-muted text-center py-4">No test cases loaded</p>
                )}
              </div>
            </div>
          </section>

          {/* Historical Metrics */}
          <section className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="rounded-xl bg-success-bg p-2.5">
                  <TrendingUp className="h-5 w-5 text-success" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">Historical Performance</h3>
                  <p className="text-xs text-muted">Aggregated metrics from logged queries</p>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleRefreshSummary}
                  className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-foreground transition hover:bg-surface-2"
                >
                  <RefreshCw className="h-3 w-3" />
                  Refresh
                </button>
                <button
                  onClick={handleClearLogs}
                  className="flex items-center gap-2 rounded-lg border border-danger/30 bg-surface px-3 py-1.5 text-xs font-medium text-danger transition hover:bg-danger-bg"
                >
                  <Trash2 className="h-3 w-3" />
                  Clear
                </button>
              </div>
            </div>

            {logMessage && <p className="mb-4 text-sm text-muted">{logMessage}</p>}

            {logSummary ? (
              logSummary.error ? (
                <p className="text-sm text-danger">{logSummary.error}</p>
              ) : (
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="rounded-xl bg-surface-2 p-4">
                    <p className="text-xs uppercase tracking-wide text-muted mb-1">Queries Analyzed</p>
                    <p className="text-2xl font-bold text-foreground">{logSummary.total_queries_analyzed ?? 0}</p>
                  </div>
                  <div className="rounded-xl bg-surface-2 p-4">
                    <p className="text-xs uppercase tracking-wide text-muted mb-1">Avg Total Latency</p>
                    <p className="text-2xl font-bold text-foreground">{(logSummary.avg_total_time_seconds ?? 0).toFixed(2)}s</p>
                  </div>
                  <div className="rounded-xl bg-surface-2 p-4">
                    <p className="text-xs uppercase tracking-wide text-muted mb-1">Avg Relevance</p>
                    <p className="text-2xl font-bold text-foreground">{(logSummary.avg_relevance_score ?? 0).toFixed(2)}</p>
                  </div>
                </div>
              )
            ) : (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 text-muted animate-spin" />
              </div>
            )}
          </section>

          {/* Scheduled Evaluation Runs */}
          <section className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="rounded-xl bg-info-bg p-2.5">
                  <Calendar className="h-5 w-5 text-info" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">Scheduled Evaluation Runs</h3>
                  <p className="text-xs text-muted">Dataset evaluations triggered by CI</p>
                </div>
              </div>
              <button
                onClick={handleRefreshRuns}
                className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-foreground transition hover:bg-surface-2"
              >
                <RefreshCw className={`h-3 w-3 ${runsLoading ? "animate-spin" : ""}`} />
                Refresh
              </button>
            </div>

            {runsError && (
              <p className="text-sm text-danger">{runsError}</p>
            )}

            {runsLoading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 text-muted animate-spin" />
              </div>
            ) : evaluationRuns.length === 0 ? (
              <p className="text-sm text-muted">No scheduled runs recorded yet.</p>
            ) : (
              <div className="space-y-4">
                {evaluationRuns.map((run) => {
                  const quality = run.summary?.quality_summary;
                  const drift = run.summary?.drift_summary;
                  const correctness = quality?.avg_correctness;
                  const faithfulness = quality?.avg_faithfulness;
                  const relevance = quality?.avg_answer_relevance;
                  const avgDrift = drift?.avg_drift_score;
                  const delta = run.summary?.delta;
                  return (
                    <div
                      key={run.run_id}
                      className="rounded-xl border border-line bg-surface-2 p-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <p className="text-sm font-semibold text-foreground">
                            {new Date(run.timestamp).toLocaleString()}
                          </p>
                          <p className="text-xs text-muted">
                            {run.dataset} · {run.source}
                          </p>
                        </div>
                        <span className="rounded-full bg-info-bg px-3 py-1 text-xs font-medium text-info">
                          {run.summary?.total_evaluated ?? 0} evaluated
                        </span>
                      </div>

                      <div className="mt-3 grid gap-3 sm:grid-cols-5">
                        <div>
                          <p className="text-[11px] uppercase tracking-wide text-muted">Avg Latency</p>
                          <p className="text-sm font-semibold text-foreground">
                            {formatMetric(run.summary?.avg_latency, 2, "s")}
                          </p>
                          {typeof delta?.avg_latency === "number" && (
                            <p className="text-[11px] text-muted">
                              Δ {delta.avg_latency >= 0 ? "+" : ""}
                              {delta.avg_latency.toFixed(2)}s
                            </p>
                          )}
                        </div>
                        <div>
                          <p className="text-[11px] uppercase tracking-wide text-muted">Correctness</p>
                          <p className={`text-sm font-semibold ${qualityColor(correctness)}`}>
                            {formatMetric(correctness, 2)}
                          </p>
                          {typeof delta?.avg_correctness === "number" && (
                            <p className="text-[11px] text-muted">
                              Δ {delta.avg_correctness >= 0 ? "+" : ""}
                              {delta.avg_correctness.toFixed(2)}
                            </p>
                          )}
                        </div>
                        <div>
                          <p className="text-[11px] uppercase tracking-wide text-muted">Faithfulness</p>
                          <p className={`text-sm font-semibold ${qualityColor(faithfulness)}`}>
                            {formatMetric(faithfulness, 2)}
                          </p>
                          {typeof delta?.avg_faithfulness === "number" && (
                            <p className="text-[11px] text-muted">
                              Δ {delta.avg_faithfulness >= 0 ? "+" : ""}
                              {delta.avg_faithfulness.toFixed(2)}
                            </p>
                          )}
                        </div>
                        <div>
                          <p className="text-[11px] uppercase tracking-wide text-muted">Answer Relevance</p>
                          <p className={`text-sm font-semibold ${qualityColor(relevance)}`}>
                            {formatMetric(relevance, 2)}
                          </p>
                          {typeof delta?.avg_answer_relevance === "number" && (
                            <p className="text-[11px] text-muted">
                              Δ {delta.avg_answer_relevance >= 0 ? "+" : ""}
                              {delta.avg_answer_relevance.toFixed(2)}
                            </p>
                          )}
                        </div>
                        <div>
                          <p className="text-[11px] uppercase tracking-wide text-muted">Avg Drift</p>
                          <p className={`text-sm font-semibold ${driftColor(avgDrift)}`}>
                            {formatMetric(avgDrift, 2)}
                          </p>
                          {typeof delta?.avg_drift_score === "number" && (
                            <p className="text-[11px] text-muted">
                              Δ {delta.avg_drift_score >= 0 ? "+" : ""}
                              {delta.avg_drift_score.toFixed(2)}
                            </p>
                          )}
                        </div>
                      </div>

                      {(run.sample_results?.length > 0 || drift) && (
                        <div className="mt-3">
                          {drift && (
                            <p className="mb-2 text-xs text-muted">
                              Drift baseline: {drift.baseline_path} • {drift.scored_count} scored • {drift.high_drift_count} high-drift prompts
                            </p>
                          )}
                          {run.sample_results?.length > 0 && (
                            <p className="text-xs font-medium text-muted mb-2">
                              Lowest correctness samples
                            </p>
                          )}
                          <ul className="space-y-2">
                            {run.sample_results.slice(0, 3).map((sample, idx) => (
                              <li key={`${run.run_id}-${idx}`} className="text-xs text-muted">
                                <span className="font-semibold text-foreground">
                                  {formatMetric(sample.correctness, 2)}
                                </span>
                                {" · "}
                                {sample.query}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      )}
      {/* Agent Analytics Tab */}
      {activeTab === "agents" && (
        <div className="space-y-6 animate-fade-in-up">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
                <Zap className="h-5 w-5 text-warning" />
                Agent Analytics
              </h2>
              <p className="text-sm text-muted">Multi-agent system performance and usage metrics</p>
            </div>
            <button
              onClick={fetchAgentMetricsData}
              disabled={agentMetricsLoading}
              className="flex items-center gap-2 rounded-lg bg-primary-solid px-4 py-2 text-sm font-medium text-white hover:brightness-110 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${agentMetricsLoading ? "animate-spin" : ""}`} />
              {agentMetricsLoading ? "Loading..." : "Refresh"}
            </button>
          </div>

          {agentMetricsError &&
          (!agentMetrics ||
            (agentMetrics.total_agent_interactions === 0 &&
              Object.keys(agentMetrics.agent_distribution || {}).length === 0)) ? (
            <div className="rounded-xl border border-danger/30 bg-danger-bg p-4 text-sm text-danger">
              {agentMetricsError}
            </div>
          ) : agentMetrics ? (
            <>
              {/* Summary cards */}
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                {[
                  { label: "Total Interactions", value: agentMetrics.total_agent_interactions, icon: Activity, color: "text-primary" },
                  { label: "Unique Users", value: agentMetrics.unique_users, icon: Users, color: "text-success" },
                  { label: "Avg Response Time", value: `${agentMetrics.avg_response_time_ms}ms`, icon: Clock, color: "text-warning" },
                  { label: "Routing Accuracy", value: agentMetrics.routing_accuracy?.positive_after_route == null ? "No ratings yet" : `${agentMetrics.routing_accuracy.positive_after_route}%`, icon: Target, color: "text-violet-700 dark:text-lavender" },
                ].map((card) => (
                  <div key={card.label} className="rounded-xl border border-line bg-surface p-4">
                    <div className="flex items-center gap-2 text-xs text-muted mb-1">
                      <card.icon className={`h-4 w-4 ${card.color}`} />
                      {card.label}
                    </div>
                    <div className="text-2xl font-bold text-foreground">{card.value}</div>
                  </div>
                ))}
              </div>

              {/* Agent distribution + Response times */}
              <div className="grid gap-6 md:grid-cols-2">
                <section className="rounded-xl border border-line bg-surface p-6">
                  <h3 className="mb-4 text-sm font-semibold text-foreground">Agent Distribution</h3>
                  {Object.keys(agentMetrics.agent_distribution || {}).length > 0 ? (
                    <ResponsiveContainer width="100%" height={250}>
                      <PieChart>
                        <Pie
                          data={Object.entries(agentMetrics.agent_distribution).map(([name, value]) => ({ name: name.replace("_agent", ""), value }))}
                          cx="50%" cy="50%" outerRadius={90}
                          dataKey="value" label={({ name, percent }: { name?: string; percent?: number }) => `${name ?? ""} ${((percent ?? 0) * 100).toFixed(0)}%`}
                        >
                          {Object.keys(agentMetrics.agent_distribution).map((_, i) => (
                            <Cell key={i} fill={["var(--color-primary)", "var(--color-secondary)", "var(--color-bright)", "var(--color-lavender)", "var(--color-accent)", "var(--color-danger)"][i % 6]} />
                          ))}
                        </Pie>
                        <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : <p className="text-sm text-muted text-center py-8">No data yet</p>}
                </section>

                <section className="rounded-xl border border-line bg-surface p-6">
                  <h3 className="mb-4 text-sm font-semibold text-foreground">Response Time by Agent</h3>
                  {Object.keys(agentMetrics.response_time_by_agent || {}).length > 0 ? (
                    <ResponsiveContainer width="100%" height={250}>
                      <BarChart data={Object.entries(agentMetrics.response_time_by_agent).map(([name, ms]) => ({ name: name.replace("_agent", ""), ms }))}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                        <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                        <YAxis tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                        <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                        <Bar dataKey="ms" fill="var(--color-accent)" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : <p className="text-sm text-muted text-center py-8">No data yet</p>}
                </section>
              </div>

              {/* Daily usage area chart */}
              {(agentMetrics.daily_usage?.length ?? 0) > 0 && (
                <section className="rounded-xl border border-line bg-surface p-6">
                  <h3 className="mb-4 text-sm font-semibold text-foreground">Daily Usage (14 days)</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <AreaChart data={agentMetrics.daily_usage}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} />
                      <YAxis tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                      <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                      <Area type="monotone" dataKey="count" stroke="var(--color-primary)" fill="var(--color-primary)" fillOpacity={0.2} name="Interactions" />
                      <Area type="monotone" dataKey="unique_users" stroke="var(--color-secondary)" fill="var(--color-secondary)" fillOpacity={0.2} name="Unique Users" />
                      <Legend />
                    </AreaChart>
                  </ResponsiveContainer>
                </section>
              )}

              {/* Top query types */}
              {(agentMetrics.top_query_types?.length ?? 0) > 0 && (
                <section className="rounded-xl border border-line bg-surface p-6">
                  <h3 className="mb-4 text-sm font-semibold text-foreground">Top Query Types</h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={agentMetrics.top_query_types} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                      <XAxis type="number" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                      <YAxis type="category" dataKey="type" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} width={140} />
                      <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                      <Bar dataKey="count" fill="var(--color-lavender)" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </section>
              )}
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-muted">
              <Zap className="h-12 w-12 mb-3 opacity-30" />
              <p className="text-sm">Click Refresh to load agent metrics</p>
            </div>
          )}
        </div>
      )}

      {/* Knowledge Graph Tab */}
      {activeTab === "graph" && (
        <div className="space-y-6 animate-fade-in-up">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
                <GitBranch className="h-5 w-5 text-info" />
                Knowledge Graph
              </h2>
              <p className="text-sm text-muted">Neo4j graph database metrics and student learning patterns</p>
            </div>
            <button
              onClick={fetchGraphMetricsData}
              disabled={graphMetricsLoading}
              className="flex items-center gap-2 rounded-lg bg-primary-solid px-4 py-2 text-sm font-medium text-white hover:brightness-110 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${graphMetricsLoading ? "animate-spin" : ""}`} />
              {graphMetricsLoading ? "Loading..." : "Refresh"}
            </button>
          </div>

          {graphMetricsError &&
          (!graphMetrics ||
            (graphMetrics.total_nodes === 0 &&
              graphMetrics.total_relationships === 0 &&
              Object.keys(graphMetrics.nodes_by_type || {}).length === 0 &&
              Object.keys(graphMetrics.relationships_by_type || {}).length === 0)) ? (
            <div className="rounded-xl border border-danger/30 bg-danger-bg p-4 text-sm text-danger">
              {graphMetricsError}
            </div>
          ) : graphMetrics ? (
            <>
              {/* Summary cards */}
              <div className="grid grid-cols-2 gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-line bg-surface p-4">
                  <div className="flex items-center gap-2 text-xs text-muted mb-1">
                    <Database className="h-4 w-4 text-info" /> Total Nodes
                  </div>
                  <div className="text-2xl font-bold text-foreground">{graphMetrics.total_nodes}</div>
                </div>
                <div className="rounded-xl border border-line bg-surface p-4">
                  <div className="flex items-center gap-2 text-xs text-muted mb-1">
                    <GitBranch className="h-4 w-4 text-violet-700 dark:text-lavender" /> Total Relationships
                  </div>
                  <div className="text-2xl font-bold text-foreground">{graphMetrics.total_relationships}</div>
                </div>
              </div>

              {/* Nodes by type + Relationships by type */}
              <div className="grid gap-6 md:grid-cols-2">
                <section className="rounded-xl border border-line bg-surface p-6">
                  <h3 className="mb-4 text-sm font-semibold text-foreground">Nodes by Type</h3>
                  {Object.keys(graphMetrics.nodes_by_type || {}).length > 0 ? (
                    <ResponsiveContainer width="100%" height={250}>
                      <PieChart>
                        <Pie
                          data={Object.entries(graphMetrics.nodes_by_type).map(([name, value]) => ({ name, value }))}
                          cx="50%" cy="50%" outerRadius={90} innerRadius={40}
                          dataKey="value" label={({ name, value }) => `${name}: ${value}`}
                        >
                          {Object.keys(graphMetrics.nodes_by_type).map((_, i) => (
                            <Cell key={i} fill={["var(--color-primary)", "var(--color-secondary)", "var(--color-bright)", "var(--color-lavender)", "var(--color-accent)"][i % 5]} />
                          ))}
                        </Pie>
                        <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : <p className="text-sm text-muted text-center py-8">No data yet</p>}
                </section>

                <section className="rounded-xl border border-line bg-surface p-6">
                  <h3 className="mb-4 text-sm font-semibold text-foreground">Relationships by Type</h3>
                  {Object.keys(graphMetrics.relationships_by_type || {}).length > 0 ? (
                    <ResponsiveContainer width="100%" height={250}>
                      <BarChart data={Object.entries(graphMetrics.relationships_by_type).map(([name, count]) => ({ name, count }))}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                        <XAxis dataKey="name" tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} angle={-30} textAnchor="end" height={60} />
                        <YAxis tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                        <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                        <Bar dataKey="count" fill="var(--color-bright)" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : <p className="text-sm text-muted text-center py-8">No data yet</p>}
                </section>
              </div>

              {/* Most struggled concepts + Most studied topics */}
              <div className="grid gap-6 md:grid-cols-2">
                <section className="rounded-xl border border-line bg-surface p-6">
                  <h3 className="mb-4 text-sm font-semibold text-foreground flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-danger" /> Most Struggled Concepts
                  </h3>
                  {(graphMetrics.most_struggled_concepts?.length ?? 0) > 0 ? (
                    <div className="space-y-2">
                      {graphMetrics.most_struggled_concepts.map((item, i) => (
                        <div key={i} className="flex items-center justify-between rounded-lg bg-surface-2 px-3 py-2">
                          <span className="text-sm text-foreground capitalize">{item.concept}</span>
                          <span className="text-xs font-medium text-danger">{item.students} students</span>
                        </div>
                      ))}
                    </div>
                  ) : <p className="text-sm text-muted text-center py-4">No data yet</p>}
                </section>

                <section className="rounded-xl border border-line bg-surface p-6">
                  <h3 className="mb-4 text-sm font-semibold text-foreground flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-success" /> Most Studied Topics
                  </h3>
                  {(graphMetrics.most_studied_topics?.length ?? 0) > 0 ? (
                    <div className="space-y-2">
                      {graphMetrics.most_studied_topics.map((item, i) => (
                        <div key={i} className="flex items-center justify-between rounded-lg bg-surface-2 px-3 py-2">
                          <span className="text-sm text-foreground capitalize">{item.topic}</span>
                          <span className="text-xs font-medium text-success">{item.study_count} studies</span>
                        </div>
                      ))}
                    </div>
                  ) : <p className="text-sm text-muted text-center py-4">No data yet</p>}
                </section>
              </div>

              {/* Student engagement table */}
              {(graphMetrics.student_engagement?.length ?? 0) > 0 && (
                <section className="rounded-xl border border-line bg-surface p-6">
                  <h3 className="mb-4 text-sm font-semibold text-foreground flex items-center gap-2">
                    <Users className="h-4 w-4 text-primary" /> Student Engagement
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-line text-xs text-muted">
                          <th className="text-left py-2 px-3">Student</th>
                          <th className="text-right py-2 px-3">Queries</th>
                          <th className="text-right py-2 px-3">Sessions</th>
                          <th className="text-right py-2 px-3">Doubts</th>
                        </tr>
                      </thead>
                      <tbody>
                        {graphMetrics.student_engagement.map((s, i) => (
                          <tr key={i} className="border-b border-line">
                            <td className="py-2 px-3 text-foreground">{s.username}</td>
                            <td className="py-2 px-3 text-right text-muted">{s.queries}</td>
                            <td className="py-2 px-3 text-right text-muted">{s.sessions}</td>
                            <td className="py-2 px-3 text-right text-muted">{s.doubts}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              {/* Feedback sentiment */}
              {Object.keys(graphMetrics.feedback_sentiment_overview || {}).length > 0 && (
                <section className="rounded-xl border border-line bg-surface p-6">
                  <h3 className="mb-4 text-sm font-semibold text-foreground">Feedback Sentiment</h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie
                        data={Object.entries(graphMetrics.feedback_sentiment_overview).map(([name, value]) => ({ name, value }))}
                        cx="50%" cy="50%" outerRadius={70}
                        dataKey="value" label
                      >
                        {Object.keys(graphMetrics.feedback_sentiment_overview).map((sentiment, i) => (
                          <Cell key={i} fill={sentiment === "positive" ? "var(--color-success)" : sentiment === "negative" ? "var(--color-danger)" : "var(--color-text-muted)"} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </section>
              )}
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-muted">
              <GitBranch className="h-12 w-12 mb-3 opacity-30" />
              <p className="text-sm">Click Refresh to load knowledge graph metrics</p>
            </div>
          )}
        </div>
      )}

      {/* Quiz Analytics Tab */}
      {activeTab === "quiz" && (
        <div className="space-y-6 animate-fade-in-up">
          {/* Quiz Header */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
                <Target className="h-5 w-5 text-violet-700 dark:text-lavender" />
                Quiz Analytics
              </h2>
              <p className="text-sm text-muted">Student quiz performance across all users</p>
            </div>
            <button
              onClick={fetchQuizMetricsData}
              disabled={quizMetricsLoading}
              className="flex items-center gap-2 rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-surface-2 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${quizMetricsLoading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>

          {quizMetricsLoading && !quizMetrics ? (
            <div className="flex items-center justify-center py-16">
              <RefreshCw className="h-8 w-8 text-muted animate-spin" />
            </div>
          ) : quizMetrics?.error && !quizMetrics.total_quizzes ? (
            <div className="rounded-xl bg-danger-bg border border-danger/30 p-4 text-sm text-danger">
              {quizMetrics.error}
            </div>
          ) : quizMetrics ? (
            <>
              {/* Summary Cards */}
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  { label: "Total Quizzes", value: quizMetrics.total_quizzes, icon: FileText, color: "text-violet-700 dark:text-lavender", bg: "bg-lavender/15" },
                  { label: "Unique Students", value: quizMetrics.unique_users, icon: Brain, color: "text-primary", bg: "bg-primary-bg" },
                  { label: "Avg Score", value: `${quizMetrics.avg_percentage.toFixed(1)}%`, icon: Target, color: "text-success", bg: "bg-success-bg" },
                  { label: "Questions Answered", value: quizMetrics.total_questions_answered ?? 0, icon: CheckCircle, color: "text-warning", bg: "bg-warning-bg" },
                ].map((card) => (
                  <div key={card.label} className="rounded-xl border border-line bg-surface p-5">
                    <div className="flex items-center gap-3 mb-2">
                      <div className={`p-2 rounded-lg ${card.bg}`}>
                        <card.icon className={`h-4 w-4 ${card.color}`} />
                      </div>
                      <span className="text-xs font-medium text-muted uppercase tracking-wider">{card.label}</span>
                    </div>
                    <p className="text-2xl font-bold text-foreground">{card.value}</p>
                  </div>
                ))}
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                {/* Score Distribution */}
                <section className="rounded-xl border border-line bg-surface p-5">
                  <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-violet-700 dark:text-lavender" />
                    Score Distribution
                  </h3>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={
                        ["0-20", "20-40", "40-60", "60-80", "80-100"].map((bucket) => ({
                          range: bucket + "%",
                          count: quizMetrics.score_distribution[bucket] ?? 0,
                        }))
                      }>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                        <XAxis dataKey="range" tick={{ fontSize: 12, fill: "var(--color-text-muted)" }} />
                        <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "var(--color-text-muted)" }} />
                        <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                        <Bar dataKey="count" fill="var(--color-lavender)" radius={[4, 4, 0, 0]} name="Quizzes" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </section>

                {/* Recent Activity */}
                <section className="rounded-xl border border-line bg-surface p-5">
                  <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                    <Activity className="h-4 w-4 text-primary" />
                    Last 7 Days Activity
                  </h3>
                  {quizMetrics.recent_activity.length > 0 ? (
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={quizMetrics.recent_activity.map((d) => ({
                          date: new Date(d.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
                          quizzes: d.count,
                          avg_score: d.avg_score,
                        }))}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                          <XAxis dataKey="date" tick={{ fontSize: 12, fill: "var(--color-text-muted)" }} />
                          <YAxis tick={{ fontSize: 12, fill: "var(--color-text-muted)" }} />
                          <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                          <Legend />
                          <Area type="monotone" dataKey="quizzes" stroke="var(--color-lavender)" fill="var(--color-lavender)" fillOpacity={0.2} name="Quizzes" />
                          <Area type="monotone" dataKey="avg_score" stroke="var(--color-secondary)" fill="var(--color-secondary)" fillOpacity={0.1} name="Avg Score %" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-64 text-sm text-muted">No quiz activity in the last 7 days</div>
                  )}
                </section>
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                {/* Popular Topics */}
                <section className="rounded-xl border border-line bg-surface p-5">
                  <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-success" />
                    Popular Topics
                  </h3>
                  {quizMetrics.popular_topics.length > 0 ? (
                    <div className="space-y-3">
                      {quizMetrics.popular_topics.map((topic, i) => {
                        const maxCount = quizMetrics.popular_topics[0]?.quiz_count || 1;
                        const pct = (topic.quiz_count / maxCount) * 100;
                        const label = topic.folder.split("/").pop() || topic.folder;
                        return (
                          <div key={topic.folder}>
                            <div className="flex items-center justify-between text-sm mb-1">
                              <span className="font-medium text-foreground truncate max-w-[200px]">{label}</span>
                              <span className="text-muted">{topic.quiz_count} quizzes</span>
                            </div>
                            <div className="h-2 rounded-full bg-surface-2 overflow-hidden">
                              <div className="h-full rounded-full bg-gradient-to-r from-[#1E3A8A] to-[#0D9488] dark:from-[#3B82F6] dark:to-[#14B8A6]" style={{ width: `${pct}%` }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-sm text-muted text-center py-8">No topic data available</div>
                  )}
                </section>

                {/* Top Performers */}
                <section className="rounded-xl border border-line bg-surface p-5">
                  <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                    <Zap className="h-4 w-4 text-warning" />
                    Top Performers
                  </h3>
                  {quizMetrics.top_performers.length > 0 ? (
                    <div className="space-y-3">
                      {quizMetrics.top_performers.map((performer, i) => (
                        <div key={performer.username} className="flex items-center gap-3 p-3 rounded-lg bg-surface-2">
                          <span className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                            i === 0 ? "bg-warning-bg text-warning" :
                            i === 1 ? "bg-line text-muted" :
                            i === 2 ? "bg-warning-bg text-warning" :
                            "bg-surface-2 text-muted"
                          }`}>
                            {i + 1}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-foreground truncate">{performer.username}</p>
                            <p className="text-xs text-muted">{performer.quizzes_taken} quizzes</p>
                          </div>
                          <span className={`text-sm font-bold ${
                            performer.avg_score >= 80 ? "text-success" :
                            performer.avg_score >= 60 ? "text-warning" :
                            "text-danger"
                          }`}>
                            {performer.avg_score}%
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-muted text-center py-8">No quiz data available</div>
                  )}
                </section>
              </div>
            </>
          ) : null}
        </div>
      )}
    </PageShell>
  );
}

// Default export: admin gate — redirects admins to /admin/evaluation, shows access denied to non-admins
export default function EvaluationPage() {
  const { isAdmin, isLoading } = useUser();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAdmin) {
      router.replace("/admin/evaluation");
    }
  }, [isLoading, isAdmin, router]);

  if (isLoading) {
    return (
      <PageShell>
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-primary" />
        </div>
      </PageShell>
    );
  }

  if (isAdmin) {
    return (
      <PageShell>
        <div className="flex flex-col items-center justify-center gap-3 py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-primary" />
          <p className="text-sm text-muted">Redirecting to admin dashboard…</p>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell>
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <Lock className="h-12 w-12 text-muted/40" />
        <h2 className="text-xl font-bold text-foreground">Admin Only</h2>
        <p className="max-w-md text-center text-sm text-muted">
          The Evaluation Dashboard is restricted to administrators. Please contact an admin if you need access.
        </p>
      </div>
    </PageShell>
  );
}
