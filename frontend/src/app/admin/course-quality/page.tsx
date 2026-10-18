"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { BarChart3, CheckCircle2, Database, FileWarning, Loader2, Plus, RefreshCw, RotateCw, UploadCloud } from "lucide-react";
import { useAuthToken } from "@/hooks/useAuthToken";
import {
  Course,
  CourseIngestionStatus,
  EvaluationCase,
  ObjectiveCoverage,
  InstructorSummary,
  createCourseEvaluationCase,
  fetchCourseEvaluationCases,
  fetchCourseIngestionStatus,
  fetchCourses,
  fetchObjectiveCoverage,
  fetchInstructorSummary,
  runCourseEvaluationSuite,
  reindexCourseResource,
  uploadCourseResource,
} from "@/lib/api";

export default function CourseQualityPage() {
  const { token } = useAuthToken({ redirectTo: "/login" });
  const [courses, setCourses] = useState<Course[]>([]);
  const [courseId, setCourseId] = useState("info-5731");
  const [ingestion, setIngestion] = useState<CourseIngestionStatus | null>(null);
  const [coverage, setCoverage] = useState<ObjectiveCoverage | null>(null);
  const [instructorSummary, setInstructorSummary] = useState<InstructorSummary | null>(null);
  const [cases, setCases] = useState<EvaluationCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [query, setQuery] = useState("");
  const [topics, setTopics] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [noInstructorCourses, setNoInstructorCourses] = useState(false);
  const [lastRunSummary, setLastRunSummary] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const available = await fetchCourses(token);
      const manageable = available.filter((course) => course.membership_role !== "student");
      setCourses(manageable);
      setNoInstructorCourses(manageable.length === 0);
      const selected = manageable.some((course) => course.id === courseId) ? courseId : manageable[0]?.id;
      if (!selected) return;
      if (selected !== courseId) setCourseId(selected);
      const [nextIngestion, nextCoverage, nextCases, nextSummary] = await Promise.all([
        fetchCourseIngestionStatus(token, selected),
        fetchObjectiveCoverage(token, selected),
        fetchCourseEvaluationCases(token, selected),
        fetchInstructorSummary(token, selected),
      ]);
      setIngestion(nextIngestion);
      setCoverage(nextCoverage);
      setCases(nextCases);
      setInstructorSummary(nextSummary);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not load course quality data");
    } finally {
      setLoading(false);
    }
  }, [token, courseId]);

  useEffect(() => { load(); }, [load]);

  const addCase = async () => {
    if (!token || !query.trim()) return;
    setSaving(true);
    try {
      await createCourseEvaluationCase(token, courseId, {
        query: query.trim(),
        category: "course",
        difficulty: "medium",
        expected_topics: topics.split(",").map((topic) => topic.trim()).filter(Boolean),
      });
      setQuery("");
      setTopics("");
      toast.success("Course evaluation case added");
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not add evaluation case");
    } finally {
      setSaving(false);
    }
  };

  const runSuite = async () => {
    if (!token || cases.length === 0) return;
    setRunning(true);
    try {
      const result = await runCourseEvaluationSuite(token, courseId);
      toast.success(`Completed ${result.analysis.total_tests} course evaluation cases`);
      setLastRunSummary(`Last run: ${result.analysis.total_tests} cases · ${(result.analysis.generation_summary.avg_relevance_score * 100).toFixed(0)}% average relevance`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Evaluation run failed");
    } finally {
      setRunning(false);
    }
  };

  const uploadSource = async () => {
    if (!token || !file) return;
    setSaving(true);
    try {
      await uploadCourseResource(token, courseId, file);
      setFile(null);
      toast.success("Course source uploaded; indexing has started");
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not upload course source");
    } finally {
      setSaving(false);
    }
  };

  const retryIndexing = async (resourceId: string) => {
    if (!token) return;
    setSaving(true);
    try {
      await reindexCourseResource(token, courseId, resourceId);
      toast.success("Indexing retry started");
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not restart indexing");
    } finally { setSaving(false); }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-zinc-900 dark:text-white"><BarChart3 className="h-5 w-5" /> Course quality</h2>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">Track source readiness, assessment coverage, and course-grounded RAG benchmarks.</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="sr-only" htmlFor="quality-course">Course</label><select id="quality-course" value={courseId} onChange={(event) => setCourseId(event.target.value)} className="rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
            {courses.map((course) => <option key={course.id} value={course.id}>{course.code} — {course.title}</option>)}
          </select>
          <button onClick={load} className="rounded-xl border border-zinc-200 p-2 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800" aria-label="Refresh course quality"><RefreshCw className="h-4 w-4" /></button>
        </div>
      </div>

      {loading ? <div className="flex justify-center py-16"><Loader2 className="h-7 w-7 animate-spin text-zinc-500" /></div> : noInstructorCourses ? <div className="rounded-2xl border border-zinc-200 bg-white p-8 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60">You are not an instructor for any course workspace yet.</div> : <>
        <section className="grid gap-4 md:grid-cols-3">
          <Metric icon={UploadCloud} label="Course documents" value={ingestion?.total_documents ?? 0} detail={`${ingestion?.status_counts.complete ?? 0} indexed`} />
          <Metric icon={CheckCircle2} label="Objective coverage" value={`${coverage?.coverage_pct ?? 0}%`} detail={`${coverage?.covered_objectives ?? 0} of ${coverage?.total_objectives ?? 0} objectives have items`} />
          <Metric icon={Database} label="Evaluation cases" value={cases.length} detail="Course-scoped benchmark cases" />
        </section>

        <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900/60">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-semibold text-zinc-900 dark:text-white">Class learning signals</h3><p className="text-sm text-zinc-500">Aggregated evidence only; individual learner records remain private.</p></div><span className="rounded-full bg-indigo-50 px-3 py-1 text-sm font-medium text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300">{instructorSummary?.enrolled_students ?? 0} enrolled students</span></div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">{instructorSummary?.objectives.slice().sort((a, b) => (a.average_mastery ?? -1) - (b.average_mastery ?? -1)).map((objective) => <div key={objective.objective_id} className="rounded-xl bg-zinc-50 p-3 dark:bg-zinc-800/50"><div className="flex items-center justify-between gap-3"><p className="font-medium text-zinc-800 dark:text-zinc-200">{objective.title}</p><span className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">{objective.average_mastery === null ? "No evidence" : `${Math.round(objective.average_mastery * 100)}%`}</span></div><p className="mt-1 text-xs text-zinc-500">{objective.student_count} assessed learners{objective.average_mastery !== null && objective.average_mastery < 0.5 ? " · needs attention" : ""}</p></div>)}</div>
        </section>

        <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900/60">
          <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold text-zinc-900 dark:text-white">Content ingestion status</h3><div className="flex items-center gap-2"><label className="sr-only" htmlFor="course-source">Course source file</label><input id="course-source" type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="max-w-48 text-xs" /><button onClick={uploadSource} disabled={!file || saving} className="rounded-xl border border-zinc-200 px-3 py-2 text-sm font-medium hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-800">Upload source</button></div></div>
          {ingestion?.documents.length ? <div className="mt-4 space-y-2">{ingestion.documents.map((document) => <div key={document.resource_id} className="flex items-center justify-between gap-4 rounded-xl bg-zinc-50 px-4 py-3 text-sm dark:bg-zinc-800/50"><div className="min-w-0"><p className="truncate font-medium text-zinc-800 dark:text-zinc-200">{document.file_name || document.title}</p><p className="text-xs text-zinc-500">{document.chunks_created} chunks · {document.progress_pct}%{document.error ? ` · ${document.error}` : ""}</p></div><div className="flex items-center gap-2"><StatusPill status={document.status} />{document.indexable && document.status !== "complete" && <button onClick={() => retryIndexing(document.resource_id)} disabled={saving} className="rounded-lg border border-zinc-200 p-1.5 text-zinc-600 hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-800" aria-label={`Retry indexing ${document.file_name || document.title}`}><RotateCw className="h-3.5 w-3.5" /></button>}</div></div>)}</div> : <Empty icon={FileWarning} text="No course-scoped files yet. Assign a course workspace when uploading a resource." />}
        </section>

        <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900/60">
          <h3 className="font-semibold text-zinc-900 dark:text-white">Objective-to-quiz coverage</h3>
          <div className="mt-4 divide-y divide-zinc-100 dark:divide-zinc-800">{coverage?.objectives.map((objective) => <div key={objective.objective_id} className="flex items-center justify-between gap-4 py-3 text-sm"><div><p className="font-medium text-zinc-800 dark:text-zinc-200">{objective.title}</p><p className="text-xs text-zinc-500">{objective.assessed_item_count} assessed responses</p></div><span className={objective.covered ? "rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300" : "rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-700 dark:bg-amber-950/40 dark:text-amber-300"}>{objective.quiz_item_count} quiz items</span></div>)}</div>
        </section>

        <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900/60">
          <div className="flex items-center justify-between gap-3"><div><h3 className="font-semibold text-zinc-900 dark:text-white">Course evaluation dataset</h3><p className="text-sm text-zinc-500">Only these cases are used by the course evaluation runner.</p>{lastRunSummary && <p className="mt-1 text-xs font-medium text-emerald-700 dark:text-emerald-300">{lastRunSummary}</p>}</div><button onClick={runSuite} disabled={running || cases.length === 0} className="rounded-xl bg-zinc-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-white dark:text-zinc-900">{running ? "Running…" : "Run suite"}</button></div>
          <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto]"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Evaluation question" className="rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" /><input value={topics} onChange={(event) => setTopics(event.target.value)} placeholder="Expected topics, comma separated" className="rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" /><button onClick={addCase} disabled={saving || !query.trim()} className="flex items-center justify-center gap-1 rounded-xl border border-zinc-200 px-3 py-2 text-sm font-medium hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-800"><Plus className="h-4 w-4" /> Add</button></div>
          {cases.length ? <ul className="mt-4 space-y-2">{cases.map((item) => <li key={item.id} className="rounded-xl bg-zinc-50 px-3 py-2 text-sm text-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-300">{item.query}</li>)}</ul> : <Empty icon={Database} text="Add the first course-specific evaluation question to establish a benchmark." />}
        </section>
      </>}
    </div>
  );
}

function Metric({ icon: Icon, label, value, detail }: { icon: typeof BarChart3; label: string; value: string | number; detail: string }) { return <div className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900/60"><Icon className="h-5 w-5 text-indigo-500" /><p className="mt-3 text-2xl font-bold text-zinc-900 dark:text-white">{value}</p><p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{label}</p><p className="mt-1 text-xs text-zinc-500">{detail}</p></div>; }
function Empty({ icon: Icon, text }: { icon: typeof Database; text: string }) { return <div className="mt-4 flex items-center gap-2 rounded-xl bg-zinc-50 p-4 text-sm text-zinc-500 dark:bg-zinc-800/50"><Icon className="h-4 w-4" />{text}</div>; }
function StatusPill({ status }: { status: string }) { const ok = status === "complete"; const failed = status === "error"; return <span className={ok ? "rounded-full bg-emerald-100 px-2.5 py-1 text-xs text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300" : failed ? "rounded-full bg-red-100 px-2.5 py-1 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300" : "rounded-full bg-amber-100 px-2.5 py-1 text-xs text-amber-700 dark:bg-amber-950/40 dark:text-amber-300"}>{status.replace("_", " ")}</span>; }
