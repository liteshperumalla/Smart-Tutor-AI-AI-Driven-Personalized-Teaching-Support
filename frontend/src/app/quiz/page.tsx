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
import { Brain, History, Trophy, CheckCircle, XCircle, Folder, Sparkles, Target, Clock, Award, Lightbulb } from "lucide-react";
import { PageHero } from "@/components/page-hero";
import { toast } from "sonner";

export default function QuizPage() {
  const { token } = useAuthToken();
  const [folders, setFolders] = useState<QuizFolder[]>([]);
  const [selectedFolders, setSelectedFolders] = useState<string[]>([]);
  const [numQuestions, setNumQuestions] = useState(5);
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

  const sortFoldersByPath = (folders: QuizFolder[]) => {
    return [...folders].sort((a, b) => {
      const numA = parseInt(a.path.match(/module\\s*(\\d+)/i)?.[1] || "0", 10);
      const numB = parseInt(b.path.match(/module\\s*(\\d+)/i)?.[1] || "0", 10);
      if (numA !== numB) return numA - numB;
      return a.label.localeCompare(b.label);
    });
  };

  useEffect(() => {
    if (!token) return;
    let mounted = true;
    setLoadingFolders(true);
    fetchQuizFolders(token)
      .then((data) => {
        if (!mounted) return;
        const sortedFolders = sortFoldersByPath(data);
        setFolders(sortedFolders);
        setFoldersError(null);
        if (sortedFolders.length > 0) {
          setSelectedFolders([sortedFolders[0].path]);
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
      toast.success(`Quiz generated with ${payload.questions.length} questions`);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unable to generate quiz";
      setActionError(msg);
      toast.error(msg);
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
          answers,
        },
      });
      setResult(response.result);
      setHistory((prev) => [response.result, ...prev]);
      const pct = response.result?.percentage;
      toast.success(pct != null ? `Score: ${pct}%` : "Quiz submitted");
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to submit quiz";
      setActionError(msg);
      toast.error(msg);
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

  // Build a lookup from question_id -> grading details after submission
  type QuestionResult = {
    question_id: string;
    correct_answer: string;
    user_answer: string | null;
    is_correct: boolean;
    explanation: string;
  };

  const resultMap = useMemo(() => {
    if (!result?.metadata) return new Map<string, QuestionResult>();
    const responses = (result.metadata as Record<string, unknown>).responses as QuestionResult[] | undefined;
    if (!Array.isArray(responses)) return new Map<string, QuestionResult>();
    return new Map(responses.map((r) => [r.question_id, r]));
  }, [result]);

  const getScoreColor = (percentage: number) => {
    if (percentage >= 80) return 'text-emerald-600 dark:text-emerald-400';
    if (percentage >= 60) return 'text-amber-600 dark:text-amber-400';
    return 'text-red-600 dark:text-red-400';
  };

  const getScoreBg = (percentage: number) => {
    if (percentage >= 80) return 'bg-emerald-100 dark:bg-emerald-900/30';
    if (percentage >= 60) return 'bg-amber-100 dark:bg-amber-900/30';
    return 'bg-red-100 dark:bg-red-900/30';
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 animate-fade-in-up">
      {/* Header */}
      <PageHero
        className="mb-8"
        icon={Brain}
        title="Knowledge"
        accent="Quiz"
        subtitle="Test your understanding of course materials."
      />

      <div className="grid gap-6 lg:grid-cols-4">
        {/* Quiz Setup */}
        <div className="lg:col-span-3">
          <form onSubmit={handleGenerate} className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6 shadow-sm">
            {/* Header */}
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-900/30">
                <Target className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-zinc-900 dark:text-white">Create Your Quiz</h2>
                <p className="text-sm text-zinc-500 dark:text-zinc-400">Select topics and number of questions</p>
              </div>
            </div>

            {foldersError && (
              <div className="mb-4 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-red-700 dark:text-red-400">
                {foldersError}
              </div>
            )}

            {/* Folder Selection */}
            <div className="mb-6">
              <label className="flex items-center gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3">
                <Folder className="h-4 w-4" />
                Select Topics
              </label>
              {loadingFolders ? (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {[1, 2, 3, 4, 5, 6].map((i) => (
                    <div key={i} className="rounded-xl p-4 border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 animate-pulse">
                      <div className="h-4 w-3/4 bg-zinc-200 dark:bg-zinc-700 rounded mb-2"></div>
                      <div className="h-3 w-1/2 bg-zinc-200 dark:bg-zinc-700 rounded"></div>
                    </div>
                  ))}
                </div>
              ) : folders.length === 0 ? (
                <div className="rounded-xl border-2 border-dashed border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/50 p-8 text-center">
                  <div className="mx-auto h-12 w-12 rounded-full bg-zinc-100 dark:bg-zinc-700 flex items-center justify-center mb-3">
                    <Folder className="h-6 w-6 text-zinc-400" />
                  </div>
                  <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">No course folders found</p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Upload course materials to generate quizzes</p>
                </div>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {folders.map((folder) => {
                    const isSelected = selectedFolders.includes(folder.path);
                    return (
                      <label
                        key={folder.path}
                        className={`group relative cursor-pointer overflow-hidden rounded-xl p-4 transition-all duration-200 hover:-translate-y-0.5 ${
                          isSelected
                            ? "bg-gradient-to-br from-purple-500 to-indigo-600 text-white shadow-lg shadow-purple-500/25"
                            : "border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 hover:border-purple-300 dark:hover:border-purple-600 hover:shadow-md"
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
                            <CheckCircle className="h-4 w-4" />
                          </div>
                        )}
                        <span className={`font-semibold block ${isSelected ? '' : 'text-zinc-900 dark:text-white'}`}>
                          {folder.label}
                        </span>
                        <span className={`text-xs ${isSelected ? 'text-white/70' : 'text-zinc-500 dark:text-zinc-400'}`}>
                          {folder.file_count} files
                        </span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Question Count */}
            <div className="mb-6">
              <label className="flex items-center justify-between text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3">
                <span className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4" />
                  Number of Questions
                </span>
                <span className="text-lg font-bold text-purple-600 dark:text-purple-400">{numQuestions}</span>
              </label>
              <input
                type="range"
                min={1}
                max={10}
                value={numQuestions}
                onChange={(event) => setNumQuestions(Number(event.target.value))}
                className="w-full h-2 bg-zinc-200 dark:bg-zinc-700 rounded-full appearance-none cursor-pointer accent-purple-600"
              />
              <div className="flex justify-between text-xs text-zinc-400 mt-1">
                <span>1</span>
                <span>10</span>
              </div>
            </div>

            {actionError && (
              <div className="mb-4 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-red-700 dark:text-red-400">
                {actionError}
              </div>
            )}

            {/* Generate Button */}
            <button
              type="submit"
              disabled={isGenerating || selectedFolders.length === 0}
              className="w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-semibold hover:from-purple-700 hover:to-indigo-700 transition disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isGenerating ? (
                <>
                  <span className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
                  Generating Quiz...
                </>
              ) : (
                <>
                  <Sparkles className="h-5 w-5" />
                  Generate Quiz
                </>
              )}
            </button>
          </form>
        </div>

        {/* History Sidebar */}
        <div className="lg:col-span-1">
          <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <div className="p-1.5 rounded-lg bg-amber-100 dark:bg-amber-900/30">
                <Trophy className="h-4 w-4 text-amber-600 dark:text-amber-400" />
              </div>
              <h3 className="font-semibold text-zinc-900 dark:text-white text-sm">Recent Scores</h3>
            </div>

            <div className="space-y-2">
              {history.length === 0 ? (
                <p className="text-center text-xs text-zinc-500 dark:text-zinc-400 py-6">
                  No attempts yet. Generate a quiz to get started!
                </p>
              ) : (
                history.slice(0, 5).map((attempt, index) => (
                  <div
                    key={`${attempt.id}-${attempt.created_at ?? index}`}
                    className="flex items-center justify-between p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/50"
                  >
                    <div className="flex items-center gap-2">
                      <div className={`p-1.5 rounded-lg ${getScoreBg(attempt.percentage)}`}>
                        <Award className={`h-4 w-4 ${getScoreColor(attempt.percentage)}`} />
                      </div>
                      <div>
                        <p className={`font-bold text-sm ${getScoreColor(attempt.percentage)}`}>
                          {attempt.percentage.toFixed(0)}%
                        </p>
                        <p className="text-xs text-zinc-500">{attempt.score}/{attempt.total_questions}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-zinc-400">
                        {new Date(attempt.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Active Quiz Section */}
      {quiz && (
        <div className="mt-8 rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6 shadow-sm animate-fade-in-up">
          {/* Quiz Header */}
          <div className="flex flex-col gap-2 pb-6 mb-6 border-b border-zinc-100 dark:border-zinc-800 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider text-purple-600 dark:text-purple-400 font-semibold mb-1">Active Quiz</p>
              <h2 className="text-xl font-bold text-zinc-900 dark:text-white">
                {resolvedFolderLabels.join(", ")}
              </h2>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-zinc-100 dark:bg-zinc-800">
              <Clock className="h-4 w-4 text-zinc-500" />
              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                {answeredCount}/{quiz.questions.length} answered
              </span>
            </div>
          </div>

          {/* Questions */}
          <div className="space-y-6">
            {quiz.questions.map((question, index) => {
              const qResult = resultMap.get(question.id);
              const isGraded = !!qResult;

              return (
                <div
                  key={question.id}
                  className={`rounded-xl p-5 border ${
                    isGraded
                      ? qResult.is_correct
                        ? "bg-emerald-50 dark:bg-emerald-900/10 border-emerald-200 dark:border-emerald-800/50"
                        : "bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800/50"
                      : "bg-zinc-50 dark:bg-zinc-800/50 border-zinc-100 dark:border-zinc-700/50"
                  }`}
                >
                  <div className="flex items-start gap-3 mb-4">
                    <span className={`flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${
                      isGraded
                        ? qResult.is_correct
                          ? "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400"
                          : "bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400"
                        : "bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400"
                    }`}>
                      {isGraded ? (qResult.is_correct ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />) : index + 1}
                    </span>
                    <h3 className="text-base font-semibold text-zinc-900 dark:text-white leading-relaxed">
                      {question.question}
                    </h3>
                  </div>

                  <div className="ml-11 space-y-2">
                    {question.options.map((option, optionIndex) => {
                      const letter = String.fromCharCode(65 + optionIndex);
                      const displayOption = normalizeOptionLabel(option, letter);
                      const isSelected = answers[question.id] === letter;
                      const isCorrectAnswer = isGraded && qResult.correct_answer === letter;
                      const isWrongSelection = isGraded && isSelected && !qResult.is_correct;

                      let optionClass = "";
                      let circleClass = "";
                      let textClass = "";

                      if (isGraded) {
                        if (isCorrectAnswer) {
                          optionClass = "bg-emerald-100 dark:bg-emerald-900/30 border-2 border-emerald-500";
                          circleClass = "bg-emerald-600 text-white";
                          textClass = "text-emerald-900 dark:text-emerald-100 font-medium";
                        } else if (isWrongSelection) {
                          optionClass = "bg-red-100 dark:bg-red-900/30 border-2 border-red-400";
                          circleClass = "bg-red-500 text-white";
                          textClass = "text-red-900 dark:text-red-100 font-medium line-through";
                        } else {
                          optionClass = "bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 opacity-60";
                          circleClass = "bg-zinc-100 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-400";
                          textClass = "text-zinc-700 dark:text-zinc-300";
                        }
                      } else {
                        optionClass = isSelected
                          ? "bg-purple-100 dark:bg-purple-900/30 border-2 border-purple-500"
                          : "bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 hover:border-purple-300 dark:hover:border-purple-600";
                        circleClass = isSelected
                          ? "bg-purple-600 text-white"
                          : "bg-zinc-100 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-400";
                        textClass = isSelected
                          ? "text-purple-900 dark:text-purple-100 font-medium"
                          : "text-zinc-700 dark:text-zinc-300";
                      }

                      return (
                        <label
                          key={letter}
                          className={`flex items-center gap-3 rounded-xl px-4 py-3 transition ${isGraded ? "" : "cursor-pointer"} ${optionClass}`}
                        >
                          <input
                            type="radio"
                            name={question.id}
                            value={letter}
                            checked={isSelected}
                            disabled={isGraded}
                            onChange={() =>
                              setAnswers((prev) => ({
                                ...prev,
                                [question.id]: letter,
                              }))
                            }
                            className="sr-only"
                          />
                          <span className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold ${circleClass}`}>
                            {isGraded && isCorrectAnswer ? <CheckCircle className="h-4 w-4" /> : isGraded && isWrongSelection ? <XCircle className="h-4 w-4" /> : letter}
                          </span>
                          <span className={`text-sm ${textClass}`}>
                            {displayOption}
                          </span>
                        </label>
                      );
                    })}
                  </div>

                  {/* Explanation for wrong answers */}
                  {isGraded && !qResult.is_correct && qResult.explanation && (
                    <div className="ml-11 mt-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800/50 px-4 py-3">
                      <div className="flex items-start gap-2">
                        <Lightbulb className="h-4 w-4 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
                        <p className="text-sm text-amber-900 dark:text-amber-200">{qResult.explanation}</p>
                      </div>
                    </div>
                  )}

                  {/* Confirmation for correct answers */}
                  {isGraded && qResult.is_correct && qResult.explanation && (
                    <div className="ml-11 mt-3 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800/50 px-4 py-3">
                      <div className="flex items-start gap-2">
                        <CheckCircle className="h-4 w-4 text-emerald-600 dark:text-emerald-400 mt-0.5 flex-shrink-0" />
                        <p className="text-sm text-emerald-900 dark:text-emerald-200">{qResult.explanation}</p>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Submit Section */}
          <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            {result && (
              <div className={`flex items-center gap-3 px-5 py-3 rounded-xl ${getScoreBg(result.percentage)}`}>
                <Trophy className={`h-6 w-6 ${getScoreColor(result.percentage)}`} />
                <div>
                  <p className={`text-lg font-bold ${getScoreColor(result.percentage)}`}>
                    {result.score}/{result.total_questions} ({result.percentage.toFixed(0)}%)
                  </p>
                  <p className="text-xs text-zinc-600 dark:text-zinc-400">Quiz completed!</p>
                </div>
              </div>
            )}
            {!result && (
              <button
                type="button"
                disabled={answeredCount !== quiz.questions.length || isSubmitting}
                onClick={handleSubmit}
                className="flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 font-semibold hover:bg-zinc-800 dark:hover:bg-zinc-100 transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? (
                  <>
                    <span className="h-5 w-5 animate-spin rounded-full border-2 border-white dark:border-zinc-900 border-t-transparent"></span>
                    Submitting...
                  </>
                ) : (
                  <>
                    <CheckCircle className="h-5 w-5" />
                    Submit Quiz
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
