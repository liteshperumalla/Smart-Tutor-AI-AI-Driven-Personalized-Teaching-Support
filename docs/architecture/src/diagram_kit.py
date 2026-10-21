"""Tiny SVG helpers shared by the architecture diagram generators.

Run the generators from the repo root, e.g.:
    python docs/architecture/src/rag_pipeline.py
"""

from html import escape

FONT = "Inter, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"

# Category palette: (fill, stroke, title text)
PALETTE = {
    "ingest": ("#ecfdf5", "#10b981", "#065f46"),
    "app": ("#eff6ff", "#3b82f6", "#1e3a8a"),
    "retrieve": ("#f0fdf4", "#22c55e", "#14532d"),
    "generate": ("#f5f3ff", "#8b5cf6", "#4c1d95"),
    "cache": ("#fffbeb", "#f59e0b", "#78350f"),
    "observe": ("#f8fafc", "#64748b", "#1e293b"),
    "data": ("#fef2f2", "#ef4444", "#7f1d1d"),
    "infra": ("#fff7ed", "#f97316", "#7c2d12"),
}


class Svg:
    def __init__(self, width, height, title, desc):
        self.w, self.h = width, height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" font-family="{FONT}" role="img" aria-labelledby="t d">',
            f"<title id=\"t\">{escape(title)}</title><desc id=\"d\">{escape(desc)}</desc>",
            "<defs>"
            + "".join(
                f'<marker id="arrow-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
                f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
                for k, c in {
                    "gray": "#475569", "teal": "#10b981", "amber": "#f59e0b", "violet": "#8b5cf6",
                }.items()
            )
            + "</defs>",
            # Solid card so the diagram reads the same in GitHub light and dark themes.
            f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="18" fill="#ffffff" stroke="#e2e8f0"/>',
        ]

    def text(self, x, y, s, size=13, weight=400, fill="#334155", anchor="start", italic=False):
        style = ' font-style="italic"' if italic else ""
        self.parts.append(
            f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}"{style}>{escape(s)}</text>'
        )

    def lane(self, x, y, w, h, label, sub=""):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#f8fafc" stroke="#e2e8f0"/>')
        # One <text> with a tspan so the subtitle always follows the label, whatever its width.
        tail = f'<tspan font-size="12" font-weight="400" fill="#64748b">   {escape(sub)}</tspan>' if sub else ""
        self.parts.append(
            f'<text x="{x + 18}" y="{y + 26}" font-size="13" font-weight="700" fill="#0f172a">{escape(label)}{tail}</text>'
        )

    def box(self, x, y, w, h, kind, title, lines=(), dashed=False, badge=None):
        fill, stroke, tcol = PALETTE[kind]
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.6"{dash}/>'
        )
        self.parts.append(f'<rect x="{x}" y="{y + 10}" width="4" height="{h - 20}" rx="2" fill="{stroke}"/>')
        self.text(x + 16, y + 26, title, size=14, weight=700, fill=tcol)
        for i, line in enumerate(lines):
            self.text(x + 16, y + 46 + i * 17, line, size=12, fill="#475569")
        if badge:
            bw = 7 * len(badge) + 14
            self.parts.append(
                f'<rect x="{x + w - bw - 8}" y="{y + 9}" width="{bw}" height="18" rx="9" fill="#ffffff" stroke="{stroke}"/>'
            )
            self.text(x + w - bw / 2 - 8, y + 22, badge, size=10.5, weight=600, fill=tcol, anchor="middle")

    def path(self, d, color="gray", dashed=False, width=1.8, label=None, lx=0, ly=0):
        col = {"gray": "#475569", "teal": "#10b981", "amber": "#f59e0b", "violet": "#8b5cf6"}[color]
        dash = ' stroke-dasharray="6 5"' if dashed else ""
        self.parts.append(
            f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{width}"{dash} '
            f'stroke-linejoin="round" marker-end="url(#arrow-{color})"/>'
        )
        if label:
            pad = 6.6 * len(label) + 12
            self.parts.append(
                f'<rect x="{lx - pad / 2}" y="{ly - 12}" width="{pad}" height="18" rx="9" fill="#ffffff" stroke="{col}"/>'
            )
            self.text(lx, ly + 1, label, size=11, weight=600, fill=col, anchor="middle")

    def chip(self, x, y, w, kind, title, sub):
        fill, stroke, tcol = PALETTE[kind]
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="52" rx="10" fill="{fill}" stroke="{stroke}"/>')
        self.text(x + 14, y + 22, title, size=13, weight=700, fill=tcol)
        self.text(x + 14, y + 40, sub, size=11.5, fill="#475569")

    def save(self, path):
        self.parts.append("</svg>")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(self.parts) + "\n")
