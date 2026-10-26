"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  QuizFolder,
  QuizQuestion,
  QuizHistoryEntry,
  Course,
  fetchCourses,
  fetchQuizFolders,
  fetchQuizHistory,
  fetchStudyRecommendation,
  generateQuiz,
  submitQuiz,
} from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { useActiveCourse } from "@/components/active-course-provider";
import { Brain, History, Trophy, CheckCircle, XCircle, Folder, Sparkles, Target, Clock, Award, Lightbulb } from "lucide-react";
import { PageHero } from "@/components/page-hero";
import { toast } from "sonner";
import { Skeleton, SkeletonRegion } from "@/components/skeleton";

export default function QuizPage() {
  const { token } = useAuthToken();
  const [folders, setFolders] = useState<QuizFolder[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const { activeCourseId: courseId = "info-5731", setActiveCourseId: setCourseId } = useActiveCourse();
  const [recommendedObjectiveId, setRecommendedObjectiveId] = useState<string | undefined>();
  const [recommendedTitle, setRecommendedTitle] = useState<string>();
  const [recommendedDifficulty, setRecommendedDifficulty] = useState<"easy" | "medium" | "hard">("medium");
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
    fetchCourses(token)
      .then((items) => {
        setCourses(items);
        const requestedCourse = new URLSearchParams(window.location.search).get("course");
        if (requestedCourse && items.some((item) => item.id === requestedCourse)) setCourseId(requestedCourse);
        else if (items.length > 0) setCourseId(items[0].id);
      })
      .catch(() => {});
    const params = new URLSearchParams(window.location.search);
    setRecommendedObjectiveId(params.get("objective") || undefined);
    const difficulty = params.get("difficulty");
    if (difficulty === "easy" || difficulty === "medium" || difficulty === "hard") setRecommendedDifficulty(difficulty);
  }, [setCourseId, token]);

  useEffect(() => {
    if (!token || !courseId) return;
    let mounted = true;
    setLoadingFolders(true);
    fetchQuizFolders(token, courseId)
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

    fetchQuizHistory(token, courseId)
      .then((res) => mounted && setHistory(res.results || []))
      .catch(() => {});

    fetchStudyRecommendation(token, courseId)
      .then((recommendation) => {
        if (!recommendation) return;
        setRecommendedObjectiveId((current) => current || recommendation.objective_id);
        setRecommendedTitle(recommendation.title);
        setRecommendedDifficulty(recommendation.difficulty);
      })
      .catch(() => {});

    return () => {
      mounted = false;
    };
  }, [token, courseId]);

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
        courseId,
        objectiveIds: recommendedObjectiveId ? [recommendedObjectiveId] : undefined,
        difficulty: recommendedObjectiveId ? recommendedDifficulty : undefined,
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
    if (percentage >= 80) return 'text-success';
    if (percentage >= 60) return 'text-warning';
    return 'text-danger';
  };

  const getScoreBg = (percentage: number) => {
    if (percentage >= 80) return 'bg-success-bg';
    if (percentage >= 60) return 'bg-warning-bg';
    return 'bg-danger-bg';
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
          <form onSubmit={handleGenerate} className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
            {/* Header */}
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-lavender/15">
                <Target className="h-5 w-5 text-violet-700 dark:text-lavender" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-foreground">Practice this course</h2>
                <p className="text-sm text-muted">Choose course materials, then practice with feedback.</p>
              </div>
            </div>

            <label className="mb-6 block text-sm font-medium text-foreground">
              Active course
              <select value={courseId} onChange={(event) => { setCourseId(event.target.value); setRecommendedObjectiveId(undefined); }} className="mt-2 w-full rounded-xl border border-line bg-surface px-3 py-2 text-foreground">
                {courses.map((course) => <option key={course.id} value={course.id}>{course.code} · {course.title}</option>)}
              </select>
            </label>

            {recommendedObjectiveId && <div className="mb-6 rounded-xl border border-primary/30 bg-primary-bg px-4 py-3 text-sm text-foreground"><p className="font-semibold">Recommended practice{recommendedTitle ? `: ${recommendedTitle}` : ""}</p><p className="mt-1">This {recommendedDifficulty} set targets one objective and updates mastery from your item-level answers.</p></div>}

            {foldersError && (
              <div className="mb-4 rounded-xl bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger">
                {foldersError}
              </div>
            )}

            <details className="mb-6 rounded-xl border border-line p-4" open={!recommendedObjectiveId}>
              <summary className="cursor-pointer text-sm font-semibold text-foreground">{recommendedObjectiveId ? "Customize this practice set" : "Choose practice materials"}</summary>
            {/* Folder Selection */}
            <div className="mb-6 mt-5">
              <label className="flex items-center gap-2 text-sm font-medium text-foreground mb-3">
                <Folder className="h-4 w-4" />
                Select Topics
              </label>
              {loadingFolders ? (
                <SkeletonRegion label="Loading topics" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {[1, 2, 3, 4, 5, 6].map((i) => (
                    <div key={i} className="rounded-xl border border-line bg-surface p-4">
                      <Skeleton className="mb-2 h-4 w-3/4" />
                      <Skeleton className="h-3 w-1/2" />
                    </div>
                  ))}
                </SkeletonRegion>
              ) : folders.length === 0 ? (
                <div className="rounded-xl border-2 border-dashed border-line bg-surface-2 p-8 text-center">
                  <div className="mx-auto h-12 w-12 rounded-full bg-surface-2 flex items-center justify-center mb-3">
                    <Folder className="h-6 w-6 text-muted" />
                  </div>
                  <p className="text-sm font-medium text-foreground">No course folders found</p>
                  <p className="text-xs text-muted mt-1">Upload course materials to generate quizzes</p>
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
                            ? "gradient-primary text-white shadow-brand"
                            : "border border-line bg-surface-2 hover:border-primary/40 hover:shadow-md"
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
                        <span className={`font-semibold block ${isSelected ? '' : 'text-foreground'}`}>
                          {folder.label}
                        </span>
                        <span className={`text-xs ${isSelected ? 'text-white/70' : 'text-muted'}`}>
                          {folder.file_count} files
                        </span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Question Count */}
            <div className="mb-2">
              <label className="flex items-center justify-between text-sm font-medium text-foreground mb-3">
                <span className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4" />
                  Number of Questions
                </span>
                <span className="text-lg font-bold text-violet-700 dark:text-lavender">{numQuestions}</span>
              </label>
              <input
                type="range"
                min={1}
                max={10}
                value={numQuestions}
                onChange={(event) => setNumQuestions(Number(event.target.value))}
                className="w-full h-2 bg-line rounded-full appearance-none cursor-pointer accent-purple-600"
              />
              <div className="flex justify-between text-xs text-muted mt-1">
                <span>1</span>
                <span>10</span>
              </div>
            </div>
            </details>

            {actionError && (
              <div className="mb-4 rounded-xl bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger">
                {actionError}
              </div>
            )}

            {/* Generate Button */}
            <button
              type="submit"
              disabled={isGenerating || selectedFolders.length === 0}
              className="w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl gradient-primary hover:brightness-110 text-white font-semibold transition disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isGenerating ? (
                <>
                  <span className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
                  Generating Quiz...
                </>
              ) : (
                <>
                  <Sparkles className="h-5 w-5" />
                  {recommendedObjectiveId ? "Start recommended practice" : "Generate custom quiz"}
                </>
              )}
            </button>
            {!isGenerating && selectedFolders.length === 0 && (
              <p className="mt-2 text-center text-xs text-muted" role="status">
                {recommendedObjectiveId
                  ? "Open “Customize this practice set” and pick at least one topic to start."
                  : "Pick at least one topic above to generate a quiz."}
              </p>
            )}
          </form>
        </div>

        {/* History Sidebar */}
        <div className="lg:col-span-1">
          <div className="rounded-2xl border border-line bg-surface p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <div className="p-1.5 rounded-lg bg-warning-bg">
                <Trophy className="h-4 w-4 text-warning" />
              </div>
              <h3 className="font-semibold text-foreground text-sm">Recent Scores</h3>
            </div>

            <div className="space-y-2">
              {history.length === 0 ? (
                <p className="text-center text-xs text-muted py-6">
                  No attempts yet. Generate a quiz to get started!
                </p>
              ) : (
                history.slice(0, 5).map((attempt, index) => (
                  <div
                    key={`${attempt.id}-${attempt.created_at ?? index}`}
                    className="flex items-center justify-between p-3 rounded-xl bg-surface-2"
                  >
                    <div className="flex items-center gap-2">
                      <div className={`p-1.5 rounded-lg ${getScoreBg(attempt.percentage)}`}>
                        <Award className={`h-4 w-4 ${getScoreColor(attempt.percentage)}`} />
                      </div>
                      <div>
                        <p className={`font-bold text-sm ${getScoreColor(attempt.percentage)}`}>
                          {attempt.percentage.toFixed(0)}%
                        </p>
                        <p className="text-xs text-muted">{attempt.score}/{attempt.total_questions}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-muted">
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
        <div className="mt-8 rounded-2xl border border-line bg-surface p-6 shadow-sm animate-fade-in-up">
          {/* Quiz Header */}
          <div className="flex flex-col gap-2 pb-6 mb-6 border-b border-line sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider text-violet-700 dark:text-lavender font-semibold mb-1">Active Quiz</p>
              <h2 className="text-xl font-bold text-foreground">
                {resolvedFolderLabels.join(", ")}
              </h2>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-surface-2">
              <Clock className="h-4 w-4 text-muted" />
              <span className="text-sm font-medium text-foreground">
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
                        ? "bg-success-bg border-success/30"
                        : "bg-danger-bg border-danger/30"
                      : "bg-surface-2 border-line"
                  }`}
                >
                  <div className="flex items-start gap-3 mb-4">
                    <span className={`flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${
                      isGraded
                        ? qResult.is_correct
                          ? "bg-success-bg text-success"
                          : "bg-danger-bg text-danger"
                        : "bg-lavender/15 text-violet-700 dark:text-lavender"
                    }`}>
                      {isGraded ? (qResult.is_correct ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />) : index + 1}
                    </span>
                    <h3 className="text-base font-semibold text-foreground leading-relaxed">
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
                          optionClass = "bg-success-bg border-2 border-success";
                          circleClass = "bg-success-solid text-white";
                          textClass = "text-success font-medium";
                        } else if (isWrongSelection) {
                          optionClass = "bg-danger-bg border-2 border-danger";
                          circleClass = "bg-danger-solid text-white";
                          textClass = "text-danger font-medium line-through";
                        } else {
                          optionClass = "bg-surface border border-line opacity-60";
                          circleClass = "bg-surface-2 text-muted";
                          textClass = "text-foreground";
                        }
                      } else {
                        optionClass = isSelected
                          ? "bg-primary-bg border-2 border-primary"
                          : "bg-surface border border-line hover:border-primary/40";
                        circleClass = isSelected
                          ? "bg-primary-solid text-white"
                          : "bg-surface-2 text-muted";
                        textClass = isSelected
                          ? "text-primary font-medium"
                          : "text-foreground";
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
                    <div className="ml-11 mt-3 rounded-lg bg-warning-bg border border-warning/40 px-4 py-3">
                      <div className="flex items-start gap-2">
                        <Lightbulb className="h-4 w-4 text-warning mt-0.5 flex-shrink-0" />
                        <p className="text-sm text-warning">{qResult.explanation}</p>
                      </div>
                      {question.objective_id && <Link href={`/chat?course=${encodeURIComponent(courseId)}&mode=learn&objective=${encodeURIComponent(question.objective_id)}`} className="mt-2 inline-block text-sm font-semibold text-warning underline">Review this objective in Learn mode</Link>}
                    </div>
                  )}

                  {/* Confirmation for correct answers */}
                  {isGraded && qResult.is_correct && qResult.explanation && (
                    <div className="ml-11 mt-3 rounded-lg bg-success-bg border border-success/30 px-4 py-3">
                      <div className="flex items-start gap-2">
                        <CheckCircle className="h-4 w-4 text-success mt-0.5 flex-shrink-0" />
                        <p className="text-sm text-success">{qResult.explanation}</p>
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
                  <p className="text-xs text-muted">Quiz completed!</p>
                </div>
              </div>
            )}
            {!result && (
              <button
                type="button"
                disabled={answeredCount !== quiz.questions.length || isSubmitting}
                onClick={handleSubmit}
                className="btn-primary btn-lg"
              >
                {isSubmitting ? (
                  <>
                    <span className="h-5 w-5 animate-spin rounded-full border-2 border-background border-t-transparent"></span>
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
