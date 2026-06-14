import Link from "next/link";
import { fetchHomeOverview, type HomeOverview } from "@/lib/api";
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
  const quickActions = (overview?.quick_actions ?? []).filter(
    (action) => action.href !== "/evaluation" && action.href !== "/admin/evaluation"
  );
  const professor = overview?.professor;
  return (
    <PageShell contentClassName="gap-10 pb-6" noCard>
        <header className="relative overflow-hidden rounded-3xl border border-zinc-200 p-6 sm:p-8 lg:p-10 animate-fade-in-down dark:border-zinc-800 bg-[linear-gradient(160deg,#ecfdf5_0%,#ffffff_55%,#eef2ff_100%)] dark:bg-[linear-gradient(160deg,#04201d_0%,#0f172a_55%,#1a193f_100%)]">
          {/* Dotted texture */}
          <div
            className="pointer-events-none absolute inset-0 opacity-40 dark:opacity-20"
            style={{ backgroundImage: "radial-gradient(rgba(15,23,42,0.06) 1px, transparent 1px)", backgroundSize: "22px 22px" }}
          />
          {/* Decorative blobs */}
          <div className="pointer-events-none absolute -top-20 -right-16 h-60 w-60 rounded-full blur-3xl animate-float" style={{ background: "rgba(16,185,129,0.18)" }}></div>
          <div className="pointer-events-none absolute -bottom-20 -left-10 h-52 w-52 rounded-full blur-3xl" style={{ background: "rgba(99,102,241,0.16)", animationDelay: "1s" }}></div>

          <div className="relative z-10">
            <h1 className="font-display text-4xl font-bold leading-[1.05] tracking-tight text-zinc-900 dark:text-white sm:text-5xl lg:text-6xl">
              Advanced Computational{" "}
              <span style={{ backgroundImage: "linear-gradient(90deg, #059669, #4f46e5)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
                Methods
              </span>
            </h1>
            <p className="mt-3 max-w-2xl text-base leading-relaxed text-zinc-600 dark:text-zinc-300 sm:text-lg">
              An AI tutor that cites every answer in your INFO 5731 corpus. Ask, quiz, and study — without the hallucinations.
            </p>
          </div>
        </header>

        {quickActions.length > 0 && (
          <section className="animate-fade-in-up">
            <h2 className="font-display text-2xl font-bold mb-6">Quick Actions</h2>
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {quickActions.map((action, i) => {
                const featured = action.href === "/code" || action.href === "/chat";
                return (
                  <Link
                    key={action.title}
                    href={action.href}
                    className={`group relative overflow-hidden rounded-3xl p-5 sm:p-8 transition-all hover:-translate-y-1 hover:shadow-xl animate-fade-in-up ${
                      featured
                        ? "card-gradient border-0"
                        : "border-2 border-zinc-200 bg-white hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                    }`}
                    style={{ animationDelay: `${i * 0.05}s` }}>

                    <div className="mb-4">
                      <h3 className={`font-display text-xl font-bold ${featured ? "text-white" : "text-zinc-900 dark:text-white"}`}>
                        {action.title}
                      </h3>
                      <p className={`mt-2 text-sm ${featured ? "text-white/85" : "text-zinc-600 dark:text-zinc-400"}`}>
                        {action.description}
                      </p>
                    </div>

                    <div className={`mt-4 inline-flex items-center gap-2 font-medium text-sm ${featured ? "text-white" : "text-indigo-600 dark:text-indigo-400"}`}>
                      Get started <span className="transition-transform group-hover:translate-x-1">→</span>
                    </div>
                  </Link>
                );
              })}
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
