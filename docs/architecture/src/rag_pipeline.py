"""Generate docs/architecture/rag-pipeline.svg (run from the repo root)."""

from pathlib import Path

from diagram_kit import Svg

OUT = Path(__file__).resolve().parents[1] / "rag-pipeline.svg"

W, H = 1400, 1000
BW, BH, GAP = 220, 88, 45
COLS = [60 + i * (BW + GAP) for i in range(5)]  # 60, 325, 590, 855, 1120


def mid(col):
    return COLS[col] + BW / 2


svg = Svg(
    W, H, "Smart Tutor AI — RAG pipeline",
    "Offline ingestion of INFO 5731 course materials into an S3 vector store, and the online "
    "per-message pipeline from the chat UI through retrieval, Bedrock generation, grounding and streaming.",
)
svg.text(W / 2, 46, "Smart Tutor AI — RAG Pipeline", size=26, weight=800, fill="#0f172a", anchor="middle")
svg.text(W / 2, 70, "Grounded answers from INFO 5731 course materials · AWS Bedrock · S3 vector store · SSE streaming",
         size=14, fill="#64748b", anchor="middle")

# ── ① Ingestion ────────────────────────────────────────────────────────
svg.lane(30, 92, 1340, 158, "① Ingestion", "offline · scripts/s3-vectors")
Y1 = 136
svg.box(COLS[0], Y1, BW, BH, "ingest", "Course corpus", ["11 modules of INFO 5731", "slides · PDFs · notebooks · videos"])
svg.box(COLS[1], Y1, BW, BH, "ingest", "Parse + OCR", ["LlamaIndex readers", "Tesseract for scanned PDFs"])
svg.box(COLS[2], Y1, BW, BH, "ingest", "Chunk", ["~512-token chunks", "page / slide metadata kept"])
svg.box(COLS[3], Y1, BW, BH, "ingest", "Embed", ["Amazon Titan Text v2", "1,024-dim vectors"])
svg.box(COLS[4], Y1, BW, BH, "data", "S3 vector store", ["s3://smart-ai-tutor-docs", "chunks/ + vector_index/"])
for c in range(4):
    svg.path(f"M{COLS[c] + BW} {Y1 + BH / 2} H{COLS[c + 1] - 2}", color="teal")

# ── ② Query ────────────────────────────────────────────────────────────
svg.lane(30, 272, 1340, 470, "② Query", "online · every chat message (POST /chat/sessions/{id}/messages)")
R1, R2, R3 = 314, 466, 618

svg.box(COLS[0], R1, BW, BH, "app", "Chat UI", ["Next.js 16 · React 19", "model picker per message"])
svg.box(COLS[1], R1, BW, BH, "app", "Vercel API proxy", ["/api/backend/* → EC2", "friendly 503 off-hours"])
svg.box(COLS[2], R1, BW, BH, "app", "FastAPI (SSE)", ["JWT cookies · CSRF", "Redis rate limiting"])
svg.box(COLS[3], R1, BW, BH, "app", "Route", ["greeting short-circuit", "LangGraph agents (flag)"])
svg.box(COLS[4], R1, BW, BH, "cache", "Answer cache", ["Redis · fuzzy match ≥0.95", "TTL 1 h"], dashed=True, badge="flag")
for c in range(4):
    svg.path(f"M{COLS[c] + BW} {R1 + BH / 2} H{COLS[c + 1] - 2}")

svg.box(COLS[0], R2, BW, BH, "retrieve", "Query enhancement", ["rewrite + expansion", "original kept for prompt"], dashed=True, badge="flag")
svg.box(COLS[1], R2, BW, BH, "retrieve", "Vector search", ["Titan query embedding", "cosine top-k over S3 index"])
svg.box(COLS[2], R2, BW, BH, "retrieve", "Cross-encoder rerank", ["ms-marco-MiniLM-L-12", "top-k → best 3"], dashed=True, badge="flag")
svg.box(COLS[3], R2, BW, BH, "retrieve", "Web fallback", ["only if course context is weak", "SerpAPI → DuckDuckGo"])
svg.box(COLS[4], R2, BW, BH, "generate", "Prompt assembly", ["numbered [Source n] context", "course or web QA template"])
for c in range(4):
    svg.path(f"M{COLS[c] + BW} {R2 + BH / 2} H{COLS[c + 1] - 2}")

svg.box(COLS[0], R3, BW, BH, "generate", "LLM synthesis", ["AWS Bedrock · streaming", "Llama 3.3 · Claude 5.5 · GPT 6"])
svg.box(COLS[1], R3, BW, BH, "generate", "Self-RAG check", ["is the answer grounded?", "adds a disclaimer if not"], dashed=True, badge="flag")
svg.box(COLS[2], R3, BW, BH, "cache", "Cache write-back", ["course answers only", "web answers never cached"], dashed=True, badge="flag")
svg.box(COLS[3], R3, BW, BH, "observe", "Trace + metrics", ["latency · tokens · cost", "per-stage spans"])
svg.box(COLS[4], R3, BW, BH, "app", "Stream to user", ["SSE tokens + citations", "links back to source pages"])
for c in range(4):
    svg.path(f"M{COLS[c] + BW} {R3 + BH / 2} H{COLS[c + 1] - 2}")

# Row wraps (end of a row → start of the next)
svg.path(f"M{mid(4)} {R1 + BH} V{R1 + BH + 26} H{mid(0)} V{R2 - 2}", label="miss", lx=mid(2) + 140, ly=R1 + BH + 26)
svg.path(f"M{mid(4)} {R2 + BH} V{R2 + BH + 26} H{mid(0)} V{R3 - 2}")

# S3 index feeds vector search (runs through the gap between columns 4 and 5)
gx = COLS[4] - GAP / 2
svg.path(f"M{COLS[4]} {Y1 + BH - 18} H{gx} V{R2 - 18} H{mid(1)} V{R2 - 2}", color="teal", dashed=True,
         label="index cached in memory", lx=gx - 120, ly=R2 - 18)

# Cache hit skips straight to the stream
rx = 1352
svg.path(f"M{COLS[4] + BW} {R1 + BH / 2} H{rx} V{R3 + BH / 2} H{COLS[4] + BW + 2}", color="amber", dashed=True,
         label="hit", lx=rx, ly=(R1 + R3) / 2 + BH / 2)

# ── ③ Observability & evaluation ──────────────────────────────────────
svg.lane(30, 764, 1340, 128, "③ Observability & evaluation", "every stage is traced")
CW = 310
cx = [60 + i * (CW + 13.3) for i in range(4)]
svg.chip(cx[0], 808, CW, "observe", "Langfuse v4", "rag-retrieval · web-search · llm-synthesis spans")
svg.chip(cx[1], 808, CW, "observe", "PostHog", "$ai_generation · llm_response_streamed · flags")
svg.chip(cx[2], 808, CW, "observe", "Prometheus + Grafana", "/metrics · SLO alerts → Alertmanager → Slack")
svg.chip(cx[3], 808, CW, "observe", "Scheduled RAG evaluation", "weekday LLM-judge: correctness · context recall")

# Legend
ly = 930
svg.parts.append(f'<rect x="60" y="{ly - 12}" width="34" height="18" rx="5" fill="#ffffff" stroke="#64748b"/>')
svg.text(102, ly + 2, "always on", size=12, fill="#475569")
svg.parts.append(f'<rect x="190" y="{ly - 12}" width="34" height="18" rx="5" fill="#ffffff" stroke="#64748b" stroke-dasharray="5 3"/>')
svg.text(232, ly + 2, "feature-flagged (backend/config.py, PostHog flags)", size=12, fill="#475569")
legend = [("ingest", "ingestion"), ("app", "app / API"), ("retrieve", "retrieval"), ("generate", "generation"),
          ("cache", "cache"), ("data", "storage"), ("observe", "observability")]
x = 600
for kind, label in legend:
    from diagram_kit import PALETTE
    fill, stroke, _ = PALETTE[kind]
    svg.parts.append(f'<rect x="{x}" y="{ly - 11}" width="16" height="16" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
    svg.text(x + 22, ly + 2, label, size=12, fill="#475569")
    x += 30 + 7 * len(label) + 14
svg.text(W - 40, H - 22, "Source: docs/architecture/src/rag_pipeline.py · Oct 2026", size=11, fill="#94a3b8", anchor="end")

svg.save(OUT)
print(f"wrote {OUT}")
