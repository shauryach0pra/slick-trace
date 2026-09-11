"""Render the Ask Slick Trace demo Q&A as a terminal-style screenshot."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib.pyplot as plt

from varuna_core.nlp_query import CaseKB, ask

DEMO_QUESTIONS = [
    "Which vessels crossed the likely origin zone from 02:00 to 05:00 UTC?",
    "Why is the top candidate above the second candidate?",
    "Find the current-field source used in this report.",
    "Find cases similar to this curved slick.",
]


def wrap(text, width=88):
    import textwrap
    return textwrap.wrap(text, width=width) or [""]


def render(case_dir: str = "data/cases/case_0001", out_path: str | None = None):
    kb = CaseKB(case_dir)
    lines = ["$ ask-varuna --incident case_0001", ""]
    for q in DEMO_QUESTIONS:
        r = ask(kb, q)
        color_tag = "OK" if r.supported else "REFUSED"
        lines.append(f">>> {q}")
        lines.append(f"[{r.intent} | {color_tag}]")
        if r.filters:
            lines.extend(wrap(f"filters: {r.filters}"))
        lines.extend(wrap(r.answer))
        if r.citations:
            cite_line = f"cites: {r.citations[0]}" + (f" (+{len(r.citations)-1} more)" if len(r.citations) > 1 else "")
            lines.extend(wrap(cite_line))
        lines.append("")

    fig, ax = plt.subplots(figsize=(10.5, 0.28 * len(lines) + 0.5))
    ax.axis("off")
    ax.set_facecolor("#0d1117")
    fig.patch.set_facecolor("#0d1117")
    y = 1.0
    dy = 1.0 / (len(lines) + 1)
    for line in lines:
        color = "#58a6ff" if line.startswith(">>>") else \
                "#3fb950" if "[" in line and "OK" in line else \
                "#f85149" if "REFUSED" in line else \
                "#8b949e" if line.startswith(("filters:", "cites:")) else "#e6edf3"
        ax.text(0.01, y, line, transform=ax.transAxes, fontsize=8.3, family="monospace",
                color=color, va="top")
        y -= dy

    fig.tight_layout()
    out_path = out_path or os.path.join(case_dir, "ask_varuna_transcript.png")
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    path = render()
    print(f"Saved {path}")
