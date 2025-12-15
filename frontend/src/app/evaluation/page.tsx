"use client";

import { useEffect, useMemo, useState } from "react";
import {
  clearEvaluationLogs,
  EvaluationAnalysis,
  EvaluationCase,
  EvaluationLogSummary,
  EvaluationResult,
  fetchEvaluationCases,
  fetchEvaluationLogSummary,
  runEvaluationSuite,
} from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { PageShell } from "@/components/page-shell";

export default function EvaluationDashboard() {
  const { token } = useAuthToken();
  const [cases, setCases] = useState<EvaluationCase[]>([]);
  const [analysis, setAnalysis] = useState<EvaluationAnalysis | null>(null);
  const [results, setResults] = useState<EvaluationResult[]>([]);
  const [logSummary, setLogSummary] = useState<EvaluationLogSummary | null>(null);
  const [runLimit, setRunLimit] = useState(5);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedDifficulties, setSelectedDifficulties] = useState<string[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logMessage, setLogMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetchEvaluationCases({ token })
      .then((data) => {
        if (!cancelled) {
          setCases(data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to load cases");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetchEvaluationLogSummary(token)
      .then((summary) => {
        if (!cancelled) {
          setLogSummary(summary);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setLogSummary({ error: err instanceof Error ? err.message : "Unable to load summary" });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

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

  return (
    <PageShell contentClassName="gap-8">
      <header className="space-y-2">
        <p className="text-xs uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-400">Evaluation</p>
        <h1 className="text-3xl font-semibold text-zinc-950 dark:text-white">RAG test harness</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Test and evaluate the Retrieval-Augmented Generation (RAG) pipeline performance.
        </p>
      </header>

      {analysis && (
        <section className="grid gap-4 md:grid-cols-3">
          {[{
            label: "Avg response time",
            value: `${analysis.avg_response_time.toFixed(2)}s`,
            sub: `p95 ${analysis.p95_response_time.toFixed(2)}s`,
          },
          {
            label: "Topic coverage",
            value: `${Math.round(analysis.avg_topic_coverage * 100)}%`,
            sub: `${Math.round(analysis.coverage_above_80 * 100)}% ≥ 0.8 coverage`,
          },
          {
            label: "Hallucination rate",
            value: `${Math.round(analysis.generation_summary.hallucination_rate * 100)}%`,
            sub: `${analysis.total_tests} tests run`,
          }].map((card) => (
            <div key={card.label} className="rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <p className="text-xs uppercase tracking-[0.25em] text-zinc-500 dark:text-zinc-400">{card.label}</p>
              <p className="pt-2 text-2xl font-semibold text-zinc-950 dark:text-white">{card.value}</p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">{card.sub}</p>
            </div>
          ))}
        </section>
      )}

      <section className="grid gap-6 lg:grid-cols-2">
        <form onSubmit={handleRunSuite} className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-xs uppercase tracking-[0.3em] text-zinc-500 dark:text-zinc-400">Run suite</p>
          <h2 className="pt-2 text-xl font-semibold text-zinc-950 dark:text-white">Configure filters</h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Pick a subset of dataset cases to evaluate.</p>

          <label className="mt-5 block text-sm font-medium text-zinc-800 dark:text-zinc-200">
            Number of tests
            <input
              type="number"
              min={1}
              max={100}
              value={runLimit}
              onChange={(event) => setRunLimit(Number(event.target.value))}
              className="mt-2 w-full rounded-2xl border border-zinc-200 px-4 py-2 text-base focus:border-zinc-900 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:focus:border-zinc-500"
            />
          </label>

          {categoryOptions.length > 0 && (
            <div className="mt-5">
              <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Categories</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {categoryOptions.map((category) => (
                  <button
                    type="button"
                    key={category}
                    onClick={() => toggleSelection(category, selectedCategories, setSelectedCategories)}
                    className={`rounded-full border px-4 py-1 text-sm ${
                      selectedCategories.includes(category)
                        ? "border-zinc-900 bg-zinc-900 text-white dark:border-white dark:bg-white dark:text-zinc-900"
                        : "border-zinc-200 text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
                    }`}
                  >
                    {category}
                  </button>
                ))}
              </div>
            </div>
          )}

          {difficultyOptions.length > 0 && (
            <div className="mt-5">
              <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Difficulty</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {difficultyOptions.map((difficulty) => (
                  <button
                    type="button"
                    key={difficulty}
                    onClick={() => toggleSelection(difficulty, selectedDifficulties, setSelectedDifficulties)}
                    className={`rounded-full border px-4 py-1 text-sm ${
                      selectedDifficulties.includes(difficulty)
                        ? "border-zinc-900 bg-zinc-900 text-white dark:border-white dark:bg-white dark:text-zinc-900"
                        : "border-zinc-200 text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
                    }`}
                  >
                    {difficulty}
                  </button>
                ))}
              </div>
            </div>
          )}

          {error && <p className="mt-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={isRunning}
              className="rounded-full bg-zinc-900 px-5 py-2 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-zinc-900"
            >
              {isRunning ? "Running…" : "Run evaluation"}
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedCategories([]);
                setSelectedDifficulties([]);
                setRunLimit(5);
              }}
              className="rounded-full border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
            >
              Reset
            </button>
          </div>
        </form>

        <div className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-xs uppercase tracking-[0.3em] text-zinc-500 dark:text-zinc-400">Dataset preview</p>
          <h2 className="pt-2 text-xl font-semibold text-zinc-950 dark:text-white">Latest configured cases</h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Showing the first five prompts from the evaluation dataset.</p>
          <ul className="mt-4 space-y-4">
            {cases.slice(0, 5).map((testCase) => (
              <li key={testCase.id} className="rounded-2xl border border-zinc-100 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-800/50">
                <p className="text-xs uppercase tracking-[0.25em] text-zinc-500 dark:text-zinc-400">{testCase.category || "general"}</p>
                <p className="pt-1 font-semibold text-zinc-900 dark:text-white">{testCase.query}</p>
                <p className="pt-1 text-xs text-zinc-500 dark:text-zinc-400">
                  Difficulty: {testCase.difficulty || "n/a"} · Topics: {testCase.expected_topics.join(", ")}
                </p>
              </li>
            ))}
            {cases.length === 0 && <p className="text-sm text-zinc-500 dark:text-zinc-400">No cases detected. Upload evaluation_dataset.json.</p>}
          </ul>
        </div>
      </section>

      <section className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-zinc-500 dark:text-zinc-400">Metrics log</p>
            <h2 className="pt-1 text-xl font-semibold text-zinc-950 dark:text-white">Historical performance</h2>
          </div>
          <div className="flex gap-2 text-sm">
            <button onClick={handleRefreshSummary} className="rounded-full border border-zinc-200 px-4 py-2 font-medium text-zinc-700 dark:border-zinc-700 dark:text-zinc-300">
              Refresh
            </button>
            <button onClick={handleClearLogs} className="rounded-full border border-red-200 px-4 py-2 font-medium text-red-600 dark:border-red-800 dark:text-red-400">
              Clear logs
            </button>
          </div>
        </div>
        {logMessage && <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">{logMessage}</p>}
        {logSummary ? (
          logSummary.error ? (
            <p className="mt-4 text-sm text-red-600 dark:text-red-400">{logSummary.error}</p>
          ) : (
            <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="rounded-2xl border border-zinc-100 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-800/50">
                <dt className="text-xs uppercase tracking-[0.25em] text-zinc-500 dark:text-zinc-400">Queries</dt>
                <dd className="pt-1 text-2xl font-semibold text-zinc-950 dark:text-white">{logSummary.total_queries_analyzed ?? 0}</dd>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Logged entries</p>
              </div>
              <div className="rounded-2xl border border-zinc-100 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-800/50">
                <dt className="text-xs uppercase tracking-[0.25em] text-zinc-500 dark:text-zinc-400">Avg latency</dt>
                <dd className="pt-1 text-2xl font-semibold text-zinc-950 dark:text-white">{(logSummary.avg_total_time_seconds ?? 0).toFixed(2)}s</dd>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Retrieval + generation</p>
              </div>
              <div className="rounded-2xl border border-zinc-100 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-800/50">
                <dt className="text-xs uppercase tracking-[0.25em] text-zinc-500 dark:text-zinc-400">Avg relevance</dt>
                <dd className="pt-1 text-2xl font-semibold text-zinc-950 dark:text-white">{(logSummary.avg_relevance_score ?? 0).toFixed(2)}</dd>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Retriever scores</p>
              </div>
            </dl>
          )
        ) : (
          <p className="mt-4 text-sm text-zinc-500 dark:text-zinc-400">Loading summary…</p>
        )}
      </section>

      {results.length > 0 && (
        <section className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-xs uppercase tracking-[0.3em] text-zinc-500 dark:text-zinc-400">Latest run</p>
          <h2 className="pt-1 text-xl font-semibold text-zinc-950 dark:text-white">Detailed results</h2>
          <div className="mt-6 space-y-5">
            {results.map((result) => (
              <article key={result.test_id} className="rounded-2xl border border-zinc-100 bg-zinc-50 p-5 dark:border-zinc-800 dark:bg-zinc-800/50">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.25em] text-zinc-500 dark:text-zinc-400">{result.category || "general"}</p>
                    <h3 className="text-lg font-semibold text-zinc-950 dark:text-white">{result.query}</h3>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">Difficulty: {result.difficulty || "n/a"} • {result.total_time}s</p>
                  </div>
                  <div className="flex gap-4 text-right text-sm">
                    <div>
                      <p className="text-xs uppercase text-zinc-500 dark:text-zinc-400">Coverage</p>
                      <p className="text-lg font-semibold text-zinc-900 dark:text-white">
                        {Math.round(result.generation_metrics.topic_coverage * 100)}%
                      </p>
                    </div>
                    <div>
                      <p className="text-xs uppercase text-zinc-500 dark:text-zinc-400">Recall@3</p>
                      <p className="text-lg font-semibold text-zinc-900 dark:text-white">
                        {(result.retrieval_metrics.recall_at_3 * 100).toFixed(0)}%
                      </p>
                    </div>
                  </div>
                </div>
                <p className="mt-3 text-sm text-zinc-700 line-clamp-4 dark:text-zinc-300">{result.response}</p>
                <div className="mt-4 grid gap-3 text-xs text-zinc-600 dark:text-zinc-400 md:grid-cols-2">
                  <div>
                    <p className="font-semibold text-zinc-800 dark:text-zinc-200">Retrieved topics</p>
                    <p>{result.retrieval_metrics.topics_found.join(", ") || "None"}</p>
                  </div>
                  <div>
                    <p className="font-semibold text-zinc-800 dark:text-zinc-200">Missing topics</p>
                    <p>{result.retrieval_metrics.missing_topics.join(", ") || "None"}</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
    </PageShell>
  );
}
