import Link from "next/link";
import { fetchHomeOverview, type HomeOverview } from "@/lib/api";
import { HomeHeroActions } from "@/components/home-hero-actions";
import { PageShell } from "@/components/page-shell";

const DEFAULT_OVERVIEW: HomeOverview = {
  announcements: [
    {
      id: "welcome",
      title: "Welcome",
      body: "Start the FastAPI backend to see live system metrics.",
      accent: "#3b82f6",
    },
  ],
  professor: {
    name: "Smart AI Tutor",
    links: [],
  },
  course_topics: [],
  quick_actions: [
    { title: "Chat", description: "Ask the tutor questions.", href: "/chat" },
    { title: "Generate a quiz", description: "Create course-ready quizzes.", href: "/quiz" },
    { title: "Research mode", description: "Upload and search sources.", href: "/research" },
  ],
  system_status: {
    knowledge_base: {
      ready: false,
      document_count: 0,
      source_count: 0,
      sample_sources: [],
      last_updated: null,
      last_updated_display: null,
      path: "./persisted_index/docstore.json",
    },
    vector_store_ready: false,
    chroma_ready: false,
    evaluation_ready: false,
    evaluation_cases: 0,
    evaluation: {
      ready: false,
      cases: 0,
      path: "evaluation_dataset.json",
      last_updated: null,
      last_updated_display: null,
    },
    ollama: { ready: false, models: [], error: "Backend offline" },
    issues: ["Home overview API unavailable. Start the FastAPI backend and try again."],
  },
};

export default async function Home() {
  let overview: HomeOverview = DEFAULT_OVERVIEW;
  try {
    overview = await fetchHomeOverview();
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Home overview request failed";
    if (process.env.NODE_ENV !== "production") {
      console.warn("Home overview fallback:", message);
    }
    overview = DEFAULT_OVERVIEW;
  }

  const stats = overview.system_status;
  const announcements = overview?.announcements ?? [];
  const quickActions = overview?.quick_actions ?? [];
  const professor = overview?.professor;
  const issues = stats?.issues ?? [];

  return (
    <PageShell contentClassName="gap-10 pb-6">
        <header className="space-y-3 text-center sm:text-left">
          <p className="text-xs uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-400">
            Smart AI Tutor · INFO 5731
          </p>
          <h1 className="text-4xl font-semibold text-zinc-950 dark:text-white">Advanced Computational Methods</h1>
          <HomeHeroActions />
        </header>

        {issues.length > 0 && (
          <section className="rounded-3xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
            <p className="font-semibold">Action needed</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </section>
        )}

        {quickActions.length > 0 && (
          <section className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <p className="text-xs uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-400">Quick actions</p>
            <div className="mt-4 grid gap-4 md:grid-cols-3">
              {quickActions.map((action) => (
                <Link key={action.title} href={action.href} className="rounded-2xl border border-zinc-100 bg-zinc-50 p-5 transition hover:-translate-y-0.5 dark:border-zinc-800 dark:bg-zinc-800/50">
                  <p className="pt-2 text-lg font-semibold text-zinc-900 dark:text-white">{action.title}</p>
                  <p className="text-sm text-zinc-600 dark:text-zinc-400">{action.description}</p>
                </Link>
              ))}
            </div>
          </section>
        )}

        <section className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">Latest announcements</h2>
              <span className="text-xs text-zinc-500 dark:text-zinc-400">Course-wide updates</span>
            </div>
            <div className="mt-4 space-y-4">
              {(announcements.length ? announcements : [{ id: "welcome", title: "Welcome", body: "Check back soon.", accent: "#3b82f6" }]).map((announcement) => (
                <div
                  key={announcement.id}
                  className="rounded-2xl border-l-4 bg-zinc-50 p-4 text-sm text-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-300"
                  style={{ borderColor: announcement.accent }}
                >
                  <p className="text-base font-semibold text-zinc-900 dark:text-white">{announcement.title}</p>
                  <p className="pt-1 text-sm">{announcement.body}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-6">
            <article className="rounded-3xl border border-zinc-200 bg-white p-6 text-center shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <p className="text-xs uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-400">Professor</p>
              <div className="mx-auto mt-4 flex h-16 w-16 items-center justify-center rounded-full bg-zinc-100 text-2xl font-semibold text-zinc-900 dark:bg-zinc-800 dark:text-white">
                {(professor?.name || "Faculty").charAt(0)}
              </div>
              <p className="mt-3 text-lg font-semibold text-zinc-900 dark:text-white">{professor?.name ?? "Faculty"}</p>
              {professor?.email && <p className="text-xs text-zinc-500 dark:text-zinc-400">{professor.email}</p>}
              <div className="mt-4 flex flex-wrap justify-center gap-2 text-sm">
                {professor?.links?.map((link) => (
                  <a key={link.url} href={link.url} target="_blank" className="rounded-full border border-zinc-200 px-3 py-1 text-zinc-700 dark:border-zinc-700 dark:text-zinc-300">
                    {link.label}
                  </a>
                ))}
              </div>
            </article>
            <article className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-400">Resources</p>
                  <p className="pt-2 text-sm text-zinc-600 dark:text-zinc-400">
                    Need lecture slides or Canvas links? Browse the curated resources hub.
                  </p>
                </div>
                <Link
                  href="/resources"
                  className="rounded-full border border-zinc-200 px-4 py-2 text-sm font-semibold text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
                >
                  Open resources
                </Link>
              </div>
            </article>
          </div>
        </section>

    </PageShell>
  );
}
