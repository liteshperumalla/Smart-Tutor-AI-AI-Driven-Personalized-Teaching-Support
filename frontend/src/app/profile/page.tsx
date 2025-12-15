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

  const [profileForm, setProfileForm] = useState({
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
      <PageShell as="section">
        <p className="text-sm text-zinc-600">Loading your profile…</p>
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
      <header className="space-y-3">
        <p className="text-xs uppercase tracking-[0.35em] text-zinc-500">Profile</p>
        <h1 className="text-3xl font-semibold text-zinc-950">Manage your Smart AI Tutor account</h1>
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
                className="w-full rounded-full border border-zinc-200 px-4 py-2 text-xs font-semibold text-zinc-900 transition hover:bg-zinc-900 hover:text-white dark:border-zinc-600 dark:text-white dark:hover:bg-white dark:hover:text-zinc-900"
                disabled={pictureStatus.loading}
              >
                {pictureStatus.loading ? "Uploading…" : "Save photo"}
              </button>
            </form>
          </div>
        </article>

        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-zinc-900">Account overview</h2>
              <p className="text-sm text-zinc-500">Signed in as {profile.user.username}</p>
            </div>
            <span className="rounded-full bg-zinc-900 px-3 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-white">
              {profile.user.role}
            </span>
          </div>
          <dl className="mt-4 space-y-2 text-sm text-zinc-600">
            <div className="flex justify-between">
              <dt className="text-zinc-500">Email</dt>
              <dd className="font-medium text-zinc-900">{profile.user.email || "Not set"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-zinc-500">Last login</dt>
              <dd className="font-medium text-zinc-900">{formattedLastLogin}</dd>
            </div>
          </dl>
          <Link href="/" className="mt-6 inline-flex items-center text-sm font-medium text-blue-600">
            Back to home →
          </Link>
        </article>

        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-zinc-900">Recent highlights</h2>
          <div className="mt-4 grid gap-3 text-sm text-zinc-600">
            <div className="rounded-xl border border-zinc-100 bg-zinc-50 p-3">
              <p className="text-xs uppercase tracking-[0.3em] text-zinc-400">Quizzes</p>
              <p className="text-2xl font-semibold text-zinc-900">{profile.recent_quizzes.length}</p>
              <p className="text-xs text-zinc-500">Stored results in the last uploads folder.</p>
            </div>
            <div className="rounded-xl border border-zinc-100 bg-zinc-50 p-3">
              <p className="text-xs uppercase tracking-[0.3em] text-zinc-400">Appointments</p>
              <p className="text-2xl font-semibold text-zinc-900">{profile.recent_appointments.length}</p>
              <p className="text-xs text-zinc-500">Showing the five most recent requests.</p>
            </div>
          </div>
        </article>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-zinc-900">Full quiz history</h2>
            <span className="text-xs text-zinc-500">{quizHistory.length} total</span>
          </div>
          <div className="mt-4 space-y-3 max-h-[360px] overflow-auto pr-1">
            {quizHistory.length === 0 && <p className="text-sm text-zinc-500">No quiz attempts recorded.</p>}
            {quizHistory.map((quiz) => (
              <div key={quiz.id} className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 text-sm">
                <p className="font-semibold text-zinc-900">
                  {quiz.score}/{quiz.total_questions} · {quiz.percentage.toFixed(1)}%
                </p>
                <p className="text-xs text-zinc-500">{formatDate(quiz.created_at)}</p>
                {quiz.metadata?.selected_folders && Array.isArray(quiz.metadata.selected_folders) && (
                  <p className="text-xs text-zinc-500">
                    Folders: {(quiz.metadata.selected_folders as string[]).join(", ")}
                  </p>
                )}
              </div>
            ))}
          </div>
        </article>

        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-zinc-900">All appointment requests</h2>
            <span className="text-xs text-zinc-500">{appointmentHistory.length} total</span>
          </div>
          <div className="mt-4 space-y-3 max-h-[360px] overflow-auto pr-1">
            {appointmentHistory.length === 0 && <p className="text-sm text-zinc-500">No appointments submitted.</p>}
            {appointmentHistory.map((appt) => (
              <div key={appt.id} className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 text-sm">
                <p className="font-semibold text-zinc-900">
                  {appt.preferred_date} · {appt.preferred_time}
                </p>
                <p className="text-xs text-zinc-500">{appt.appointment_with}</p>
                <p className="text-xs text-zinc-500">Reason: {appt.primary_reason}</p>
                <p className="text-xs text-zinc-500">Status: {appt.status}</p>
                {appt.additional_details && <p className="text-xs text-zinc-500">{appt.additional_details}</p>}
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-zinc-900">Feedback submissions</h2>
          <Link href="/feedback" className="text-sm font-medium text-blue-600">
            Share more feedback
          </Link>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-zinc-500">General feedback</p>
            <div className="mt-2 space-y-3 max-h-[260px] overflow-auto pr-1">
              {feedbackHistory.feedback.length === 0 && <p className="text-sm text-zinc-500">No submissions yet.</p>}
              {feedbackHistory.feedback.map((entry, index) => (
                <div key={`fb-${index}`} className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 text-sm">
                  <p className="font-semibold text-zinc-900">{entry.category}</p>
                  <p className="text-xs text-zinc-500">{formatDate(entry.created_at)}</p>
                  <p className="text-xs text-zinc-600">{entry.message}</p>
                </div>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-zinc-500">Bug reports</p>
            <div className="mt-2 space-y-3 max-h-[260px] overflow-auto pr-1">
              {feedbackHistory.bugs.length === 0 && <p className="text-sm text-zinc-500">No bugs reported.</p>}
              {feedbackHistory.bugs.map((entry, index) => (
                <div key={`bug-${index}`} className="rounded-xl border border-zinc-100 bg-zinc-50 p-3 text-sm">
                  <p className="font-semibold text-zinc-900">{entry.feature}</p>
                  <p className="text-xs text-zinc-500">
                    Severity: {entry.severity} · {formatDate(entry.created_at)}
                  </p>
                  <p className="text-xs text-zinc-600">{entry.description}</p>
                  {entry.steps && <p className="text-xs text-zinc-500">Steps: {entry.steps}</p>}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-zinc-900">Contact details & theme</h2>
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
              onChange={(event) => setProfileForm((prev) => ({ ...prev, theme: event.target.value }))}
            >
              <option value="light">Light mode</option>
              <option value="dark">Dark mode</option>
            </select>
            {profileStatus.error && <p className="text-sm text-red-600">{profileStatus.error}</p>}
            {profileStatus.message && <p className="text-sm text-emerald-600">{profileStatus.message}</p>}
            <button
              type="submit"
              className="rounded-full bg-zinc-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              disabled={profileStatus.saving}
            >
              {profileStatus.saving ? "Saving…" : "Save changes"}
            </button>
          </form>
        </article>

        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-zinc-900">Personal notes</h2>
          <form className="mt-4 space-y-3" onSubmit={handleNotesSave}>
            <textarea
              className="input min-h-[200px]"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Jot down reminders or references—stored locally under your user folder."
            />
            {notesStatus.error && <p className="text-sm text-red-600">{notesStatus.error}</p>}
            {notesStatus.message && <p className="text-sm text-emerald-600">{notesStatus.message}</p>}
            <button
              type="submit"
              className="rounded-full border border-zinc-200 px-4 py-2 text-sm font-semibold text-zinc-900 transition hover:bg-zinc-900 hover:text-white disabled:opacity-60"
              disabled={notesStatus.saving}
            >
              {notesStatus.saving ? "Saving…" : "Save notes"}
            </button>
          </form>
        </article>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-zinc-900">Recent quiz history</h2>
            <Link href="/quiz" className="text-sm font-medium text-blue-600">
              Open quiz builder
            </Link>
          </div>
          <div className="mt-4 space-y-3">
            {profile.recent_quizzes.length === 0 && (
              <p className="text-sm text-zinc-500">No quiz submissions yet.</p>
            )}
            {profile.recent_quizzes.map((quiz) => {
              const selectedFolders =
                quiz.metadata && Array.isArray(quiz.metadata["selected_folders"])
                  ? (quiz.metadata["selected_folders"] as string[])
                  : null;
              return (
                <div key={quiz.id} className="rounded-xl border border-zinc-100 bg-zinc-50 p-4 text-sm text-zinc-700">
                  <p className="font-semibold text-zinc-900">
                    {quiz.score}/{quiz.total_questions} · {quiz.percentage.toFixed(1)}%
                  </p>
                  <p className="text-xs text-zinc-500">{formatDate(quiz.created_at)}</p>
                  {selectedFolders && selectedFolders.length > 0 && (
                    <p className="mt-1 text-xs text-zinc-500">Folders: {selectedFolders.join(", ")}</p>
                  )}
                </div>
              );
            })}
          </div>
        </article>

        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-zinc-900">Recent appointment requests</h2>
            <Link href="/appointments" className="text-sm font-medium text-blue-600">
              Schedule time
            </Link>
          </div>
          <div className="mt-4 space-y-3">
            {profile.recent_appointments.length === 0 && (
              <p className="text-sm text-zinc-500">No appointments logged yet.</p>
            )}
            {profile.recent_appointments.map((appt) => (
              <div key={appt.id} className="rounded-xl border border-zinc-100 bg-zinc-50 p-4 text-sm text-zinc-700">
                <p className="font-semibold text-zinc-900">{appt.appointment_with}</p>
                <p className="text-xs text-zinc-500">
                  {appt.preferred_date} at {appt.preferred_time} · {appt.primary_reason}
                </p>
                {appt.additional_details && <p className="mt-1 text-xs text-zinc-500">{appt.additional_details}</p>}
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-zinc-900">Password & security</h2>
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
            {passwordStatus.error && <p className="text-sm text-red-600">{passwordStatus.error}</p>}
            {passwordStatus.message && <p className="text-sm text-emerald-600">{passwordStatus.message}</p>}
            <button
              type="submit"
              className="rounded-full bg-zinc-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              disabled={passwordStatus.saving}
            >
              {passwordStatus.saving ? "Updating…" : "Update password"}
            </button>
          </form>
        </article>

        <article className="rounded-2xl border border-red-200 bg-red-50 p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-red-900">Danger zone</h2>
          <p className="mt-2 text-sm text-red-700">
            Deleting your account removes stored chat logs, quizzes, and research files from the local filesystem.
          </p>
          <form className="mt-4 space-y-3" onSubmit={handleDeleteAccount}>
            <input
              className="input border-red-200 bg-white/80"
              placeholder="Type your username to confirm"
              value={deleteConfirm}
              onChange={(event) => setDeleteConfirm(event.target.value)}
            />
            {deleteStatus.error && <p className="text-sm text-red-700">{deleteStatus.error}</p>}
            <button
              type="submit"
              className="rounded-full bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              disabled={deleteStatus.loading}
            >
              {deleteStatus.loading ? "Deleting…" : "Delete account"}
            </button>
          </form>
        </article>
      </section>
    </PageShell>
  );
}
