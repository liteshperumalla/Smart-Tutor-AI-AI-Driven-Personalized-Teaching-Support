"use client";

import { FormEvent, useEffect, useState } from "react";
import { BookOpen, Plus, ShieldCheck, Trash2, Users } from "lucide-react";
import { toast } from "sonner";
import { createCourse, fetchCourseMemberships, fetchCourses, removeCourseMembership, saveCourseMembership, type Course, type CourseMembership } from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";

function slug(value: string) {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export default function AdminCoursesPage() {
  const { token } = useAuthToken();
  const [courses, setCourses] = useState<Course[]>([]);
  const [courseId, setCourseId] = useState("");
  const [memberships, setMemberships] = useState<CourseMembership[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [openEnrollment, setOpenEnrollment] = useState(false);
  const [moduleTitle, setModuleTitle] = useState("");
  const [objectives, setObjectives] = useState("");
  const [memberUsername, setMemberUsername] = useState("");
  const [memberRole, setMemberRole] = useState<"student" | "instructor">("student");

  const loadCourses = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const items = await fetchCourses(token);
      setCourses(items);
      setCourseId((current) => current || items[0]?.id || "");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to load courses");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadCourses(); }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!token || !courseId) { setMemberships([]); return; }
    fetchCourseMemberships(token, courseId)
      .then(setMemberships)
      .catch((error) => toast.error(error instanceof Error ? error.message : "Unable to load course members"));
  }, [courseId, token]);

  async function createWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    const courseId = slug(code || title);
    const moduleId = slug(moduleTitle || "course-foundations");
    const objectiveRows = objectives.split("\n").map((value) => value.trim()).filter(Boolean).map((value, index) => ({ id: `${moduleId}-${index + 1}`, title: value, module_id: moduleId }));
    setSaving(true);
    try {
      await createCourse(token, {
        id: courseId,
        code: code.trim(),
        title: title.trim(),
        description: description.trim(),
        open_enrollment: openEnrollment,
        modules: moduleTitle || objectiveRows.length ? [{ id: moduleId, title: moduleTitle || "Course foundations", objectives: objectiveRows }] : [],
      });
      toast.success("Course workspace created");
      setCode(""); setTitle(""); setDescription(""); setModuleTitle(""); setObjectives(""); setOpenEnrollment(false);
      await loadCourses();
      setCourseId(courseId);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to create course workspace");
    } finally { setSaving(false); }
  }

  async function addMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !courseId) return;
    setSaving(true);
    try {
      const membership = await saveCourseMembership(token, courseId, memberUsername.trim(), memberRole);
      setMemberships((items) => [...items.filter((item) => item.username !== membership.username), membership].sort((a, b) => a.username.localeCompare(b.username)));
      setMemberUsername("");
      toast.success(`${membership.username} is now a ${membership.role}`);
    } catch (error) { toast.error(error instanceof Error ? error.message : "Unable to save course member"); }
    finally { setSaving(false); }
  }

  async function removeMember(membership: CourseMembership) {
    if (!token || !courseId || !window.confirm(`Remove ${membership.username} from this course?`)) return;
    try {
      await removeCourseMembership(token, courseId, membership.username);
      setMemberships((items) => items.filter((item) => item.username !== membership.username));
      toast.success("Course member removed");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Unable to remove course member"); }
  }

  return <div className="space-y-6">
    <header><h2 className="flex items-center gap-2 text-lg font-semibold text-zinc-900 dark:text-white"><BookOpen className="h-5 w-5" /> Course workspaces</h2><p className="mt-1 text-sm text-zinc-500">Create multi-course workspaces and manage course-level student and instructor access.</p></header>
    <div className="grid gap-6 xl:grid-cols-2">
      <form onSubmit={createWorkspace} className="space-y-4 rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900/60">
        <h3 className="flex items-center gap-2 font-semibold text-zinc-900 dark:text-white"><Plus className="h-4 w-4" /> Create workspace</h3>
        <div className="grid gap-4 sm:grid-cols-2"><label className="text-sm font-medium">Course code<input required value={code} onChange={(event) => setCode(event.target.value)} placeholder="CS 6310" className="mt-1.5 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-800" /></label><label className="text-sm font-medium">Course title<input required value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Machine Learning" className="mt-1.5 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-800" /></label></div>
        <label className="block text-sm font-medium">Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} className="mt-1.5 min-h-20 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-800" /></label>
        <label className="block text-sm font-medium">First module (optional)<input value={moduleTitle} onChange={(event) => setModuleTitle(event.target.value)} placeholder="Foundations" className="mt-1.5 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-800" /></label>
        <label className="block text-sm font-medium">Learning objectives, one per line<textarea value={objectives} onChange={(event) => setObjectives(event.target.value)} placeholder="Explain the core concepts\nApply a method to a new problem" className="mt-1.5 min-h-24 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-800" /></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={openEnrollment} onChange={(event) => setOpenEnrollment(event.target.checked)} /> Allow students to enroll themselves</label>
        <button disabled={saving} className="rounded-xl bg-zinc-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">Create course</button>
      </form>
      <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900/60">
        <h3 className="flex items-center gap-2 font-semibold text-zinc-900 dark:text-white"><Users className="h-4 w-4" /> Course membership</h3>
        {loading ? <p className="mt-4 text-sm text-zinc-500">Loading courses…</p> : <>
          <label className="mt-4 block text-sm font-medium">Active course
            <select value={courseId} onChange={(event) => setCourseId(event.target.value)} className="mt-1.5 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-800">
              {courses.map((course) => <option key={course.id} value={course.id}>{course.code} — {course.title}</option>)}
            </select>
          </label>
          <form onSubmit={addMember} className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto_auto]">
            <label className="sr-only" htmlFor="course-member">Username</label>
            <input id="course-member" required value={memberUsername} onChange={(event) => setMemberUsername(event.target.value)} placeholder="Username" className="rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800" />
            <select value={memberRole} onChange={(event) => setMemberRole(event.target.value as "student" | "instructor")} aria-label="Course role" className="rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"><option value="student">Student</option><option value="instructor">Instructor</option></select>
            <button disabled={!courseId || saving} className="rounded-xl border border-zinc-200 px-3 py-2 text-sm font-semibold hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800">Add</button>
          </form>
          <ul className="mt-4 divide-y divide-zinc-100 dark:divide-zinc-800">
            {memberships.map((membership) => <li key={membership.username} className="flex items-center justify-between gap-3 py-3"><div><p className="font-medium text-zinc-800 dark:text-zinc-200">{membership.username}</p><p className="flex items-center gap-1 text-xs text-zinc-500">{membership.role === "instructor" && <ShieldCheck className="h-3 w-3" />}{membership.role}</p></div><button onClick={() => removeMember(membership)} className="rounded-lg p-2 text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/30" aria-label={`Remove ${membership.username} from course`}><Trash2 className="h-4 w-4" /></button></li>)}
          </ul>
          {courseId && memberships.length === 0 && <p className="mt-4 text-sm text-zinc-500">No members have been added yet.</p>}
        </>}
      </section>
    </div>
  </div>;
}
