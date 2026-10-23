"""Generate docs/architecture/system-architecture.svg (run from the repo root)."""

from pathlib import Path

from diagram_kit import PALETTE, Svg

OUT = Path(__file__).resolve().parents[1] / "system-architecture.svg"
W, H = 1400, 1010

svg = Svg(
    W, H, "Smart Tutor AI — system architecture",
    "Next.js frontend on Vercel proxies to a FastAPI backend on a scheduled AWS EC2 instance, which uses "
    "AWS Bedrock, S3, Postgres, Redis and Neo4j Aura, with Langfuse, PostHog and Prometheus/Grafana for "
    "observability and GitHub Actions for CI/CD.",
)
svg.text(W / 2, 46, "Smart Tutor AI — System Architecture", size=26, weight=800, fill="#0f172a", anchor="middle")
svg.text(W / 2, 70, "Vercel frontend · FastAPI on AWS EC2 · AWS Bedrock · managed data & observability · GitHub Actions",
         size=14, fill="#64748b", anchor="middle")


def group(x, y, w, h, label, sub, stroke="#cbd5e1", fill="#f8fafc"):
    svg.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>')
    svg.text(x + 16, y + 24, label, size=13, weight=700, fill="#0f172a")
    if sub:
        svg.text(x + 16, y + 42, sub, size=11.5, fill="#64748b")


# ── Edge (left column) ────────────────────────────────────────────────
group(30, 96, 300, 470, "Users & edge", "browser → Vercel")
svg.box(50, 152, 260, 78, "app", "Students & instructors", ["INFO 5731 · UNT", "any modern browser"])
svg.box(50, 262, 260, 112, "app", "Vercel · Next.js 16", ["App Router · React 19 · Tailwind 4", "chat · code · quiz · research", "admin & LLMOps dashboards"])
svg.box(50, 406, 260, 96, "app", "/api/backend proxy", ["forwards /api/backend/* to EC2", "maintenance notice when", "the backend is scheduled off"])
svg.path("M180 230 V260")
svg.path("M180 374 V404")

# ── AWS (centre) ──────────────────────────────────────────────────────
group(360, 96, 640, 664, "AWS · us-east-1", "", stroke="#f97316", fill="#fff7ed")
group(380, 140, 600, 388, "EC2 t3a.medium · Elastic IP", "runs Mon–Fri 09:00–17:00 CT (ec2-schedule.yml) · Docker, restart=unless-stopped",
      stroke="#fb923c", fill="#ffffff")
svg.box(400, 196, 270, 128, "app", "FastAPI backend", ["Uvicorn · Python 3.11 · :8010", "auth · chat (SSE) · code · quiz", "research · files · admin · health", "rolling candidate-container swap"])
svg.box(690, 196, 270, 128, "generate", "RAG + agents", ["S3 vector retriever · reranker", "LangGraph tutor/quiz/doubts", "agents (flag) · circuit breaker", "complexity-based LLM routing"])
svg.box(400, 340, 175, 76, "data", "PostgreSQL", ["users · sessions", "Alembic migrations"])
svg.box(590, 340, 175, 76, "cache", "Redis", ["rate limits · cache", "JWT blacklist"])
svg.box(780, 340, 180, 76, "observe", "Monitoring stack", ["Prometheus ← /metrics", "Grafana · Alertmanager"])
svg.box(400, 432, 560, 76, "observe", "Telemetry out", ["Prometheus remote_write → Grafana Cloud · Alertmanager → Slack",
                                                     "Langfuse v4 traces · PostHog events · container logs → CloudWatch"])
svg.path("M670 260 H688")
svg.path("M535 324 V338")
svg.path("M677 324 V338")

svg.box(380, 572, 190, 80, "generate", "Amazon Bedrock", ["Llama 3.3 · Claude 5.5 · GPT 6", "Titan Text v2 embeddings"])
svg.box(585, 572, 190, 80, "data", "Amazon S3", ["course docs · chunks", "vector index · results"])
svg.box(790, 572, 190, 80, "data", "Secrets Manager", ["app secrets in prod", ".env fallback in dev"])
svg.box(380, 664, 190, 80, "data", "DynamoDB", ["hybrid storage", "backend option"])
svg.box(585, 664, 190, 80, "observe", "CloudWatch Logs", ["awslogs driver", "/smart-ai-tutor/backend"])
svg.box(790, 664, 190, 80, "infra", "GHCR images", ["backend + frontend", "version-tagged"])
svg.path("M545 528 V570", color="violet")
svg.path("M680 528 V570")
svg.path("M885 528 V570")

# Vercel proxy → EC2
svg.path("M310 454 H340 V260 H398", label="HTTP", lx=340, ly=360)

# ── Managed services (right) ──────────────────────────────────────────
group(1030, 96, 340, 664, "Managed services", "")
svg.box(1050, 140, 300, 84, "data", "Neo4j Aura", ["knowledge graph · agent memory", "auto-resumed when paused"])
svg.box(1050, 240, 300, 84, "observe", "Langfuse Cloud (v4)", ["per-stage RAG traces", "prompt + cost analytics"])
svg.box(1050, 340, 300, 84, "observe", "PostHog", ["product + LLM analytics", "feature flags (agents, etc.)"])
svg.box(1050, 440, 300, 84, "observe", "Grafana Cloud", ["5 core dashboards", "long-term metrics"])
svg.box(1050, 540, 300, 84, "infra", "Slack", ["alerts · deploys · evals", "#all-smart-tutor-ai"])
svg.box(1050, 640, 300, 84, "infra", "Web search", ["SerpAPI → DuckDuckGo", "fallback for weak context"])
svg.path("M960 230 H1048", color="violet")

# ── CI/CD (bottom) ────────────────────────────────────────────────────
group(30, 784, 1340, 150, "GitHub Actions", "every PR and every push to main")
steps = [
    ("app", "Pull request", ["CodeRabbit + AI review", "Vercel preview"]),
    ("retrieve", "CI pipeline", ["backend · frontend · e2e", "SAST · CodeQL · DAST"]),
    ("infra", "Production deploy", ["build → smoke test", "→ EC2 swap + Vercel"]),
    ("observe", "Post-deploy", ["smoke tests", "GitOps promote (opt.)"]),
    ("observe", "Scheduled jobs", ["synthetic monitor · RAG eval", "security scans · EC2 schedule"]),
]
sw, sg = 240, 27
for i, (kind, title, lines) in enumerate(steps):
    x = 50 + i * (sw + sg)
    svg.box(x, 836, sw, 78, kind, title, lines)
    if i < len(steps) - 1:
        svg.path(f"M{x + sw} 875 H{x + sw + sg - 2}")

svg.text(W - 40, H - 30, "Source: docs/architecture/src/system_architecture.py · Oct 2026", size=11, fill="#94a3b8", anchor="end")
x = 50
for kind, label in [("app", "app / API"), ("generate", "AI / RAG"), ("data", "data"), ("cache", "cache"),
                    ("observe", "observability"), ("infra", "infra / delivery")]:
    fill, stroke, _ = PALETTE[kind]
    svg.parts.append(f'<rect x="{x}" y="{H - 43}" width="16" height="16" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
    svg.text(x + 22, H - 30, label, size=12, fill="#475569")
    x += 50 + 7 * len(label)

svg.save(OUT)
print(f"wrote {OUT}")
