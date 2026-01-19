"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import {
  changeProfilePassword,
  deleteAccount,
  fetchFeedbackHistory,
  fetchProfile,
  fetchProfileAppointmentsHistory,
  fetchProfileQuizHistory,
  ProfileData,
  FeedbackHistory,
  updateProfileDetails,
  saveProfileNotes,
  uploadProfilePicture,
  QuizHistoryEntry,
  AppointmentRecord,
} from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { useTheme } from "@/context/theme-context";
import { PageShell } from "@/components/page-shell";
import {
  User, Camera, Mail, Phone, Calendar, Trophy, Clock,
  MessageSquare, Bug, Save, Lock, Shield, Trash2, StickyNote
} from "lucide-react";

function formatDate(value?: string) {
  if (!value) return "Unknown";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export default function ProfilePage() {
  const { token, setToken } = useAuthToken();
  const { setTheme } = useTheme();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [profileForm, setProfileForm] = useState<{
    display_name: string;
    phone_number: string;
    theme: "light" | "dark";
  }>({
    display_name: "",
    phone_number: "",
    theme: "light",
  });
  const [profileStatus, setProfileStatus] = useState<{ saving: boolean; message: string | null; error: string | null }>({
    saving: false,
    message: null,
    error: null,
  });

  const [notes, setNotes] = useState("");
  const [notesStatus, setNotesStatus] = useState<{ saving: boolean; message: string | null; error: string | null }>({
    saving: false,
    message: null,
    error: null,
  });

  const [passwordForm, setPasswordForm] = useState({
    current: "",
    next: "",
    confirm: "",
  });
  const [passwordStatus, setPasswordStatus] = useState<{ saving: boolean; message: string | null; error: string | null }>({
    saving: false,
    message: null,
    error: null,
  });

  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deleteStatus, setDeleteStatus] = useState<{ loading: boolean; error: string | null }>({
    loading: false,
    error: null,
  });
  const [pictureFile, setPictureFile] = useState<File | null>(null);
  const [pictureStatus, setPictureStatus] = useState<{ loading: boolean; error: string | null; success: string | null }>({
    loading: false,
    error: null,
    success: null,
  });
  const [quizHistory, setQuizHistory] = useState<QuizHistoryEntry[]>([]);
  const [appointmentHistory, setAppointmentHistory] = useState<AppointmentRecord[]>([]);
  const [feedbackHistory, setFeedbackHistory] = useState<FeedbackHistory>({ feedback: [], bugs: [] });

  useEffect(() => {
    if (!token) return;
    let isMounted = true;
    const frame = requestAnimationFrame(() => setLoading(true));
    fetchProfile(token)
      .then((data) => {
        if (!isMounted) return;
        setProfile(data);
        setProfileForm({
          display_name: data.user.display_name || "",
          phone_number: data.user.phone_number || "",
          theme: data.user.theme === "dark" ? "dark" : "light",
        });
        setTheme(data.user.theme === "dark" ? "dark" : "light");
        setNotes(data.notes || "");
        setError(null);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : "Unable to load your profile.");
      })
      .finally(() => {
        if (isMounted) {
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
      cancelAnimationFrame(frame);
    };
  }, [token, setTheme]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetchProfileQuizHistory(token)
      .then((results) => {
        if (!cancelled) {
          setQuizHistory(results);
        }
      })
      .catch(() => !cancelled && setQuizHistory([]));
    fetchProfileAppointmentsHistory(token)
      .then((items) => {
        if (!cancelled) {
          setAppointmentHistory(items);
        }
      })
      .catch(() => !cancelled && setAppointmentHistory([]));
    fetchFeedbackHistory(token)
      .then((data) => {
        if (!cancelled) {
          setFeedbackHistory(data);
        }
      })
      .catch(() => !cancelled && setFeedbackHistory({ feedback: [], bugs: [] }));

    return () => {
      cancelled = true;
    };
  }, [token]);

  const formattedLastLogin = profile?.user.last_login ? formatDate(profile.user.last_login) : "Never";

  async function handleProfileSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    setProfileStatus({ saving: true, message: null, error: null });
    try {
      const updated = await updateProfileDetails({ token, updates: profileForm });
      setProfile((prev) => (prev ? { ...prev, user: { ...prev.user, ...updated } } : prev));
      setTheme(updated.theme);
      setProfileStatus({ saving: false, message: "Profile updated.", error: null });
    } catch (err) {
      setProfileStatus({
        saving: false,
        message: null,
        error: err instanceof Error ? err.message : "Failed to save profile information.",
      });
    }
  }

  async function handlePictureSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !pictureFile) {
      setPictureStatus({ loading: false, error: "Choose an image to upload.", success: null });
      return;
    }
    setPictureStatus({ loading: true, error: null, success: null });
    try {
      const encoded = await uploadProfilePicture({ token, file: pictureFile });
      setProfile((prev) => (prev ? { ...prev, profile_picture: encoded || null } : prev));
      setPictureFile(null);
      setPictureStatus({ loading: false, error: null, success: "Profile picture updated." });
    } catch (err) {
      setPictureStatus({
        loading: false,
        success: null,
        error: err instanceof Error ? err.message : "Failed to upload picture.",
      });
    }
  }

  async function handleNotesSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    setNotesStatus({ saving: true, message: null, error: null });
    try {
      const saved = await saveProfileNotes({ token, content: notes });
      setNotes(saved);
      setNotesStatus({ saving: false, message: "Notes saved.", error: null });
    } catch (err) {
      setNotesStatus({
        saving: false,
        message: null,
        error: err instanceof Error ? err.message : "Failed to save notes.",
      });
    }
  }

  async function handlePasswordSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    if (passwordForm.next !== passwordForm.confirm) {
      setPasswordStatus({ saving: false, message: null, error: "New passwords do not match." });
      return;
    }
    setPasswordStatus({ saving: true, message: null, error: null });
    try {
      await changeProfilePassword({
        token,
        current_password: passwordForm.current,
        new_password: passwordForm.next,
      });
      setPasswordForm({ current: "", next: "", confirm: "" });
      setPasswordStatus({ saving: false, message: "Password updated.", error: null });
    } catch (err) {
      setPasswordStatus({
        saving: false,
        message: null,
        error: err instanceof Error ? err.message : "Could not update password.",
      });
    }
  }

  async function handleDeleteAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !profile) return;
    if (deleteConfirm !== profile.user.username) {
      setDeleteStatus({ loading: false, error: "Username confirmation does not match." });
      return;
    }
    setDeleteStatus({ loading: true, error: null });
    try {
      await deleteAccount({ token, confirm_username: deleteConfirm });
      setToken(null);
    } catch (err) {
      setDeleteStatus({
        loading: false,
        error: err instanceof Error ? err.message : "Failed to delete account.",
      });
    }
  }

  if (loading) {
    return (
      <PageShell className="max-w-5xl" contentClassName="gap-8">
        <header className="relative overflow-hidden rounded-3xl gradient-mesh p-12 animate-pulse">
          <div className="absolute top-0 right-0 h-64 w-64 bg-indigo-400/20 rounded-full blur-3xl"></div>
          <div className="absolute bottom-0 left-0 h-48 w-48 bg-amber-400/20 rounded-full blur-3xl" style={{animationDelay: '1s'}}></div>
          <div className="relative z-10 space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white/80 px-4 py-2 text-sm font-medium text-indigo-700 backdrop-blur dark:border-indigo-800 dark:bg-zinc-900/80 dark:text-indigo-300 mb-4">
              <div className="h-2 w-2 rounded-full bg-indigo-600 dark:bg-indigo-400"></div>
              <div className="h-4 w-20 bg-indigo-200 dark:bg-indigo-800 rounded"></div>
            </div>
            <div className="h-10 w-64 bg-zinc-200 dark:bg-zinc-700 rounded"></div>
            <div className="h-6 w-96 bg-zinc-200 dark:bg-zinc-700 rounded"></div>
          </div>
        </header>

        <section className="grid gap-4 md:grid-cols-3">
          <article className="rounded-2xl border border-zinc-200 bg-white p-6 text-sm dark:border-zinc-800 dark:bg-zinc-900">
            <div className="h-6 w-32 bg-zinc-200 dark:bg-zinc-700 rounded mb-4"></div>
            <div className="h-4 w-full bg-zinc-100 dark:bg-zinc-800 rounded mb-2"></div>
            <div className="flex flex-col items-center gap-3">
              <div className="h-32 w-32 rounded-full bg-zinc-200 dark:bg-zinc-700"></div>
              <div className="h-10 w-full bg-zinc-200 dark:bg-zinc-700 rounded"></div>
            </div>
          </article>
          <article className="rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
            <div className="h-6 w-48 bg-zinc-200 dark:bg-zinc-700 rounded mb-2"></div>
            <div className="h-4 w-32 bg-zinc-100 dark:bg-zinc-800 rounded mb-4"></div>
            <div className="h-4 w-full bg-zinc-100 dark:bg-zinc-800 rounded mb-2"></div>
            <div className="h-4 w-3/4 bg-zinc-100 dark:bg-zinc-800 rounded mb-4"></div>
            <div className="h-4 w-24 bg-zinc-100 dark:bg-zinc-800 rounded"></div>
          </article>
          <article className="rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
            <div className="h-6 w-40 bg-zinc-200 dark:bg-zinc-700 rounded mb-4"></div>
            <div className="grid gap-3 text-sm">
              <div className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-800">
                <div className="h-3 w-16 bg-zinc-200 dark:bg-zinc-600 rounded mb-2"></div>
                <div className="h-6 w-12 bg-zinc-300 dark:bg-zinc-500 rounded"></div>
              </div>
              <div className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-800">
                <div className="h-3 w-20 bg-zinc-200 dark:bg-zinc-600 rounded mb-2"></div>
                <div className="h-6 w-12 bg-zinc-300 dark:bg-zinc-500 rounded"></div>
              </div>
            </div>
          </article>
        </section>

        <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="h-6 w-40 bg-zinc-200 dark:bg-zinc-700 rounded mb-4"></div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-800">
                  <div className="h-4 w-24 bg-zinc-200 dark:bg-zinc-600 rounded mb-2"></div>
                  <div className="h-3 w-32 bg-zinc-100 dark:bg-zinc-700 rounded"></div>
                </div>
              ))}
            </div>
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-800">
                  <div className="h-4 w-24 bg-zinc-200 dark:bg-zinc-600 rounded mb-2"></div>
                  <div className="h-3 w-32 bg-zinc-100 dark:bg-zinc-700 rounded"></div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell as="section">
        <div className="rounded-2xl border border-red-200 bg-red-50 px-6 py-6 text-sm text-red-700">
          {error}
        </div>
      </PageShell>
    );
  }

  if (!profile) {
    return null;
  }

  return (
    <PageShell className="max-w-5xl" contentClassName="gap-8">
      <header className="relative overflow-hidden rounded-3xl gradient-mesh p-12 animate-fade-in-down">
        <div className="absolute top-0 right-0 h-64 w-64 bg-indigo-400/20 rounded-full blur-3xl animate-float"></div>
        <div className="absolute bottom-0 left-0 h-48 w-48 bg-amber-400/20 rounded-full blur-3xl" style={{animationDelay: '1s'}}></div>

        <div className="relative z-10">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white/80 px-4 py-2 text-sm font-medium text-indigo-700 backdrop-blur dark:border-indigo-800 dark:bg-zinc-900/80 dark:text-indigo-300 mb-4">
            <User className="h-4 w-4" />
            Profile
          </div>
          <h1 className="font-display text-5xl font-bold text-zinc-900 dark:text-white">
            Manage your account
          </h1>
          <p className="mt-4 text-lg text-zinc-600 max-w-2xl dark:text-zinc-400">
            Update your profile, track your progress, and manage your settings
          </p>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="rounded-2xl border border-zinc-200 bg-white p-6 text-sm text-zinc-600 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">Profile photo</h2>
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            Upload a square PNG or JPG. Stored locally in your user folder.
          </p>
          <div className="mt-4 flex flex-col items-center gap-3">
            <div className="h-32 w-32 overflow-hidden rounded-full border border-dashed border-zinc-300 dark:border-zinc-600">
              {profile.profile_picture ? (
                <Image
                  src={profile.profile_picture}
                  alt="Profile"
                  width={128}
                  height={128}
                  className="h-full w-full object-cover"
                  sizes="128px"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-xs text-zinc-400">No photo</div>
              )}
            </div>
            <form className="w-full space-y-3" onSubmit={handlePictureSubmit}>
              <input
                type="file"
                accept="image/png,image/jpeg"
                onChange={(event) => setPictureFile(event.target.files?.[0] || null)}
                className="w-full text-xs text-zinc-600 dark:text-zinc-300"
              />
              {pictureStatus.error && <p className="text-xs text-red-500">{pictureStatus.error}</p>}
              {pictureStatus.success && <p className="text-xs text-emerald-500">{pictureStatus.success}</p>}
              <button
                type="submit"
                className="w-full btn-secondary text-xs disabled:opacity-60 disabled:hover:scale-100"
                disabled={pictureStatus.loading}
              >
                {pictureStatus.loading ? (
                  <><span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-zinc-900 border-t-transparent dark:border-white"></span> Uploading…</>
                ) : (
                  "Save photo"
                )}
              </button>
            </form>
          </div>
        </article>

        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">Account overview</h2>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Signed in as {profile.user.username}</p>
            </div>
            <span className="rounded-full bg-zinc-900 px-3 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-white dark:bg-white dark:text-zinc-900">
              {profile.user.role}
            </span>
          </div>
          <dl className="mt-4 space-y-2 text-sm text-zinc-600 dark:text-zinc-400">
            <div className="flex justify-between">
              <dt className="text-zinc-500 dark:text-zinc-400">Email</dt>
              <dd className="font-medium text-zinc-900 dark:text-white">{profile.user.email || "Not set"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-zinc-500 dark:text-zinc-400">Last login</dt>
              <dd className="font-medium text-zinc-900 dark:text-white">{formattedLastLogin}</dd>
            </div>
          </dl>
          <Link href="/" className="mt-6 inline-flex items-center text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline">
            Back to home →
          </Link>
        </article>

        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-white">Recent highlights</h2>
          <div className="mt-4 grid gap-3 text-sm text-zinc-600 dark:text-zinc-400">
            <div className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-800">
              <p className="text-xs uppercase tracking-[0.3em] text-zinc-400 dark:text-zinc-500">Quizzes</p>
              <p className="text-2xl font-semibold text-zinc-900 dark:text-white">{profile.recent_quizzes.length}</p>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">Stored results in the last uploads folder.</p>
            </div>
            <div className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-800">
              <p className="text-xs uppercase tracking-[0.3em] text-zinc-400 dark:text-zinc-500">Appointments</p>
              <p className="text-2xl font-semibold text-zinc-900 dark:text-white">{profile.recent_appointments.length}</p>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">Showing the five most recent requests.</p>
            </div>
          </div>
        </article>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-white">Full quiz history</h2>
            <span className="text-xs text-zinc-500 dark:text-zinc-400">{quizHistory.length} total</span>
          </div>
          <div className="mt-4 space-y-3 max-h-[360px] overflow-auto pr-1">
            {quizHistory.length === 0 && <p className="text-sm text-zinc-500 dark:text-zinc-400">No quiz attempts recorded.</p>}
            {quizHistory.map((quiz) => (
              <div key={quiz.id} className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 text-sm dark:border-zinc-700 dark:bg-zinc-800">
                <p className="font-semibold text-zinc-900 dark:text-white">
                  {quiz.score}/{quiz.total_questions} · {quiz.percentage.toFixed(1)}%
                </p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">{formatDate(quiz.created_at)}</p>
                {quiz.metadata &&
                  "selected_folders" in quiz.metadata &&
                  Array.isArray(quiz.metadata.selected_folders) &&
                  quiz.metadata.selected_folders.every((item: unknown) => typeof item === "string") && (
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    Folders: {(quiz.metadata.selected_folders as string[]).join(", ")}
                  </p>
                )}
              </div>
            ))}
          </div>
        </article>

        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-white">All appointment requests</h2>
            <span className="text-xs text-zinc-500 dark:text-zinc-400">{appointmentHistory.length} total</span>
          </div>
          <div className="mt-4 space-y-3 max-h-[360px] overflow-auto pr-1">
            {appointmentHistory.length === 0 && <p className="text-sm text-zinc-500 dark:text-zinc-400">No appointments submitted.</p>}
            {appointmentHistory.map((appt) => (
              <div key={appt.id} className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 text-sm dark:border-zinc-700 dark:bg-zinc-800">
                <p className="font-semibold text-zinc-900 dark:text-white">
                  {appt.preferred_date} · {appt.preferred_time}
                </p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">{appt.appointment_with}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Reason: {appt.primary_reason}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Status: {appt.status}</p>
                {appt.additional_details && <p className="text-xs text-zinc-500 dark:text-zinc-400">{appt.additional_details}</p>}
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-white">Feedback submissions</h2>
          <Link href="/feedback" className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline">
            Share more feedback
          </Link>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-zinc-500 dark:text-zinc-400">General feedback</p>
            <div className="mt-2 space-y-3 max-h-[260px] overflow-auto pr-1">
              {feedbackHistory.feedback.length === 0 && <p className="text-sm text-zinc-500 dark:text-zinc-400">No submissions yet.</p>}
              {feedbackHistory.feedback.map((entry, index) => (
                <div key={`fb-${index}`} className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 text-sm dark:border-zinc-700 dark:bg-zinc-800">
                  <p className="font-semibold text-zinc-900 dark:text-white">{entry.category}</p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">{formatDate(entry.created_at)}</p>
                  <p className="text-xs text-zinc-600 dark:text-zinc-300">{entry.message}</p>
                </div>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-zinc-500 dark:text-zinc-400">Bug reports</p>
            <div className="mt-2 space-y-3 max-h-[260px] overflow-auto pr-1">
              {feedbackHistory.bugs.length === 0 && <p className="text-sm text-zinc-500 dark:text-zinc-400">No bugs reported.</p>}
              {feedbackHistory.bugs.map((entry, index) => (
                <div key={`bug-${index}`} className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 text-sm dark:border-zinc-700 dark:bg-zinc-800">
                  <p className="font-semibold text-zinc-900 dark:text-white">{entry.feature}</p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    Severity: {entry.severity} · {formatDate(entry.created_at)}
                  </p>
                  <p className="text-xs text-zinc-600 dark:text-zinc-300">{entry.description}</p>
                  {entry.steps && <p className="text-xs text-zinc-500 dark:text-zinc-400">Steps: {entry.steps}</p>}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-700 dark:bg-zinc-800">
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">Contact details & theme</h2>
          <form className="mt-4 space-y-4" onSubmit={handleProfileSubmit}>
            <input
              name="display_name"
              placeholder="Display name"
              className="input"
              value={profileForm.display_name}
              onChange={(event) => setProfileForm((prev) => ({ ...prev, display_name: event.target.value }))}
            />
            <input
              name="phone_number"
              placeholder="Phone number"
              className="input"
              value={profileForm.phone_number}
              onChange={(event) => setProfileForm((prev) => ({ ...prev, phone_number: event.target.value }))}
            />
            <select
              name="theme"
              className="input"
              value={profileForm.theme}
              onChange={(event) => setProfileForm((prev) => ({ ...prev, theme: event.target.value as "light" | "dark" }))}
            >
              <option value="light">Light mode</option>
              <option value="dark">Dark mode</option>
            </select>
            {profileStatus.error && <p className="text-sm text-red-600 dark:text-red-400">{profileStatus.error}</p>}
            {profileStatus.message && <p className="text-sm text-emerald-600 dark:text-emerald-400">{profileStatus.message}</p>}
            <button
              type="submit"
              className="btn-primary disabled:opacity-60 disabled:hover:scale-100"
              disabled={profileStatus.saving}
            >
              {profileStatus.saving ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Saving…</>
              ) : (
                "Save changes"
              )}
            </button>
          </form>
        </article>

        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-700 dark:bg-zinc-800">
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">Personal notes</h2>
          <form className="mt-4 space-y-3" onSubmit={handleNotesSave}>
            <textarea
              className="input min-h-[200px]"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Jot down reminders or references—stored locally under your user folder."
            />
            {notesStatus.error && <p className="text-sm text-red-600 dark:text-red-400">{notesStatus.error}</p>}
            {notesStatus.message && <p className="text-sm text-emerald-600 dark:text-emerald-400">{notesStatus.message}</p>}
            <button
              type="submit"
              className="btn-secondary disabled:opacity-60 disabled:hover:scale-100"
              disabled={notesStatus.saving}
            >
              {notesStatus.saving ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-zinc-900 border-t-transparent dark:border-white"></span> Saving…</>
              ) : (
                "Save notes"
              )}
            </button>
          </form>
        </article>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-700 dark:bg-zinc-800">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">Recent quiz history</h2>
            <Link href="/quiz" className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline">
              Open quiz builder
            </Link>
          </div>
          <div className="mt-4 space-y-3">
            {profile.recent_quizzes.length === 0 && (
              <p className="text-sm text-zinc-500 dark:text-zinc-400">No quiz submissions yet.</p>
            )}
            {profile.recent_quizzes.map((quiz) => {
              const selectedFolders =
                quiz.metadata && Array.isArray(quiz.metadata["selected_folders"])
                  ? (quiz.metadata["selected_folders"] as string[])
                  : null;
              return (
                <div key={quiz.id} className="rounded-xl border border-zinc-100 bg-zinc-50 p-4 text-sm text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                  <p className="font-semibold text-zinc-900 dark:text-white">
                    {quiz.score}/{quiz.total_questions} · {quiz.percentage.toFixed(1)}%
                  </p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">{formatDate(quiz.created_at)}</p>
                  {selectedFolders && selectedFolders.length > 0 && (
                    <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">Folders: {selectedFolders.join(", ")}</p>
                  )}
                </div>
              );
            })}
          </div>
        </article>

        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-700 dark:bg-zinc-800">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">Recent appointment requests</h2>
            <Link href="/appointments" className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline">
              Schedule time
            </Link>
          </div>
          <div className="mt-4 space-y-3">
            {profile.recent_appointments.length === 0 && (
              <p className="text-sm text-zinc-500 dark:text-zinc-400">No appointments logged yet.</p>
            )}
            {profile.recent_appointments.map((appt) => (
              <div key={appt.id} className="rounded-xl border border-zinc-100 bg-zinc-50 p-4 text-sm text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                <p className="font-semibold text-zinc-900 dark:text-white">{appt.appointment_with}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  {appt.preferred_date} at {appt.preferred_time} · {appt.primary_reason}
                </p>
                {appt.additional_details && <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{appt.additional_details}</p>}
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-700 dark:bg-zinc-800">
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">Password & security</h2>
          <form className="mt-4 space-y-3" onSubmit={handlePasswordSubmit}>
            <input
              type="password"
              name="current_password"
              className="input"
              placeholder="Current password"
              value={passwordForm.current}
              onChange={(event) => setPasswordForm((prev) => ({ ...prev, current: event.target.value }))}
              required
            />
            <input
              type="password"
              name="new_password"
              className="input"
              placeholder="New password"
              value={passwordForm.next}
              onChange={(event) => setPasswordForm((prev) => ({ ...prev, next: event.target.value }))}
              required
            />
            <input
              type="password"
              name="confirm_password"
              className="input"
              placeholder="Confirm new password"
              value={passwordForm.confirm}
              onChange={(event) => setPasswordForm((prev) => ({ ...prev, confirm: event.target.value }))}
              required
            />
            {passwordStatus.error && <p className="text-sm text-red-600 dark:text-red-400">{passwordStatus.error}</p>}
            {passwordStatus.message && <p className="text-sm text-emerald-600 dark:text-emerald-400">{passwordStatus.message}</p>}
            <button
              type="submit"
              className="btn-primary disabled:opacity-60 disabled:hover:scale-100"
              disabled={passwordStatus.saving}
            >
              {passwordStatus.saving ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Updating…</>
              ) : (
                "Update password"
              )}
            </button>
          </form>
        </article>

        <article className="rounded-2xl border border-red-200 bg-red-50 p-6 shadow-sm dark:border-red-900/50 dark:bg-red-900/20">
          <h2 className="text-xl font-semibold text-red-900 dark:text-red-400">Danger zone</h2>
          <p className="mt-2 text-sm text-red-700 dark:text-red-400/80">
            Deleting your account removes stored chat logs, quizzes, and research files from the local filesystem.
          </p>
          <form className="mt-4 space-y-3" onSubmit={handleDeleteAccount}>
            <input
              className="input border-red-200 bg-white/80 dark:border-red-900/50 dark:bg-red-900/20 dark:text-white"
              placeholder="Type your username to confirm"
              value={deleteConfirm}
              onChange={(event) => setDeleteConfirm(event.target.value)}
            />
            {deleteStatus.error && <p className="text-sm text-red-700 dark:text-red-400">{deleteStatus.error}</p>}
            <button
              type="submit"
              className="rounded-full bg-red-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-red-600/30 transition hover:scale-105 hover:shadow-xl disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100"
              disabled={deleteStatus.loading}
            >
              {deleteStatus.loading ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Deleting…</>
              ) : (
                "Delete account"
              )}
            </button>
          </form>
        </article>
      </section>
    </PageShell>
  );
}
