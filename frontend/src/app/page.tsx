import Link from "next/link";
import { fetchHomeOverview, type HomeOverview } from "@/lib/api";
import { HomeHeroActions } from "@/components/home-hero-actions";
import { PageShell } from "@/components/page-shell";
import { KnowledgeBaseWidget } from "@/components/knowledge-base-widget";
import { Bell, GraduationCap, FolderOpen, ExternalLink } from "lucide-react";

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
    { title: "Chat", description: "Ask the tutor questions about course material.", href: "/chat", icon: "chat" },
    { title: "Generate a quiz", description: "Create practice quizzes from course content.", href: "/quiz", icon: "quiz" },
    { title: "Code sandbox", description: "Write and execute code in multiple languages.", href: "/code", icon: "code" },
    { title: "Appointments", description: "Schedule time with the professor or TA.", href: "/appointments", icon: "calendar" },
    { title: "Evaluation", description: "Run RAG system evaluations and benchmarks.", href: "/evaluation", icon: "chart" },
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
    <PageShell contentClassName="gap-10 pb-6" noCard>
        <header className="relative overflow-hidden rounded-3xl p-6 sm:p-8 lg:p-12 animate-fade-in-down">
          {/* Decorative blobs */}
          <div className="absolute top-0 right-0 h-64 w-64 bg-indigo-400/20 rounded-full blur-3xl animate-float"></div>
          <div className="absolute bottom-0 left-0 h-48 w-48 bg-amber-400/20 rounded-full blur-3xl" style={{animationDelay: '1s'}}></div>

          <div className="relative z-10">
            <h1 className="font-display mt-4 text-3xl font-bold text-zinc-900 leading-tight dark:text-white sm:text-4xl lg:mt-6 lg:text-6xl">
              Advanced Computational<br className="hidden sm:block" /> Methods
            </h1>

            <p className="mt-3 text-base text-zinc-600 max-w-2xl dark:text-zinc-400 sm:mt-4 sm:text-lg">
              Spring 2025 · Master AI-powered learning with intelligent tutoring, dynamic quizzes, and research tools
            </p>

            <div className="mt-8 flex flex-wrap gap-4">
              <HomeHeroActions />
            </div>
          </div>
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
          <section className="animate-fade-in-up">
            <h2 className="font-display text-2xl font-bold mb-6">Quick Actions</h2>
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {quickActions.map((action, i) => (
                <Link
                  key={action.title}
                  href={action.href}
                  className="group relative overflow-hidden rounded-3xl p-5 sm:p-8 transition-all hover:-translate-y-1 hover:shadow-xl animate-fade-in-up bg-white hover:bg-zinc-100 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                  style={{animationDelay: `${i * 0.05}s`}}>
                  
                  <div className="mb-4">
                    <h3 className="font-display text-xl font-bold text-zinc-900 dark:text-white">
                      {action.title}
                    </h3>
                    <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
                      {action.description}
                    </p>
                  </div>

                  <div className={`mt-4 inline-flex items-center gap-2 font-medium text-sm ${i < 2 ? 'text-white' : 'text-indigo-600 dark:text-indigo-400'}`}>
                    Get started <span className="transition-transform group-hover:translate-x-1">→</span>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}

        <section className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-zinc-900 dark:text-white flex items-center gap-2">
                <Bell className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />
                Latest announcements
              </h2>
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
              <p className="text-xs uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-400 flex items-center justify-center gap-2">
                <GraduationCap className="h-4 w-4" />
                Professor
              </p>
              <div className="mx-auto mt-4 flex h-16 w-16 items-center justify-center rounded-full bg-zinc-100 text-2xl font-semibold text-zinc-900 dark:bg-zinc-800 dark:text-white">
                {(professor?.name || "Faculty").charAt(0)}
              </div>
              <p className="mt-3 text-lg font-semibold text-zinc-900 dark:text-white">{professor?.name ?? "Faculty"}</p>
              {professor?.email && <p className="text-xs text-zinc-500 dark:text-zinc-400">{professor.email}</p>}
              <div className="mt-4 flex flex-wrap justify-center gap-2 text-sm">
                {professor?.links?.map((link) => (
                  <a key={link.url} href={link.url} target="_blank" rel="noopener noreferrer" className="rounded-full border border-zinc-200 px-3 py-1 text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800 transition-colors">
                    {link.label}
                  </a>
                ))}
              </div>
            </article>

            <KnowledgeBaseWidget
              knowledge_base={stats.knowledge_base}
              vector_store_ready={stats.vector_store_ready}
            />

            <article className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-400 flex items-center gap-2">
                    <FolderOpen className="h-4 w-4" />
                    Resources
                  </p>
                  <p className="pt-2 text-sm text-zinc-600 dark:text-zinc-400">
                    Lecture slides, Canvas links, and curated learning materials.
                  </p>
                </div>
                <Link
                  href="/resources"
                  className="rounded-full border border-zinc-200 px-4 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800 transition-colors flex items-center gap-1"
                >
                  Browse <ExternalLink className="h-3 w-3" />
                </Link>
              </div>
            </article>
          </div>
        </section>

    </PageShell>
  );
}
