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
import { Brain, Plus, History, Trophy, CheckCircle, HelpCircle } from "lucide-react";

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

  const normalizeOptionLabel = (option: string, letter: string) => {
    const pattern = new RegExp(`^${letter}[\\.)\\-:\\]]\\s+`, "i");
    return option.replace(pattern, "").trim();
  };

  return (
    <PageShell contentClassName="gap-10">
        <header className="relative overflow-hidden rounded-3xl gradient-mesh p-12 animate-fade-in-down">
          <div className="absolute top-0 right-0 h-64 w-64 bg-indigo-400/20 rounded-full blur-3xl animate-float"></div>
          <div className="absolute bottom-0 left-0 h-48 w-48 bg-amber-400/20 rounded-full blur-3xl" style={{animationDelay: '1s'}}></div>

          <div className="relative z-10">
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white/80 px-4 py-2 text-sm font-medium text-indigo-700 backdrop-blur dark:border-indigo-800 dark:bg-zinc-900/80 dark:text-indigo-300 mb-4">
              <Brain className="h-4 w-4" />
              Quiz Generator
            </div>
            <h1 className="font-display text-5xl font-bold text-zinc-900 dark:text-white">
              Master the course material
            </h1>
            <p className="mt-4 text-lg text-zinc-600 max-w-2xl dark:text-zinc-400">
              Generate custom quizzes from your course materials and track your progress
            </p>
          </div>
        </header>

        <section className="grid gap-6 lg:grid-cols-3 animate-fade-in-up">
          <form
            onSubmit={handleGenerate}
            className="card lg:col-span-2"
          >
            {foldersError && (
              <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400">
                {foldersError}
              </div>
            )}

            <div className="space-y-2">
              <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Select folders</p>
              {loadingFolders ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="rounded-2xl p-4 border-2 border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-800 animate-pulse">
                      <div className="h-4 w-3/4 bg-zinc-200 dark:bg-zinc-700 rounded mb-2"></div>
                      <div className="h-3 w-1/2 bg-zinc-200 dark:bg-zinc-700 rounded"></div>
                    </div>
                  ))}
                </div>
              ) : folders.length === 0 ? (
                <div className="rounded-2xl border-2 border-dashed border-zinc-200 bg-zinc-50 p-8 text-center dark:border-zinc-700 dark:bg-zinc-800/50">
                  <div className="mx-auto h-12 w-12 rounded-full bg-zinc-100 dark:bg-zinc-700 flex items-center justify-center mb-3">
                    <svg className="h-6 w-6 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                    </svg>
                  </div>
                  <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">No course folders found</p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Upload course materials to the knowledge base to generate quizzes.</p>
                  <a href="/research" className="inline-block mt-3 text-sm font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400">
                    Go to Research mode →
                  </a>
                </div>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  {folders.map((folder) => {
                  const isSelected = selectedFolders.includes(folder.path);
                  return (
                    <label
                      key={folder.path}
                      className={`group relative cursor-pointer overflow-hidden rounded-2xl p-4 text-sm transition hover:-translate-y-1 ${
                        isSelected
                          ? "bg-gradient-to-br from-indigo-500 to-purple-600 text-white shadow-lg shadow-indigo-500/30"
                          : "border-2 border-zinc-200 bg-white hover:border-indigo-300 hover:shadow-md dark:border-zinc-700 dark:bg-zinc-800 dark:hover:border-indigo-600"
                      }`}
                    >
                      <input
                        type="checkbox"
                        className="hidden"
                        checked={isSelected}
                        onChange={() => toggleFolder(folder.path)}
                      />
                      {isSelected && (
                        <div className="absolute top-3 right-3 flex h-6 w-6 items-center justify-center rounded-full bg-white/20 backdrop-blur">
                          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                      )}
                      <div className={`flex h-10 w-10 items-center justify-center rounded-xl mb-3 ${
                        isSelected ? 'bg-white/20' : 'bg-indigo-100 dark:bg-indigo-900/30'
                      }`}>
                        <div className={`h-5 w-5 rounded-full ${isSelected ? 'bg-white/40' : 'bg-indigo-600 dark:bg-indigo-400'}`}></div>
                      </div>
                      <span className={`font-bold block ${isSelected ? '' : 'text-zinc-900 dark:text-white'}`}>{folder.label}</span>
                      <span className={`text-xs ${isSelected ? 'text-white/70' : 'text-zinc-500 dark:text-zinc-400'}`}>{folder.file_count} files</span>
                    </label>
                  );
                })}
              </div>
              )}
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
              className="btn-primary mt-6 w-full disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:scale-100"
            >
              {isGenerating ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Building quiz…</>
              ) : (
                <>Generate quiz <span className="transition-transform group-hover:translate-x-1">→</span></>
              )}
            </button>
          </form>

          <aside className="card">
            <div className="flex items-center gap-2 mb-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-100 dark:bg-indigo-900/30">
                <History className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
              </div>
              <p className="font-semibold text-zinc-900 dark:text-white">Recent attempts</p>
            </div>
            <div className="space-y-3 text-sm">
              {history.slice(0, 4).map((attempt, index) => (
                <div
                  key={`${attempt.id}-${attempt.created_at ?? index}`}
                  className="rounded-xl border-2 border-zinc-100 bg-zinc-50 p-3 transition hover:border-indigo-200 hover:shadow-sm dark:border-zinc-800 dark:bg-zinc-800/50 dark:hover:border-indigo-800"
                >
                  <div className="flex items-center justify-between">
                    <p className="font-bold text-zinc-900 dark:text-white">
                      {attempt.score}/{attempt.total_questions}
                    </p>
                    <span className={`badge ${
                      attempt.percentage >= 80 ? 'badge-success' :
                      attempt.percentage >= 60 ? 'badge-warning' :
                      'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                    }`}>
                      {attempt.percentage.toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                    {new Date(attempt.created_at).toLocaleString()}
                  </p>
                </div>
              ))}
              {history.length === 0 && <p className="text-center text-xs text-zinc-500 dark:text-zinc-400 py-4">No attempts yet. Generate a quiz to get started!</p>}
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
                      const displayOption = normalizeOptionLabel(option, letter);
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
                          <span className="text-zinc-700 dark:text-zinc-300">{displayOption}</span>
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
