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
  if (error) return <p className="text-sm text-muted">Learning progress is temporarily unavailable.</p>;
  if (coursesLoaded && !courseId) {
    return <section className="rounded-2xl border border-primary/30 bg-primary-bg p-6 shadow-sm"><p className="text-sm font-semibold text-primary">Course catalog</p><h2 className="mt-2 text-xl font-bold text-foreground">Choose a course to begin</h2><p className="mt-2 text-sm text-muted">Course content remains private until you explicitly enroll.</p><div className="mt-5 grid gap-3 md:grid-cols-2">{catalog.filter((course) => !course.enrolled).map((availableCourse) => <article key={availableCourse.id} className="rounded-2xl bg-surface p-4 shadow-sm"><p className="text-xs font-semibold uppercase tracking-wide text-primary">{availableCourse.code}</p><h3 className="mt-1 font-semibold text-foreground">{availableCourse.title}</h3><p className="mt-2 text-sm text-muted">{availableCourse.description || "Course workspace"}</p><button type="button" disabled={enrolling} onClick={async () => { setEnrolling(true); try { await enrollInCourse(token, availableCourse.id); setCourses((items) => [...items, { ...availableCourse, membership_role: "student" }]); setCourseId(availableCourse.id); } catch { setError("Unable to enroll in this course"); } finally { setEnrolling(false); } }} className="btn-primary btn-sm mt-4">{enrolling ? "Joining…" : `Join ${availableCourse.code}`}</button></article>)}</div>{catalog.length === 0 && <p className="mt-4 text-sm text-muted">No courses are open for enrollment yet.</p>}</section>;
  }
  if (!dashboard) return <section className="rounded-2xl border border-line bg-surface p-6 shadow-sm"><div className="shimmer-line h-5 w-48" /></section>;

  const recommendation = dashboard.recommendation;
  return (
    <section aria-labelledby="learning-progress-title" className="rounded-2xl border border-line bg-surface p-6 shadow-sm sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.25em] text-primary"><CircleGauge className="h-4 w-4" /> Learning progress</p>
          <h2 id="learning-progress-title" className="mt-2 text-2xl font-bold text-foreground">{dashboard.course?.title ?? "Your course"}</h2>
        </div>
        {courses.length > 1 && <label className="text-sm font-medium text-foreground">Course <select value={courseId} onChange={(event) => setCourseId(event.target.value)} className="ml-2 rounded-lg border border-line bg-surface px-2 py-1.5"><option value="">Select</option>{courses.map((course) => <option key={course.id} value={course.id}>{course.code} — {course.title}</option>)}</select></label>}
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <article className="rounded-xl bg-surface-2 p-4">
          <p className="text-sm text-muted">Weekly practice</p>
          <p className="mt-2 font-display text-3xl font-bold text-foreground">{dashboard.weekly_goal.completed}<span className="text-base font-medium text-muted">/{dashboard.weekly_goal.target}</span></p>
          <p className="mt-1 text-xs text-muted">assessment items completed this week</p>
        </article>
        <article className="rounded-xl bg-surface-2 p-4 lg:col-span-2">
          <p className="flex items-center gap-2 text-sm font-semibold text-foreground"><Target className="h-4 w-4 text-primary" /> Next best action</p>
          {recommendation ? <><p className="mt-2 font-medium text-foreground">Practice: {recommendation.title}</p><p className="mt-1 text-sm text-muted">{recommendation.reason}</p><Link href={`/quiz?course=${encodeURIComponent(dashboard.course!.id)}&objective=${encodeURIComponent(recommendation.objective_id)}&difficulty=${encodeURIComponent(recommendation.difficulty)}`} className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline">Start practice <ChevronRight className="h-4 w-4" /></Link></> : <p className="mt-2 text-sm text-muted">Add learning objectives to this course to receive a recommendation.</p>}
        </article>
      </div>
      {dashboard.mastery.length > 0 && <div className="mt-6"><p className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground"><BookOpenCheck className="h-4 w-4 text-primary" /> Objective mastery</p><div className="grid gap-3 md:grid-cols-3">{dashboard.mastery.slice(0, 3).map((objective) => <div key={objective.objective_id} className="rounded-xl bg-surface-2 p-3"><div className="flex items-center justify-between gap-2"><p className="text-sm font-medium text-foreground">{objective.title}</p><span className="text-xs text-muted">{masteryLabel(objective.score)}</span></div><div className="mt-3 h-2.5 overflow-hidden rounded-full bg-line"><div className="h-full rounded-full bg-gradient-to-r from-[#1E3A8A] to-[#0D9488] dark:from-[#3B82F6] dark:to-[#14B8A6]" style={{ width: `${Math.round(objective.score * 100)}%` }} /></div></div>)}</div></div>}
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <article className="rounded-xl bg-surface-2 p-4"><p className="text-sm font-semibold text-foreground">Upcoming review</p>{dashboard.mastery.filter((item) => item.next_review_at).sort((a, b) => String(a.next_review_at).localeCompare(String(b.next_review_at))).slice(0, 3).map((item) => <p key={item.objective_id} className="mt-2 text-sm text-muted">{item.title} · {new Date(item.next_review_at!).toLocaleDateString()}</p>)}{!dashboard.mastery.some((item) => item.next_review_at) && <p className="mt-2 text-sm text-muted">Complete a practice item to schedule review.</p>}</article>
        <article className="rounded-xl bg-surface-2 p-4"><p className="text-sm font-semibold text-foreground">Recent activity</p>{dashboard.recent_activity.slice(0, 3).map((item) => <p key={item.id} className="mt-2 text-sm text-muted">{item.is_correct ? "Correct practice response" : "Practice response"} · {new Date(item.created_at).toLocaleDateString()}</p>)}{dashboard.recent_activity.length === 0 && <p className="mt-2 text-sm text-muted">Your assessed practice will appear here.</p>}</article>
      </div>
    </section>
  );
}
