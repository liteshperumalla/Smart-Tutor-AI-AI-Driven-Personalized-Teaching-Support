"use client";

import { PageShell } from "@/components/page-shell";
import { PageHero } from "@/components/page-hero";
import {
  Info,
  LayoutGrid,
  Layers,
  User,
  MessageSquare,
  Brain,
  Sparkles,
  FolderOpen,
  CalendarDays,
  ShieldCheck,
  Github,
  Linkedin,
  Mail,
  type LucideIcon,
} from "lucide-react";

const keyFeatures: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: MessageSquare,
    title: "Interactive document chat",
    body: "Ask contextual questions about uploaded materials and get cited responses.",
  },
  {
    icon: Brain,
    title: "Custom quiz generation",
    body: "Create formative assessments sourced directly from class content.",
  },
  {
    icon: Sparkles,
    title: "Personalized tutoring",
    body: "Receive AI guidance that adapts to your progress and pace.",
  },
  {
    icon: FolderOpen,
    title: "Resource hub",
    body: "Browse course-scoped readings, slides, and notes across your enrolled courses.",
  },
  {
    icon: CalendarDays,
    title: "Appointment scheduling",
    body: "Book meetings with professors or TAs without leaving the tutor.",
  },
  {
    icon: ShieldCheck,
    title: "Grounded answers",
    body: "Every response cites a real chunk of indexed course material.",
  },
];

const techStack = [
  { label: "Frontend", value: "Next.js · React 19 · Tailwind v4" },
  { label: "Backend & AI", value: "FastAPI · Python · LlamaIndex" },
  { label: "LLM Runtime", value: "AWS Bedrock · Llama 3.1 70B" },
  { label: "File Processing", value: "PyMuPDF · python-pptx · docx" },
];

const developerLinks: { icon: LucideIcon; label: string; href: string }[] = [
  { icon: Github, label: "GitHub", href: "https://github.com/liteshperumalla" },
  { icon: Linkedin, label: "LinkedIn", href: "https://www.linkedin.com/in/perumalla-litesh/" },
  { icon: Mail, label: "Email", href: "mailto:liteshperumalla@my.unt.edu" },
];

function SectionLabel({ icon: Icon, children }: { icon: LucideIcon; children: string }) {
  return (
    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.3em] text-zinc-500 dark:text-zinc-400">
      <Icon className="h-4 w-4" />
      {children}
    </div>
  );
}

export default function AboutPage() {
  return (
    <PageShell className="max-w-5xl" contentClassName="gap-10" noCard>
      <PageHero
        icon={Info}
        eyebrow="About"
        title="Why Smart"
        accent="AI Tutor exists."
        subtitle="An RAG-grounded, multi-course tutor built so students get answers backed by their actual lectures and readings."
      />

      {/* Key features */}
      <section className="animate-fade-in-up">
        <SectionLabel icon={LayoutGrid}>Key Features</SectionLabel>
        <div className="mt-5 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {keyFeatures.map((feature, i) => {
            const Icon = feature.icon;
            return (
              <article
                key={feature.title}
                className="group rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
                style={{ animationDelay: `${i * 0.05}s` }}
              >
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="font-display mt-5 text-lg font-bold text-zinc-900 dark:text-white">
                  {feature.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
                  {feature.body}
                </p>
              </article>
            );
          })}
        </div>
      </section>

      {/* Technology stack */}
      <section className="animate-fade-in-up stagger-1">
        <SectionLabel icon={Layers}>Technology Stack</SectionLabel>
        <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {techStack.map((item) => (
            <div
              key={item.label}
              className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.25em] text-zinc-400 dark:text-zinc-500">
                {item.label}
              </p>
              <p className="mt-2 text-sm font-semibold text-zinc-900 dark:text-white">
                {item.value}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Developer */}
      <section className="animate-fade-in-up stagger-2 rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 sm:p-8">
        <SectionLabel icon={User}>Developer</SectionLabel>
        <div className="mt-6 flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <span className="flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 text-2xl font-bold text-white">
              L
            </span>
            <div>
              <p className="font-display text-xl font-bold text-zinc-900 dark:text-white">
                Litesh Perumalla
              </p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">UNT · Computer Science</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2.5">
            {developerLinks.map((link) => {
              const Icon = link.icon;
              return (
                <a
                  key={link.href}
                  href={link.href}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-full border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-700 transition hover:border-zinc-300 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:border-zinc-600 dark:hover:bg-zinc-800"
                >
                  <Icon className="h-4 w-4" />
                  {link.label}
                </a>
              );
            })}
          </div>
        </div>
      </section>
    </PageShell>
  );
}
