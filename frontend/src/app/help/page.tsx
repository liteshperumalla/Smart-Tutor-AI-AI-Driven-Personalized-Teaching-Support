import Link from "next/link";
import {
  BookOpen,
  Brain,
  CalendarDays,
  ChevronDown,
  CircleHelp,
  Code2,
  FolderOpen,
  LifeBuoy,
  MessageSquare,
  type LucideIcon,
} from "lucide-react";
import { PageShell } from "@/components/page-shell";
import { PageHero } from "@/components/page-hero";
import { WINDOW_LABEL } from "@/lib/maintenance";

const guides: { icon: LucideIcon; title: string; href: string; body: string }[] = [
  {
    icon: MessageSquare,
    title: "Chat",
    href: "/chat",
    body: "Pick a mode: Ask for a direct answer with sources, Learn for a guided explanation, Practice for questions, Review to go over a topic. Answers cite your course materials.",
  },
  {
    icon: Brain,
    title: "Quiz",
    href: "/quiz",
    body: "Choose a course and the materials to practise from, set the number of questions, and get instant scoring with explanations. Recent scores appear beside the form.",
  },
  {
    icon: FolderOpen,
    title: "Resources",
    href: "/resources",
    body: "Slides, readings and code demos the tutor can cite. Anything listed here is searchable from the chat.",
  },
  {
    icon: CalendarDays,
    title: "Appointments",
    href: "/appointments",
    body: "Request time with the professor or a TA. Pick a preferred date and time; the request and its status show in your history.",
  },
  {
    icon: Code2,
    title: "Code sandbox",
    href: "/code",
    body: "Write and run Python, JavaScript or Java, and ask the coding assistant to generate, explain or debug code.",
  },
];

const faqs: { q: string; a: React.ReactNode }[] = [
  {
    q: "Why does the tutor say it is offline?",
    a: <>The AI tutor runs during service hours, {WINDOW_LABEL}. Outside those hours the site stays up but chat, quizzes and the code sandbox are unavailable.</>,
  },
  {
    q: "Where do the tutor's answers come from?",
    a: <>From the materials indexed for your active course, listed on the <Link href="/resources" className="font-medium text-emerald-700 underline-offset-2 hover:underline dark:text-emerald-400">Resources</Link> page. Answers show which sources they used so you can check them.</>,
  },
  {
    q: "Can I choose which AI model answers?",
    a: <>Yes. Use the model menu in the chat composer. If a model is unavailable, another one answers and the reply is labelled with the model that actually responded.</>,
  },
  {
    q: "How do I switch courses?",
    a: <>If you are enrolled in more than one course, pick it from the course selector on the Chat or Quiz page. Chats and quizzes use the materials of the course you select.</>,
  },
  {
    q: "How do I change light or dark mode?",
    a: <>Use the sun/moon button at the bottom of the sidebar. Your choice is remembered on this device.</>,
  },
  {
    q: "I forgot my password.",
    a: <>Use <Link href="/password-reset/request" className="font-medium text-emerald-700 underline-offset-2 hover:underline dark:text-emerald-400">Reset password</Link> on the sign-in page and follow the link in the email.</>,
  },
];

export default function HelpPage() {
  return (
    <PageShell className="max-w-5xl" contentClassName="gap-10" noCard>
      <PageHero
        icon={CircleHelp}
        eyebrow="Help"
        title="How can we"
        accent="help?"
        subtitle="Guides for each part of Smart AI Tutor, answers to common questions, and how to reach us."
      />

      <section className="animate-fade-in-up">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500 dark:text-zinc-400">
          <BookOpen className="h-4 w-4" />
          Feature guides
        </h2>
        <div className="mt-5 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {guides.map(({ icon: Icon, title, href, body }) => (
            <Link
              key={title}
              href={href}
              className="group rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <h3 className="font-display mt-5 text-lg font-bold text-zinc-900 dark:text-white">
                {title}
                <span className="ml-1 inline-block transition-transform group-hover:translate-x-1" aria-hidden="true">→</span>
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{body}</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="animate-fade-in-up stagger-1">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500 dark:text-zinc-400">
          <CircleHelp className="h-4 w-4" />
          Frequently asked questions
        </h2>
        <div className="mt-5 divide-y divide-zinc-200 overflow-hidden rounded-2xl border border-zinc-200 bg-white dark:divide-zinc-800 dark:border-zinc-800 dark:bg-zinc-900">
          {faqs.map(({ q, a }) => (
            <details key={q} className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-6 py-4 text-sm font-semibold text-zinc-900 hover:bg-zinc-50 dark:text-white dark:hover:bg-zinc-800/60 [&::-webkit-details-marker]:hidden">
                {q}
                <ChevronDown className="h-4 w-4 shrink-0 text-zinc-500 transition-transform group-open:rotate-180" aria-hidden="true" />
              </summary>
              <p className="px-6 pb-5 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{a}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="animate-fade-in-up stagger-2 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
              <LifeBuoy className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <h2 className="font-display text-lg font-bold text-zinc-900 dark:text-white">Still stuck?</h2>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                Send feedback or report a bug and it goes straight to the course team.
              </p>
            </div>
          </div>
          <Link
            href="/feedback"
            className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-emerald-600 to-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
          >
            Contact us →
          </Link>
        </div>
      </section>
    </PageShell>
  );
}
