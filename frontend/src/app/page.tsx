import Link from "next/link";
import { fetchHomeOverview, type HomeOverview } from "@/lib/api";
import { PageShell } from "@/components/page-shell";
import { KnowledgeBaseWidget } from "@/components/knowledge-base-widget";
import { Bell, GraduationCap, FolderOpen } from "lucide-react";

const DEFAULT_OVERVIEW: HomeOverview = {
  announcements: [
    {
      id: "welcome",
      title: "Welcome",
      body: "Start the FastAPI backend to see live system metrics.",
      accent: "var(--color-primary)",
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
        <header className="gradient-mesh relative overflow-hidden rounded-2xl border border-line bg-surface p-6 shadow-sm animate-fade-in-up sm:p-8 lg:p-10">
          {/* Dotted texture */}
          <div
            className="pointer-events-none absolute inset-0 opacity-40 dark:opacity-20"
            style={{ backgroundImage: "radial-gradient(rgba(15,23,42,0.06) 1px, transparent 1px)", backgroundSize: "22px 22px" }}
          />
          {/* Decorative blobs */}
          <div className="pointer-events-none absolute -top-20 -right-16 h-60 w-60 rounded-full blur-3xl animate-float" style={{ background: "var(--color-success-bg)" }}></div>
          <div className="pointer-events-none absolute -bottom-20 -left-10 h-52 w-52 rounded-full blur-3xl" style={{ background: "var(--color-primary-bg)", animationDelay: "1s" }}></div>

          <div className="relative z-10">
            <h1 className="font-display text-4xl font-bold leading-[1.05] tracking-tight text-foreground sm:text-5xl lg:text-6xl">
              Smart AI{" "}
              <span className="text-gradient-primary">
                Tutor
              </span>
            </h1>
            <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted sm:text-lg">
              Your multi-course learning platform for grounded answers, targeted practice, and measurable mastery.
            </p>
          </div>
        </header>

        {quickActions.length > 0 && (
          <section className="animate-fade-in-up">
            <h2 className="font-display text-2xl font-bold mb-6">Quick Actions</h2>
            {/* Four cards fill one row of four; other counts keep the three-column layout. */}
            <div className={`grid gap-6 md:grid-cols-2 ${quickActions.length % 4 === 0 ? "xl:grid-cols-4" : "lg:grid-cols-3"}`}>
              {quickActions.map((action, i) => {
                const featured =
                  action.href === "/code" ||
                  action.href === "/chat" ||
                  action.href === "/quiz" ||
                  action.href === "/appointments";
                return (
                  <Link
                    key={action.title}
                    href={action.href}
                    className={`group relative overflow-hidden rounded-3xl p-5 sm:p-8 transition-all hover:-translate-y-1 hover:shadow-xl animate-fade-in-up ${
                      featured
                        ? "card-gradient border-0"
                        : "border-2 border-line bg-surface hover:bg-surface-2"
                    }`}
                    style={{ animationDelay: `${i * 0.05}s` }}>

                    <div className="mb-4">
                      <h3 className={`font-display text-xl font-bold ${featured ? "text-white" : "text-foreground"}`}>
                        {action.title}
                      </h3>
                      <p className={`mt-2 text-sm ${featured ? "text-white/85" : "text-muted"}`}>
                        {action.description}
                      </p>
                    </div>

                    <div className={`mt-4 inline-flex items-center gap-2 font-medium text-sm ${featured ? "text-white" : "text-primary"}`}>
                      Get started <span className="transition-transform group-hover:translate-x-1">→</span>
                    </div>
                  </Link>
                );
              })}
            </div>
          </section>
        )}

        <section className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 rounded-3xl border border-line bg-surface p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-foreground flex items-center gap-2">
                <Bell className="h-5 w-5 text-muted" />
                Latest announcements
              </h2>
              <span className="text-xs text-muted">Course-wide updates</span>
            </div>
            <div className="mt-4 space-y-4">
              {(announcements.length ? announcements : [{ id: "welcome", title: "Welcome", body: "Check back soon.", accent: "var(--color-primary)" }]).map((announcement) => (
                <div
                  key={announcement.id}
                  className="rounded-2xl border-l-4 bg-surface-2 p-4 text-sm text-foreground"
                  style={{ borderColor: announcement.accent }}
                >
                  <p className="text-base font-semibold text-foreground">{announcement.title}</p>
                  <p className="pt-1 text-sm">{announcement.body}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-6">
            <article className="rounded-3xl border border-line bg-surface p-6 text-center shadow-sm">
              <p className="text-xs uppercase tracking-[0.35em] text-muted flex items-center justify-center gap-2">
                <GraduationCap className="h-4 w-4" />
                Professor
              </p>
              <div className="mx-auto mt-4 flex h-16 w-16 items-center justify-center rounded-full bg-surface-2 text-2xl font-semibold text-foreground">
                {(professor?.name || "Faculty").charAt(0)}
              </div>
              <p className="mt-3 text-lg font-semibold text-foreground">{professor?.name ?? "Faculty"}</p>
              {professor?.email && <p className="text-xs text-muted">{professor.email}</p>}
              <div className="mt-4 flex flex-wrap justify-center gap-2 text-sm">
                {professor?.links?.map((link) => (
                  <a key={link.url} href={link.url} target="_blank" rel="noopener noreferrer" className="rounded-full border border-line px-3 py-1 text-foreground hover:bg-surface-2 transition-colors">
                    {link.label}
                  </a>
                ))}
              </div>
            </article>

            <KnowledgeBaseWidget
              knowledge_base={stats.knowledge_base}
              vector_store_ready={stats.vector_store_ready}
            />

            <article className="rounded-3xl border border-line bg-surface p-6 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0 flex-1 basis-48">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted flex items-center gap-2">
                    <FolderOpen className="h-4 w-4" />
                    Resources
                  </p>
                  <p className="pt-2 text-sm text-muted">
                    Lecture slides, Canvas links, and curated learning materials.
                  </p>
                </div>
                <Link
                  href="/resources"
                  className="shrink-0 whitespace-nowrap rounded-full border border-line px-4 py-2 text-sm font-semibold text-foreground hover:bg-surface-2 transition-colors flex items-center gap-1"
                >
                  Browse <span aria-hidden="true">→</span>
                </Link>
              </div>
            </article>
          </div>
        </section>

    </PageShell>
  );
}
