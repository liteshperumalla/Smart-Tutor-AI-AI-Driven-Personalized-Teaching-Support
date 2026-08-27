"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BookOpenCheck, CircleGauge, Target, ChevronRight } from "lucide-react";
import { enrollInCourse, fetchCourseCatalog, fetchCourses, fetchLearningDashboard, type Course, type CourseCatalogEntry, type LearningDashboard } from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { useActiveCourse } from "@/components/active-course-provider";

function masteryLabel(score: number) {
  if (score >= 0.8) return "Strong";
  if (score >= 0.5) return "Developing";
  return "Start here";
}

export function LearnerDashboard() {
  const { token } = useAuthToken({ redirectTo: undefined });
  const [courses, setCourses] = useState<Course[]>([]);
  const [catalog, setCatalog] = useState<CourseCatalogEntry[]>([]);
  const { activeCourseId: courseId, setActiveCourseId: setCourseId } = useActiveCourse();
  const [dashboard, setDashboard] = useState<LearningDashboard>();
  const [error, setError] = useState<string>();
  const [coursesLoaded, setCoursesLoaded] = useState(false);
  const [enrolling, setEnrolling] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetchCourses(token)
      .then((items) => {
        setCourses(items);
        setCourseId(courseId && items.some((course) => course.id === courseId) ? courseId : items[0]?.id);
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load learning progress"))
      .finally(() => setCoursesLoaded(true));
    fetchCourseCatalog(token).then(setCatalog).catch(() => undefined);
  }, [courseId, setCourseId, token]);

  useEffect(() => {
    if (!token || !courseId) return;
    fetchLearningDashboard(token, courseId)
      .then(setDashboard)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Unable to load learning progress"));
  }, [token, courseId]);

  if (!token) return null;
  if (error) return <p className="text-sm text-zinc-500">Learning progress is temporarily unavailable.</p>;
  if (coursesLoaded && !courseId) {
    return <section className="rounded-3xl border border-indigo-200 bg-indigo-50 p-6 shadow-sm dark:border-indigo-900/60 dark:bg-indigo-950/40"><p className="text-sm font-semibold text-indigo-700 dark:text-indigo-300">Course catalog</p><h2 className="mt-2 text-xl font-bold text-zinc-900 dark:text-white">Choose a course to begin</h2><p className="mt-2 text-sm text-zinc-600 dark:text-zinc-300">Course content remains private until you explicitly enroll.</p><div className="mt-5 grid gap-3 md:grid-cols-2">{catalog.filter((course) => !course.enrolled).map((availableCourse) => <article key={availableCourse.id} className="rounded-2xl bg-white p-4 shadow-sm dark:bg-zinc-900"><p className="text-xs font-semibold uppercase tracking-wide text-indigo-600 dark:text-indigo-300">{availableCourse.code}</p><h3 className="mt-1 font-semibold text-zinc-900 dark:text-white">{availableCourse.title}</h3><p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">{availableCourse.description || "Course workspace"}</p><button type="button" disabled={enrolling} onClick={async () => { setEnrolling(true); try { await enrollInCourse(token, availableCourse.id); setCourses((items) => [...items, { ...availableCourse, membership_role: "student" }]); setCourseId(availableCourse.id); } catch { setError("Unable to enroll in this course"); } finally { setEnrolling(false); } }} className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{enrolling ? "Joining…" : `Join ${availableCourse.code}`}</button></article>)}</div>{catalog.length === 0 && <p className="mt-4 text-sm text-zinc-500">No courses are open for enrollment yet.</p>}</section>;
  }
  if (!dashboard) return <section className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 animate-pulse"><div className="h-5 w-48 rounded bg-zinc-200 dark:bg-zinc-800" /></section>;

  const recommendation = dashboard.recommendation;
  return (
    <section aria-labelledby="learning-progress-title" className="rounded-3xl border border-indigo-200 bg-gradient-to-br from-indigo-50 to-white p-6 shadow-sm dark:border-indigo-900/60 dark:from-indigo-950/40 dark:to-zinc-900 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.25em] text-indigo-700 dark:text-indigo-300"><CircleGauge className="h-4 w-4" /> Learning progress</p>
          <h2 id="learning-progress-title" className="mt-2 text-2xl font-bold text-zinc-900 dark:text-white">{dashboard.course?.title ?? "Your course"}</h2>
        </div>
        {courses.length > 1 && <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Course <select value={courseId} onChange={(event) => setCourseId(event.target.value)} className="ml-2 rounded-lg border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-800"><option value="">Select</option>{courses.map((course) => <option key={course.id} value={course.id}>{course.code} — {course.title}</option>)}</select></label>}
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <article className="rounded-2xl bg-white/80 p-4 dark:bg-zinc-900/80">
          <p className="text-sm text-zinc-600 dark:text-zinc-400">Weekly practice</p>
          <p className="mt-2 text-3xl font-bold text-zinc-900 dark:text-white">{dashboard.weekly_goal.completed}<span className="text-base font-medium text-zinc-500">/{dashboard.weekly_goal.target}</span></p>
          <p className="mt-1 text-xs text-zinc-500">assessment items completed this week</p>
        </article>
        <article className="rounded-2xl bg-white/80 p-4 dark:bg-zinc-900/80 lg:col-span-2">
          <p className="flex items-center gap-2 text-sm font-semibold text-zinc-900 dark:text-white"><Target className="h-4 w-4 text-indigo-600" /> Next best action</p>
          {recommendation ? <><p className="mt-2 font-medium text-zinc-900 dark:text-white">Practice: {recommendation.title}</p><p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{recommendation.reason}</p><Link href={`/quiz?course=${encodeURIComponent(dashboard.course!.id)}&objective=${encodeURIComponent(recommendation.objective_id)}&difficulty=${encodeURIComponent(recommendation.difficulty)}`} className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-indigo-700 hover:underline dark:text-indigo-300">Start practice <ChevronRight className="h-4 w-4" /></Link></> : <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">Add learning objectives to this course to receive a recommendation.</p>}
        </article>
      </div>
      {dashboard.mastery.length > 0 && <div className="mt-6"><p className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-900 dark:text-white"><BookOpenCheck className="h-4 w-4 text-indigo-600" /> Objective mastery</p><div className="grid gap-3 md:grid-cols-3">{dashboard.mastery.slice(0, 3).map((objective) => <div key={objective.objective_id} className="rounded-xl bg-white/80 p-3 dark:bg-zinc-900/80"><div className="flex items-center justify-between gap-2"><p className="text-sm font-medium text-zinc-800 dark:text-zinc-100">{objective.title}</p><span className="text-xs text-zinc-500">{masteryLabel(objective.score)}</span></div><div className="mt-3 h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700"><div className="h-full rounded-full bg-indigo-600" style={{ width: `${Math.round(objective.score * 100)}%` }} /></div></div>)}</div></div>}
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl bg-white/80 p-4 dark:bg-zinc-900/80"><p className="text-sm font-semibold text-zinc-900 dark:text-white">Upcoming review</p>{dashboard.mastery.filter((item) => item.next_review_at).sort((a, b) => String(a.next_review_at).localeCompare(String(b.next_review_at))).slice(0, 3).map((item) => <p key={item.objective_id} className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">{item.title} · {new Date(item.next_review_at!).toLocaleDateString()}</p>)}{!dashboard.mastery.some((item) => item.next_review_at) && <p className="mt-2 text-sm text-zinc-500">Complete a practice item to schedule review.</p>}</article>
        <article className="rounded-2xl bg-white/80 p-4 dark:bg-zinc-900/80"><p className="text-sm font-semibold text-zinc-900 dark:text-white">Recent activity</p>{dashboard.recent_activity.slice(0, 3).map((item) => <p key={item.id} className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">{item.is_correct ? "Correct practice response" : "Practice response"} · {new Date(item.created_at).toLocaleDateString()}</p>)}{dashboard.recent_activity.length === 0 && <p className="mt-2 text-sm text-zinc-500">Your assessed practice will appear here.</p>}</article>
      </div>
    </section>
  );
}
