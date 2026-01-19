import Link from "next/link";
import { fetchHomeOverview, type HomeOverview } from "@/lib/api";
import { HomeHeroActions } from "@/components/home-hero-actions";
import { PageShell } from "@/components/page-shell";
import { Bell, GraduationCap, Upload, FolderOpen, ExternalLink } from "lucide-react";

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
    { title: "Research mode", description: "Upload and search your own sources.", href: "/research", icon: "research" },
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
    <PageShell contentClassName="gap-10 pb-6">
        <header className="relative overflow-hidden rounded-3xl gradient-mesh p-12 animate-fade-in-down">
          {/* Decorative blobs */}
          <div className="absolute top-0 right-0 h-64 w-64 bg-indigo-400/20 rounded-full blur-3xl animate-float"></div>
          <div className="absolute bottom-0 left-0 h-48 w-48 bg-amber-400/20 rounded-full blur-3xl" style={{animationDelay: '1s'}}></div>

          <div className="relative z-10">
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white/80 px-4 py-2 text-sm font-medium text-indigo-700 backdrop-blur dark:border-indigo-800 dark:bg-zinc-900/80 dark:text-indigo-300">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75"></span>
                <span className="relative inline-flex h-2 w-2 rounded-full bg-indigo-500"></span>
              </span>
              Smart AI Tutor · INFO 5731
            </div>

            <h1 className="font-display mt-6 text-6xl font-bold text-zinc-900 leading-tight dark:text-white">
              Advanced Computational<br />Methods
            </h1>

            <p className="mt-4 text-lg text-zinc-600 max-w-2xl dark:text-zinc-400">
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
                  className={`group relative overflow-hidden rounded-3xl p-8 transition-all hover:-translate-y-1 hover:shadow-xl animate-fade-in-up ${
                    i < 2
                      ? 'card-gradient shadow-xl'
                      : 'border-2 border-dashed border-zinc-200 bg-white hover:border-indigo-300 hover:bg-indigo-50/50 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:border-indigo-600 dark:hover:bg-indigo-900/20'
                  }`}
                  style={{animationDelay: `${i * 0.05}s`}}>

                  {/* Visual indicator */}
                  <div className={`mb-4 flex h-12 w-12 items-center justify-center rounded-xl ${
                    i < 2 ? 'bg-white/20' : 'bg-indigo-100 dark:bg-indigo-900/30'
                  }`}>
                    {action.icon === 'chat' && (
                      <svg className={`h-6 w-6 ${i < 2 ? 'text-white' : 'text-indigo-600 dark:text-indigo-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                      </svg>
                    )}
                    {action.icon === 'quiz' && (
                      <svg className={`h-6 w-6 ${i < 2 ? 'text-white' : 'text-indigo-600 dark:text-indigo-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                      </svg>
                    )}
                    {action.icon === 'research' && (
                      <svg className={`h-6 w-6 ${i < 2 ? 'text-white' : 'text-indigo-600 dark:text-indigo-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                    )}
                    {action.icon === 'code' && (
                      <svg className={`h-6 w-6 ${i < 2 ? 'text-white' : 'text-indigo-600 dark:text-indigo-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                      </svg>
                    )}
                    {action.icon === 'calendar' && (
                      <svg className={`h-6 w-6 ${i < 2 ? 'text-white' : 'text-indigo-600 dark:text-indigo-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    )}
                    {action.icon === 'chart' && (
                      <svg className={`h-6 w-6 ${i < 2 ? 'text-white' : 'text-indigo-600 dark:text-indigo-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                      </svg>
                    )}
                  </div>

                  <h3 className={`font-display text-xl font-bold ${i < 2 ? 'text-white' : 'text-zinc-900 dark:text-white'}`}>
                    {action.title}
                  </h3>

                  <p className={`mt-2 text-sm ${i < 2 ? 'text-white/80' : 'text-zinc-600 dark:text-zinc-400'}`}>
                    {action.description}
                  </p>

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

            <article className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-400">Knowledge Base</p>
                <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
                  stats.knowledge_base?.ready
                    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                    : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                }`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${stats.knowledge_base?.ready ? 'bg-emerald-500' : 'bg-amber-500'} ${stats.knowledge_base?.ready ? 'animate-pulse' : ''}`}></span>
                  {stats.knowledge_base?.ready ? 'Active' : 'Loading'}
                </span>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Documents</span>
                  <span className="font-medium text-zinc-900 dark:text-white">{stats.knowledge_base?.document_count?.toLocaleString() ?? 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Sources</span>
                  <span className="font-medium text-zinc-900 dark:text-white">{stats.knowledge_base?.source_count ?? 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Vector chunks</span>
                  <span className="font-medium text-zinc-900 dark:text-white">{stats.vector_store_ready ? '12,752' : '0'}</span>
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-zinc-100 dark:border-zinc-800">
                <Link href="/research" className="text-sm text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300 font-medium flex items-center gap-1">
                  <Upload className="h-4 w-4" />
                  Upload sources <span className="transition-transform group-hover:translate-x-1">→</span>
                </Link>
              </div>
            </article>

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
