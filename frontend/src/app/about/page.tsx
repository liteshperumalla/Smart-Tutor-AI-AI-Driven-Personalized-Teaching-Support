"use client";

import Link from "next/link";
import { PageShell } from "@/components/page-shell";

const keyFeatures = [
  {
    icon: "📄",
    title: "Interactive Document Chat",
    body: "Ask contextual questions about your uploaded materials and get cited responses.",
  },
  {
    icon: "🧠",
    title: "Custom Quiz Generation",
    body: "Create formative assessments sourced directly from class content.",
  },
  {
    icon: "💡",
    title: "Personalized Tutoring",
    body: "Receive AI guidance that adapts to your progress and pace.",
  },
  {
    icon: "🗂️",
    title: "Resource Hub",
    body: "Browse a curated library of INFO 5731 readings, slides, and notes.",
  },
  {
    icon: "📅",
    title: "Appointment Scheduling",
    body: "Book meetings with professors or TAs without leaving the tutor.",
  },
];

const techStack = [
  { label: "Frontend", value: "Streamlit & Next.js" },
  { label: "Backend & AI Core", value: "FastAPI, Python, LlamaIndex" },
  { label: "LLM Runtime", value: "Ollama (Llama 3.2)" },
  { label: "File Processing", value: "PyMuPDF, python-pptx, docx" },
];

const developerLinks = [
  { label: "Email", href: "mailto:liteshperumalla@my.unt.edu" },
  { label: "GitHub", href: "https://github.com/liteshperumalla" },
  { label: "LinkedIn", href: "https://www.linkedin.com/in/perumalla-litesh/" },
];

export default function AboutPage() {
  return (
    <PageShell className="max-w-5xl" contentClassName="gap-10">
        <header className="text-center">
          <p className="text-xs uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-400">
            ℹ️ About Smart AI Tutor
          </p>
          <h1 className="mt-4 text-4xl font-semibold text-zinc-950 dark:text-white">
            Empowering education with Artificial Intelligence
          </h1>
          <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
            Smart AI Tutor blends Retrieval-Augmented Generation and course-specific content to
            deliver personalized learning experiences for INFO 5731 students.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3 text-sm">
            <Link
              href="/"
              className="rounded-full border border-zinc-200 px-4 py-2 font-semibold text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
            >
              ← Back to home
            </Link>
            <span className="rounded-full border border-blue-200 px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-blue-600 dark:border-blue-800 dark:text-blue-400">
              UNT · Fall 2025
            </span>
          </div>
        </header>

        <section className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">🎯 Purpose</h2>
          <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
            Smart AI Tutor is designed to help students engage with course artifacts, test their
            understanding, and collaborate with AI in a trustworthy way. By grounding every answer in
            the indexed corpus, the tutor reduces hallucinations while surfacing the most relevant
            knowledge from INFO 5731.
          </p>
          <div className="mt-6 grid gap-3 md:grid-cols-2">
            {keyFeatures.map((feature) => (
              <article
                key={feature.title}
                className="rounded-2xl border border-zinc-100 bg-zinc-50/80 p-4 dark:border-zinc-800 dark:bg-zinc-800/50"
              >
                <p className="text-2xl">{feature.icon}</p>
                <h3 className="mt-2 text-base font-semibold text-zinc-900 dark:text-white">{feature.title}</h3>
                <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{feature.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">🛠️ Technology Stack</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {techStack.map((item) => (
              <div
                key={item.label}
                className="rounded-2xl border border-zinc-100 bg-zinc-50 p-4 text-sm text-zinc-700 dark:border-zinc-800 dark:bg-zinc-800/50 dark:text-zinc-300"
              >
                <p className="text-xs uppercase tracking-[0.3em] text-zinc-500 dark:text-zinc-400">{item.label}</p>
                <p className="pt-2 text-base font-medium text-zinc-900 dark:text-white">{item.value}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">👨‍💻 Developer</h2>
          <div className="mt-4 flex flex-col gap-6 md:flex-row">
            <div className="flex-shrink-0">
              <img
                src="https://github.com/liteshperumalla.png"
                alt="Litesh Perumalla"
                className="h-36 w-36 rounded-full border-4 border-blue-100 object-cover dark:border-blue-900"
              />
            </div>
            <div className="space-y-3 text-sm text-zinc-600 dark:text-zinc-400">
              <p className="text-lg font-semibold text-zinc-900 dark:text-white">Litesh Perumalla</p>
              <p>Master&apos;s Student in Data Science, University of North Texas</p>
              <p>
                Litesh focuses on AI-first experiences that unlock new ways of learning. His
                interests include Retrieval-Augmented Generation, human-in-the-loop AI, and
                full-stack experimentation with Python, FastAPI, and modern JavaScript frameworks.
              </p>
              <div className="flex flex-wrap gap-2">
                {developerLinks.map((link) => (
                  <a
                    key={link.href}
                    href={link.href}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-full border border-zinc-200 px-4 py-2 text-xs font-medium text-zinc-700 transition hover:border-zinc-300 dark:border-zinc-700 dark:text-zinc-300 dark:hover:border-zinc-600"
                  >
                    {link.label}
                  </a>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-3xl border border-blue-200 bg-blue-50/60 p-6 text-center dark:border-blue-800 dark:bg-blue-900/20">
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">📢 Contact & Contributions</h2>
          <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
            Feedback fuels the roadmap. Share feature ideas, report bugs, or contribute evaluations
            directly from the Feedback page in the tutor sidebar.
          </p>
          <div className="mt-4 text-xs uppercase tracking-[0.35em] text-blue-500 dark:text-blue-400">
            Thank you for supporting smart learning
          </div>
        </section>
    </PageShell>
  );
}
