"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  QuizFolder,
  QuizQuestion,
  QuizHistoryEntry,
  fetchQuizFolders,
  fetchQuizHistory,
  generateQuiz,
  submitQuiz,
} from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { PageShell } from "@/components/page-shell";

export default function QuizPage() {
  const { token } = useAuthToken();
  const [folders, setFolders] = useState<QuizFolder[]>([]);
  const [selectedFolders, setSelectedFolders] = useState<string[]>([]);
  const [numQuestions, setNumQuestions] = useState(3);
  const [loadingFolders, setLoadingFolders] = useState(true);
  const [foldersError, setFoldersError] = useState<string | null>(null);

  const [quiz, setQuiz] = useState<{
    quiz_id: string;
    selected_folders: string[];
    questions: QuizQuestion[];
  } | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<QuizHistoryEntry | null>(null);
  const [history, setHistory] = useState<QuizHistoryEntry[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let mounted = true;
    setLoadingFolders(true);
    fetchQuizFolders(token)
      .then((data) => {
        if (!mounted) return;
        setFolders(data);
        setFoldersError(null);
        if (data.length > 0) {
          setSelectedFolders([data[0].path]);
        }
      })
      .catch((error) => {
        if (!mounted) return;
        setFoldersError(error instanceof Error ? error.message : "Failed to load folders");
      })
      .finally(() => mounted && setLoadingFolders(false));

    fetchQuizHistory(token)
      .then((res) => mounted && setHistory(res.results || []))
      .catch(() => {});

    return () => {
      mounted = false;
    };
  }, [token]);

  const resolvedFolderLabels = useMemo(() => {
    const lookup = new Map(folders.map((f) => [f.path, f.label]));
    const source = quiz ? quiz.selected_folders : selectedFolders;
    return source.map((path) => lookup.get(path) || path);
  }, [folders, quiz, selectedFolders]);

  function toggleFolder(path: string) {
    setSelectedFolders((prev) =>
      prev.includes(path) ? prev.filter((folder) => folder !== path) : [...prev, path]
    );
  }

  async function handleGenerate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    if (selectedFolders.length === 0) {
      setActionError("Select at least one folder to generate a quiz.");
      return;
    }
    setActionError(null);
    setIsGenerating(true);
    setResult(null);
    try {
      const payload = await generateQuiz({
        token,
        folders: selectedFolders,
        numQuestions,
      });
      setQuiz({
        quiz_id: payload.quiz_id,
        selected_folders: payload.selected_folders,
        questions: payload.questions,
      });
      setAnswers({});
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to generate quiz");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleSubmit() {
    if (!token || !quiz) return;
    setIsSubmitting(true);
    setActionError(null);
    try {
      const response = await submitQuiz({
        token,
        payload: {
          quiz_id: quiz.quiz_id,
          selected_folders: quiz.selected_folders,
          questions: quiz.questions,
          answers,
        },
      });
      setResult(response.result);
      setHistory((prev) => [response.result, ...prev]);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to submit quiz");
    } finally {
      setIsSubmitting(false);
    }
  }

  const answeredCount = useMemo(
    () => (quiz ? quiz.questions.filter((q) => answers[q.id]).length : 0),
    [quiz, answers]
  );

  return (
    <PageShell contentClassName="gap-10">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-400">Quiz Generator</p>
            <h1 className="pt-2 text-3xl font-semibold text-zinc-950 dark:text-white">Master the course material</h1>
          </div>
          <Link
            href="/"
            className="inline-flex items-center justify-center rounded-full border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
          >
            ← Back to home
          </Link>
        </header>

        <section className="grid gap-6 lg:grid-cols-3">
          <form
            onSubmit={handleGenerate}
            className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm lg:col-span-2 dark:border-zinc-800 dark:bg-zinc-900"
          >
            {foldersError && (
              <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400">
                {foldersError}
              </div>
            )}

            <div className="space-y-2">
              <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Select folders</p>
              {loadingFolders && <p className="text-xs text-zinc-500 dark:text-zinc-400">Loading folders…</p>}
              {!loadingFolders && folders.length === 0 && (
                <p className="text-xs text-red-600 dark:text-red-400">No folders found in the knowledge base.</p>
              )}
              <div className="grid gap-2 sm:grid-cols-2">
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
              </div>
            </div>

            <div className="mt-6 space-y-2">
              <label htmlFor="numQuestions" className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
                Number of questions
              </label>
              <input
                id="numQuestions"
                type="range"
                min={1}
                max={10}
                value={numQuestions}
                onChange={(event) => setNumQuestions(Number(event.target.value))}
                className="w-full"
              />
              <p className="text-sm text-zinc-600 dark:text-zinc-400">Generating {numQuestions} questions</p>
            </div>

            {actionError && (
              <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400">
                {actionError}
              </div>
            )}

            <button
              type="submit"
              disabled={isGenerating || selectedFolders.length === 0}
              className="mt-6 w-full rounded-full bg-zinc-900 px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-zinc-900"
            >
              {isGenerating ? "Building quiz…" : "Generate quiz"}
            </button>
          </form>

          <aside className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Recent attempts</p>
            <div className="mt-4 space-y-3 text-sm text-zinc-600 dark:text-zinc-400">
              {history.slice(0, 4).map((attempt, index) => (
                <div
                  key={`${attempt.id}-${attempt.created_at ?? index}`}
                  className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-800/50"
                >
                  <p className="font-medium text-zinc-900 dark:text-white">
                    {attempt.score}/{attempt.total_questions} ({attempt.percentage.toFixed(1)}%)
                  </p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    {new Date(attempt.created_at).toLocaleString()}
                  </p>
                </div>
              ))}
              {history.length === 0 && <p className="text-xs text-zinc-500 dark:text-zinc-400">No attempts yet.</p>}
            </div>
          </aside>
        </section>

        {quiz && (
          <section className="rounded-3xl border border-zinc-200 bg-white p-8 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex flex-col gap-2 border-b border-zinc-100 pb-4 sm:flex-row sm:items-center sm:justify-between dark:border-zinc-800">
              <div>
                <p className="text-xs uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-400">Active quiz</p>
                <h2 className="text-2xl font-semibold text-zinc-900 dark:text-white">
                  {resolvedFolderLabels.join(", ")}
                </h2>
              </div>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                Answered {answeredCount}/{quiz.questions.length}
              </p>
            </div>

            <div className="mt-6 space-y-6">
              {quiz.questions.map((question, index) => (
                <div
                  key={question.id}
                  className="rounded-2xl border border-zinc-100 bg-zinc-50 p-5 shadow-inner dark:border-zinc-800 dark:bg-zinc-800/50"
                >
                  <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Question {index + 1}</p>
                  <h3 className="mt-2 text-lg font-semibold text-zinc-900 dark:text-white">{question.question}</h3>

                  <div className="mt-4 space-y-2">
                    {question.options.map((option, optionIndex) => {
                      const letter = String.fromCharCode(65 + optionIndex);
                      return (
                        <label
                          key={letter}
                          className={`flex cursor-pointer items-center gap-3 rounded-2xl border px-4 py-3 text-sm transition ${
                            answers[question.id] === letter
                              ? "border-zinc-900 bg-white dark:border-white dark:bg-zinc-700"
                              : "border-zinc-200 hover:border-zinc-300 dark:border-zinc-700 dark:hover:border-zinc-600"
                          }`}
                        >
                          <input
                            type="radio"
                            name={question.id}
                            value={letter}
                            checked={answers[question.id] === letter}
                            onChange={() =>
                              setAnswers((prev) => ({
                                ...prev,
                                [question.id]: letter,
                              }))
                            }
                          />
                          <span className="font-medium text-zinc-900 dark:text-white">{letter}.</span>
                          <span className="text-zinc-700 dark:text-zinc-300">{option}</span>
                        </label>
                      );
                    })}
                  </div>

                  {question.explanation && (
                    <p className="mt-4 text-sm text-zinc-500 dark:text-zinc-400">Source: {question.explanation}</p>
                  )}
                </div>
              ))}
            </div>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              {result && (
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300">
                  Score: {result.score}/{result.total_questions} ({result.percentage.toFixed(1)}%)
                </div>
              )}
              {!result && (
                <button
                  type="button"
                  disabled={answeredCount !== quiz.questions.length || isSubmitting}
                  onClick={handleSubmit}
                  className="rounded-full bg-zinc-900 px-6 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-zinc-900"
                >
                  {isSubmitting ? "Submitting…" : "Submit quiz"}
                </button>
              )}
            </div>
          </section>
        )}
    </PageShell>
  );
}
