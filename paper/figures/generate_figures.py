"""
Generates every figure used in the n=100 study (paper/tokenmizer_ieee.tex)
from the committed benchmark results. Deterministic: re-running this
script against the same results JSON produces byte-identical PDFs
(matplotlib's PDF backend does not embed timestamps when
`pdf.fonttype` is set as below and `SOURCE_DATE_EPOCH` is unset only
affects the /CreationDate field, which is not compared here).

Run from the repository root:
    pip install matplotlib numpy
    python3 paper/figures/generate_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.titlesize": 9,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 7.5,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.6,
    "grid.color": "#dddddd",
    "grid.linewidth": 0.5,
})

RESULTS_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "results" / "memorybench_n100_20260813.json"
OUT_DIR = Path(__file__).resolve().parent

ORDER = [
    "tokenmizer_v0.5.2", "graphiti_style", "mem0_style", "graphrag_style",
    "memgpt_style", "sliding_window_10", "naive_truncation", "naive_summary",
]
LABEL = {
    "tokenmizer_v0.5.2": "TokenMizer", "graphiti_style": "Graphiti-style",
    "mem0_style": "Mem0-style", "graphrag_style": "GraphRAG-style",
    "memgpt_style": "MemGPT-style", "sliding_window_10": "Sliding window",
    "naive_truncation": "Naive truncation", "naive_summary": "Naive summary",
}
# Print-safe grayscale-distinguishable palette; TokenMizer in black to
# anchor the reader's eye across every figure.
COLOR = {
    "tokenmizer_v0.5.2": "#000000", "graphiti_style": "#1f77b4",
    "mem0_style": "#2ca02c", "graphrag_style": "#d62728",
    "memgpt_style": "#9467bd", "sliding_window_10": "#8c8c8c",
    "naive_truncation": "#8c8c8c", "naive_summary": "#8c8c8c",
}
CATS = ["completed_tasks", "pending_tasks", "decisions", "files", "errors"]
CAT_LABEL = {"completed_tasks": "Completed", "pending_tasks": "Pending",
             "decisions": "Decisions", "files": "Files", "errors": "Errors"}

data = json.loads(RESULTS_PATH.read_text())
results = data["results"]


def savefig(fig, name):
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"{name}.pdf")
    fig.savefig(OUT_DIR / f"{name}.png", dpi=300)
    plt.close(fig)
    print(f"wrote {name}.pdf / .png")


# ── Figure 1: overall ranking with 95% CI ─────────────────────────────────
def fig_overall():
    rows = sorted(ORDER, key=lambda m: -results[m]["macro_f1"])
    fig, ax = plt.subplots(figsize=(3.45, 2.6))
    ys = np.arange(len(rows))[::-1]
    for y, m in zip(ys, rows):
        f1 = results[m]["macro_f1"]
        lo, hi = results[m]["macro_f1_ci95"]
        c = COLOR[m]
        ax.plot([lo, hi], [y, y], color=c, lw=1.1, alpha=0.6, zorder=1)
        ax.barh(y, f1, height=0.55, color=c, alpha=0.9 if m == "tokenmizer_v0.5.2" else 0.75, zorder=2)
        ax.text(f1 + 0.015, y, f"{f1*100:.0f}%", va="center", fontsize=7.5)
    ax.set_yticks(ys)
    ax.set_yticklabels([LABEL[m] for m in rows])
    # set_yticklabels binds label i to the tick value at ys[i] (the order
    # we supplied both arrays in), not to sorted vertical position — so
    # the matching label index is i itself, with no reversal.
    for i, m in enumerate(rows):
        ax.get_yticklabels()[i].set_fontweight(
            "bold" if m == "tokenmizer_v0.5.2" else "normal")
    ax.set_xlim(0, 0.72)
    ax.set_xlabel("Macro F1 (95% bootstrap CI)")
    ax.grid(axis="x", zorder=0)
    savefig(fig, "fig_n100_overall")


# ── Figure 2: per-category heatmap ────────────────────────────────────────
def fig_category_heatmap():
    mat = np.zeros((len(ORDER), len(CATS)))
    for i, m in enumerate(ORDER):
        for j, c in enumerate(CATS):
            mat[i, j] = results[m]["micro_by_category"].get(c, {}).get("f1", np.nan)

    fig, ax = plt.subplots(figsize=(3.45, 2.7))
    im = ax.imshow(mat, cmap="Greys", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(CATS)))
    ax.set_xticklabels([CAT_LABEL[c] for c in CATS], rotation=30, ha="right")
    ax.set_yticks(range(len(ORDER)))
    ax.set_yticklabels([LABEL[m] for m in ORDER])
    for i in range(len(ORDER)):
        for j in range(len(CATS)):
            v = mat[i, j]
            color = "white" if v > 0.55 else "black"
            ax.text(j, i, f"{v*100:.0f}", ha="center", va="center", fontsize=6.5, color=color)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("F1 (%)", fontsize=7.5)
    cbar.ax.tick_params(labelsize=6.5)
    savefig(fig, "fig_n100_category_heatmap")


# ── Figure 3: register collapse ───────────────────────────────────────────
def fig_register():
    order = ["explicit", "semi", "mixed", "implicit"]
    xlabels = ["Explicit\nmarkers", "Plain\nsentence", "Mixed", "Indirect /\nburied"]
    fig, ax = plt.subplots(figsize=(3.45, 2.6))
    x = np.arange(len(order))
    for m in ORDER:
        vals = [results[m]["macro_f1_by_register"].get(r, np.nan) for r in order]
        is_anchor = m == "tokenmizer_v0.5.2"
        ax.plot(x, vals, marker="o", ms=3.5 if is_anchor else 2.8,
                lw=1.8 if is_anchor else 1.0, color=COLOR[m],
                alpha=1.0 if is_anchor else 0.75,
                label=LABEL[m], zorder=3 if is_anchor else 2)
    ax.set_xticks(x)
    ax.set_xticklabels(xlabels)
    ax.set_ylabel("Macro F1")
    ax.set_ylim(0, 1.0)
    ax.grid(axis="y")
    ax.legend(loc="upper right", ncol=1, frameon=False, fontsize=6.3, handlelength=1.5)
    savefig(fig, "fig_n100_register")


# ── Figure 4: TokenMizer paired difference vs each method ────────────────
def fig_paired_diff():
    comps = data["comparisons_vs_tokenmizer"]
    others = [m for m in ORDER if m != "tokenmizer_v0.5.2"]
    fig, ax = plt.subplots(figsize=(3.6, 2.5))
    ys = np.arange(len(others))[::-1]
    for y, m in zip(ys, others):
        c = comps[f"tokenmizer_v0.5.2_vs_{m}"]
        d, lo, hi = c["mean_diff"], c["ci_lo"], c["ci_hi"]
        color = "#000000" if lo > 0 else ("#999999" if lo <= 0 <= hi else "#555555")
        ax.plot([lo, hi], [y, y], color=color, lw=1.3)
        ax.plot(d, y, "o", color=color, ms=4)
    ax.axvline(0, color="#333333", lw=0.7, ls="--")
    ax.set_yticks(ys)
    ax.set_yticklabels([LABEL[m] for m in others])
    ax.set_xlabel(r"TokenMizer $-$ method (macro F1)")
    ax.grid(axis="x")
    savefig(fig, "fig_n100_paired_diff")


# ── Figure 5: TokenMizer domain-level variance ────────────────────────────
def fig_domain_variance():
    dom = results["tokenmizer_v0.5.2"]["macro_f1_by_domain"]
    items = sorted(dom.items(), key=lambda kv: kv[1])
    labels = [k for k, _ in items]
    vals = [v for _, v in items]
    fig, ax = plt.subplots(figsize=(3.45, 4.4))
    y = np.arange(len(labels))
    ax.barh(y, vals, color="#444444", height=0.65)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=6.3)
    ax.set_xlabel("TokenMizer macro F1")
    ax.set_xlim(0, 1.0)
    ax.grid(axis="x")
    savefig(fig, "fig_n100_domain_variance")


if __name__ == "__main__":
    fig_overall()
    fig_category_heatmap()
    fig_register()
    fig_paired_diff()
    fig_domain_variance()
