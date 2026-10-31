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
import { PageHero } from "@/components/page-hero";
import { User, MessageSquare, Shield, ShieldAlert, BarChart3, Users } from "lucide-react";
import { toast } from "sonner";
import { SkeletonRegion } from "@/components/skeleton";

function formatDate(value?: string) {
  if (!value) return "Unknown";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export default function ProfilePage() {
  const { token, setToken } = useAuthToken();
  const { theme, setTheme } = useTheme();
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
    fetchProfile(token)
      .then((data) => {
        if (!isMounted) return;
        setProfile(data);
        setProfileForm({
          display_name: data.user.display_name || "",
          phone_number: data.user.phone_number || "",
          // Show the theme the app is actually using. Applying the saved
          // profile value here used to flip the whole app (usually to light)
          // every time this page opened, overriding the sidebar toggle.
          theme,
        });
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
    };
    // Load once per session token; later theme changes are synced below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Keep the form's theme field in step with the sidebar toggle.
  useEffect(() => {
    setProfileForm((prev) => (prev.theme === theme ? prev : { ...prev, theme }));
  }, [theme]);

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
      toast.success("Profile updated");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to save profile information.";
      setProfileStatus({ saving: false, message: null, error: msg });
      toast.error(msg);
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
      toast.success("Profile picture updated");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to upload picture.";
      setPictureStatus({ loading: false, success: null, error: msg });
      toast.error(msg);
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
      toast.success("Notes saved");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to save notes.";
      setNotesStatus({ saving: false, message: null, error: msg });
      toast.error(msg);
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
      toast.success("Password updated");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not update password.";
      setPasswordStatus({ saving: false, message: null, error: msg });
      toast.error(msg);
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
      <PageShell className="max-w-5xl" contentClassName="gap-8" noCard>
        <SkeletonRegion label="Loading your profile" className="contents">
        <header className="relative overflow-hidden rounded-3xl p-6 sm:p-8 lg:p-12">
          <div className="relative z-10 space-y-4">
            <div className="skeleton h-10 w-64"></div>
            <div className="skeleton h-6 w-96 max-w-full"></div>
          </div>
        </header>

        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
          <article className="rounded-2xl border border-line bg-surface p-6 text-sm">
            <div className="skeleton h-6 w-32 mb-4"></div>
            <div className="skeleton h-4 w-full mb-2"></div>
            <div className="flex flex-col items-center gap-3">
              <div className="skeleton h-32 w-32 rounded-full"></div>
              <div className="skeleton h-10 w-full"></div>
            </div>
          </article>
          <article className="rounded-2xl border border-line bg-surface p-6">
            <div className="skeleton h-6 w-48 mb-2"></div>
            <div className="skeleton h-4 w-32 mb-4"></div>
            <div className="skeleton h-4 w-full mb-2"></div>
            <div className="skeleton h-4 w-3/4 mb-4"></div>
            <div className="skeleton h-4 w-24"></div>
          </article>
          <article className="rounded-2xl border border-line bg-surface p-6">
            <div className="skeleton h-6 w-40 mb-4"></div>
            <div className="grid gap-3 text-sm">
              <div className="rounded-xl border border-line bg-surface-2 p-3">
                <div className="skeleton h-3 w-16 mb-2"></div>
                <div className="skeleton h-6 w-12"></div>
              </div>
              <div className="rounded-xl border border-line bg-surface-2 p-3">
                <div className="skeleton h-3 w-20 mb-2"></div>
                <div className="skeleton h-6 w-12"></div>
              </div>
            </div>
          </article>
        </section>

        <section className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
          <div className="skeleton h-6 w-40 mb-4"></div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="rounded-xl border border-line bg-surface-2 p-3">
                  <div className="skeleton h-4 w-24 mb-2"></div>
                  <div className="skeleton h-3 w-32"></div>
                </div>
              ))}
            </div>
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="rounded-xl border border-line bg-surface-2 p-3">
                  <div className="skeleton h-4 w-24 mb-2"></div>
                  <div className="skeleton h-3 w-32"></div>
                </div>
              ))}
            </div>
          </div>
        </section>
        </SkeletonRegion>
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell as="section">
        <div className="rounded-2xl border border-danger/30 bg-danger-bg px-6 py-6 text-sm text-danger">
          {error}
        </div>
      </PageShell>
    );
  }

  if (!profile) {
    return null;
  }

  return (
    <PageShell className="max-w-5xl" contentClassName="gap-8 animate-fade-in-up" noCard>
      <PageHero
        icon={User}
        title="Manage your"
        accent="account"
        subtitle="Update your profile, track your progress, and manage your settings."
      />

      {profile.user.role === "Admin" && (
        <section className="rounded-2xl border border-warning/40 bg-warning-bg p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <ShieldAlert className="h-5 w-5 text-warning" />
            <h2 className="text-lg font-semibold text-warning">Admin Quick Access</h2>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-2 md:grid-cols-4">
            <Link href="/admin" className="flex items-center gap-2.5 rounded-xl border border-warning/40 bg-surface px-4 py-3 text-sm font-medium text-warning hover:bg-warning-bg transition-colors">
              <ShieldAlert className="h-4 w-4" />
              Dashboard
            </Link>
            <Link href="/admin/evaluation" className="flex items-center gap-2.5 rounded-xl border border-warning/40 bg-surface px-4 py-3 text-sm font-medium text-warning hover:bg-warning-bg transition-colors">
              <BarChart3 className="h-4 w-4" />
              Evaluation
            </Link>
            <Link href="/admin/users" className="flex items-center gap-2.5 rounded-xl border border-warning/40 bg-surface px-4 py-3 text-sm font-medium text-warning hover:bg-warning-bg transition-colors">
              <Users className="h-4 w-4" />
              Users
            </Link>
            <Link href="/admin/feedback" className="flex items-center gap-2.5 rounded-xl border border-warning/40 bg-surface px-4 py-3 text-sm font-medium text-warning hover:bg-warning-bg transition-colors">
              <MessageSquare className="h-4 w-4" />
              Feedback
            </Link>
          </div>
        </section>
      )}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
        <article className="rounded-2xl border border-line bg-surface p-6 text-sm text-muted shadow-sm">
          <h2 className="text-xl font-semibold text-foreground">Profile photo</h2>
          <p className="mt-1 text-xs text-muted">
            Upload a square PNG or JPG. Stored locally in your user folder.
          </p>
          <div className="mt-4 flex flex-col items-center gap-3">
            <div className="h-32 w-32 overflow-hidden rounded-full border-2 border-dashed border-line">
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
                <div className="flex h-full w-full items-center justify-center text-xs text-muted">No photo</div>
              )}
            </div>
            <form className="w-full space-y-3" onSubmit={handlePictureSubmit}>
              <input
                type="file"
                accept="image/png,image/jpeg"
                onChange={(event) => setPictureFile(event.target.files?.[0] || null)}
                className="w-full text-xs text-muted"
              />
              {pictureStatus.error && <p className="text-xs text-danger">{pictureStatus.error}</p>}
              {pictureStatus.success && <p className="text-xs text-success">{pictureStatus.success}</p>}
              <button
                type="submit"
                className="w-full btn-secondary text-xs disabled:opacity-60 disabled:hover:scale-100"
                disabled={pictureStatus.loading}
              >
                {pictureStatus.loading ? (
                  <><span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-foreground border-t-transparent"></span> Uploading…</>
                ) : (
                  "Save photo"
                )}
              </button>
            </form>
          </div>
        </article>

        <article className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-xl font-semibold text-foreground">Account overview</h2>
              <p className="truncate text-sm text-muted">Signed in as {profile.user.username}</p>
            </div>
            <span className={`shrink-0 whitespace-nowrap rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.15em] ${profile.user.role === "Admin" ? "bg-warning-bg text-warning" : "bg-primary-bg text-primary"}`}>
              {profile.user.role}
            </span>
          </div>
          <dl className="mt-4 space-y-2 text-sm text-muted">
            <div className="flex justify-between gap-4">
              <dt className="shrink-0 text-muted">Email</dt>
              <dd className="min-w-0 truncate text-right font-medium text-foreground">{profile.user.email || "Not set"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="shrink-0 text-muted">Last login</dt>
              <dd className="min-w-0 truncate text-right font-medium text-foreground">{formattedLastLogin}</dd>
            </div>
          </dl>
          <div className="mt-6 flex items-center gap-4">
            <Link href="/" className="inline-flex items-center text-sm font-medium text-primary hover:underline">
              Back to home →
            </Link>
            {profile.user.role === "Admin" && (
              <Link href="/admin" className="inline-flex items-center gap-1.5 text-sm font-medium text-warning hover:underline">
                <Shield className="h-3.5 w-3.5" />
                Admin Panel →
              </Link>
            )}
          </div>
        </article>

        <article className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-foreground">Recent highlights</h2>
          <div className="mt-4 grid gap-3 text-sm text-muted">
            <div className="rounded-xl border border-line bg-surface-2 p-3">
              <p className="text-xs uppercase tracking-[0.3em] text-muted">Quizzes</p>
              <p className="text-2xl font-semibold text-foreground">{profile.recent_quizzes.length}</p>
              <p className="text-xs text-muted">Stored results in the last uploads folder.</p>
            </div>
            <div className="rounded-xl border border-line bg-surface-2 p-3">
              <p className="text-xs uppercase tracking-[0.3em] text-muted">Appointments</p>
              <p className="text-2xl font-semibold text-foreground">{profile.recent_appointments.length}</p>
              <p className="text-xs text-muted">Showing the five most recent requests.</p>
            </div>
          </div>
        </article>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">Full quiz history</h2>
            <span className="text-xs text-muted">{quizHistory.length} total</span>
          </div>
          <div className="mt-4 space-y-3 max-h-[360px] overflow-auto pr-1">
            {quizHistory.length === 0 && <p className="text-sm text-muted">No quiz attempts recorded.</p>}
            {quizHistory.map((quiz) => (
              <div key={quiz.id} className="rounded-xl border border-line bg-surface-2 p-3 text-sm">
                <p className="font-semibold text-foreground">
                  {quiz.score}/{quiz.total_questions} · {quiz.percentage.toFixed(1)}%
                </p>
                <p className="text-xs text-muted">{formatDate(quiz.created_at)}</p>
                {quiz.metadata &&
                  "selected_folders" in quiz.metadata &&
                  Array.isArray(quiz.metadata.selected_folders) &&
                  quiz.metadata.selected_folders.every((item: unknown) => typeof item === "string") && (
                  <p className="text-xs text-muted">
                    Folders: {(quiz.metadata.selected_folders as string[]).join(", ")}
                  </p>
                )}
              </div>
            ))}
          </div>
        </article>

        <article className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">All appointment requests</h2>
            <span className="text-xs text-muted">{appointmentHistory.length} total</span>
          </div>
          <div className="mt-4 space-y-3 max-h-[360px] overflow-auto pr-1">
            {appointmentHistory.length === 0 && <p className="text-sm text-muted">No appointments submitted.</p>}
            {appointmentHistory.map((appt) => (
              <div key={appt.id} className="rounded-xl border border-line bg-surface-2 p-3 text-sm">
                <p className="font-semibold text-foreground">
                  {appt.preferred_date} · {appt.preferred_time}
                </p>
                <p className="text-xs text-muted">{appt.appointment_with}</p>
                <p className="text-xs text-muted">Reason: {appt.primary_reason}</p>
                <p className="text-xs text-muted">Status: {appt.status}</p>
                {appt.additional_details && <p className="text-xs text-muted">{appt.additional_details}</p>}
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">Feedback submissions</h2>
          <Link href="/feedback" className="text-sm font-medium text-primary hover:underline">
            Share more feedback
          </Link>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-muted">General feedback</p>
            <div className="mt-2 space-y-3 max-h-[260px] overflow-auto pr-1">
              {feedbackHistory.feedback.length === 0 && <p className="text-sm text-muted">No submissions yet.</p>}
              {feedbackHistory.feedback.map((entry, index) => (
                <div key={`fb-${index}`} className="rounded-xl border border-line bg-surface-2 p-3 text-sm">
                  <p className="font-semibold text-foreground">{entry.category}</p>
                  <p className="text-xs text-muted">{formatDate(entry.created_at)}</p>
                  <p className="text-xs text-muted">{entry.message}</p>
                </div>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-muted">Bug reports</p>
            <div className="mt-2 space-y-3 max-h-[260px] overflow-auto pr-1">
              {feedbackHistory.bugs.length === 0 && <p className="text-sm text-muted">No bugs reported.</p>}
              {feedbackHistory.bugs.map((entry, index) => (
                <div key={`bug-${index}`} className="rounded-xl border border-line bg-surface-2 p-3 text-sm">
                  <p className="font-semibold text-foreground">{entry.feature}</p>
                  <p className="text-xs text-muted">
                    Severity: {entry.severity} · {formatDate(entry.created_at)}
                  </p>
                  <p className="text-xs text-muted">{entry.description}</p>
                  {entry.steps && <p className="text-xs text-muted">Steps: {entry.steps}</p>}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-foreground">Contact details & theme</h2>
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
            {profileStatus.error && <p className="text-sm text-danger">{profileStatus.error}</p>}
            {profileStatus.message && <p className="text-sm text-success">{profileStatus.message}</p>}
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

        <article className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-foreground">Personal notes</h2>
          <form className="mt-4 space-y-3" onSubmit={handleNotesSave}>
            <textarea
              className="input min-h-[200px]"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Jot down reminders or references—stored locally under your user folder."
            />
            {notesStatus.error && <p className="text-sm text-danger">{notesStatus.error}</p>}
            {notesStatus.message && <p className="text-sm text-success">{notesStatus.message}</p>}
            <button
              type="submit"
              className="btn-secondary disabled:opacity-60 disabled:hover:scale-100"
              disabled={notesStatus.saving}
            >
              {notesStatus.saving ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-foreground border-t-transparent"></span> Saving…</>
              ) : (
                "Save notes"
              )}
            </button>
          </form>
        </article>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-foreground">Recent quiz history</h2>
            <Link href="/quiz" className="text-sm font-medium text-primary hover:underline">
              Open quiz builder
            </Link>
          </div>
          <div className="mt-4 space-y-3">
            {profile.recent_quizzes.length === 0 && (
              <p className="text-sm text-muted">No quiz submissions yet.</p>
            )}
            {profile.recent_quizzes.map((quiz) => {
              const selectedFolders =
                quiz.metadata && Array.isArray(quiz.metadata["selected_folders"])
                  ? (quiz.metadata["selected_folders"] as string[])
                  : null;
              return (
                <div key={quiz.id} className="rounded-xl border border-line bg-surface-2 p-4 text-sm text-foreground">
                  <p className="font-semibold text-foreground">
                    {quiz.score}/{quiz.total_questions} · {quiz.percentage.toFixed(1)}%
                  </p>
                  <p className="text-xs text-muted">{formatDate(quiz.created_at)}</p>
                  {selectedFolders && selectedFolders.length > 0 && (
                    <p className="mt-1 text-xs text-muted">Folders: {selectedFolders.join(", ")}</p>
                  )}
                </div>
              );
            })}
          </div>
        </article>

        <article className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-foreground">Recent appointment requests</h2>
            <Link href="/appointments" className="text-sm font-medium text-primary hover:underline">
              Schedule time
            </Link>
          </div>
          <div className="mt-4 space-y-3">
            {profile.recent_appointments.length === 0 && (
              <p className="text-sm text-muted">No appointments logged yet.</p>
            )}
            {profile.recent_appointments.map((appt) => (
              <div key={appt.id} className="rounded-xl border border-line bg-surface-2 p-4 text-sm text-foreground">
                <p className="font-semibold text-foreground">{appt.appointment_with}</p>
                <p className="text-xs text-muted">
                  {appt.preferred_date} at {appt.preferred_time} · {appt.primary_reason}
                </p>
                {appt.additional_details && <p className="mt-1 text-xs text-muted">{appt.additional_details}</p>}
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-line bg-surface p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-foreground">Password & security</h2>
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
            {passwordStatus.error && <p className="text-sm text-danger">{passwordStatus.error}</p>}
            {passwordStatus.message && <p className="text-sm text-success">{passwordStatus.message}</p>}
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

        <article className="rounded-2xl border border-danger/30 bg-danger-bg p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-danger">Danger zone</h2>
          <p className="mt-2 text-sm text-danger">
            Deleting your account removes stored chat logs, quizzes, and research files from the local filesystem.
          </p>
          <form className="mt-4 space-y-4" onSubmit={handleDeleteAccount}>
            <input
              className="input w-full border-danger/30"
              placeholder="Type your username to confirm"
              value={deleteConfirm}
              onChange={(event) => setDeleteConfirm(event.target.value)}
            />
            {deleteStatus.error && <p className="text-sm text-danger">{deleteStatus.error}</p>}
            <button
              type="submit"
              className="w-full rounded-full bg-danger-solid px-6 py-3 text-sm font-semibold text-white shadow-md transition hover:scale-105 hover:shadow-xl disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100"
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
