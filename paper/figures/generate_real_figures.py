"""
Figures for the real-agent evaluation (paper Section "Evaluation on Real
Agent Sessions"), generated from the committed result files in
benchmarks/results/realworld/ so every plotted value can be regenerated.

Run from the repository root:
    pip install matplotlib numpy
    python3 paper/figures/generate_real_figures.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({
    "font.family": "serif", "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9,
    "xtick.labelsize": 7.5, "ytick.labelsize": 8, "legend.fontsize": 7.5,
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#333333", "axes.linewidth": 0.6,
    "grid.color": "#dddddd", "grid.linewidth": 0.5,
})

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "benchmarks" / "results" / "realworld"
OUT = Path(__file__).resolve().parent
TM = "tokenmizer_v0.5.2"
SYSTEMS = [("sweagent_gpt4", "SA\nGPT-4"), ("sweagent_gpt4o", "SA\nGPT-4o"),
           ("sweagent_claude3opus", "SA\nC3 Opus"),
           ("sweagent_claude35sonnet", "SA\nC3.5 S."),
           ("openhands_codeact21", "OH\nC3.5 S.")]


def _load(name: str) -> dict:
    return json.loads((RES / name).read_text())


def _ratio(rows, num, den):
    d = sum(r[den] for r in rows)
    return 100 * sum(r[num] for r in rows) / d if d else float("nan")


def fig_per_system(base: dict, fix: dict) -> None:
    """Runtime-error recall and resume coverage of runtime errors, per
    agent system, before and after the fixes (test split, batch)."""
    by = {"b": defaultdict(list), "f": defaultdict(list)}
    for key, d in (("b", base), ("f", fix)):
        for r in d["rows"][TM]:
            by[key][r["session_id"].split("__", 1)[0]].append(r)
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.5), sharey=True)
    x = np.arange(len(SYSTEMS))
    w = 0.38
    for ax, (num, title) in zip(axes, (("runtime_hit", "Runtime errors extracted"),
                                       ("resume_runtime_hit", "Runtime errors in the resume block"))):
        before = [_ratio(by["b"][s], num, "runtime_gt") for s, _ in SYSTEMS]
        after = [_ratio(by["f"][s], num, "runtime_gt") for s, _ in SYSTEMS]
        ax.bar(x - w / 2, before, w, color="#bbbbbb", label="before fixes")
        ax.bar(x + w / 2, after, w, color="#2b6cb0", label="after fixes")
        for xi, v in zip(x + w / 2, after):
            ax.text(xi, v + 1.5, f"{v:.0f}", ha="center", va="bottom", fontsize=6.5)
        ax.set_xticks(x, [lbl for _, lbl in SYSTEMS])
        ax.set_title(title)
        ax.set_ylim(0, 105)
        ax.yaxis.grid(True)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("% of ground-truth runtime errors")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=2,
               frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig_real_per_system.{ext}", dpi=300, metadata={"CreationDate": None})
    plt.close(fig)


def fig_methods(base: dict, fix: dict) -> None:
    """Runtime-error recall against resume size, every method (test split)."""
    names = {TM: "TokenMizer (before)", "graphiti_style": "Graphiti-style",
             "graphrag_style": "GraphRAG-style", "mem0_style": "Mem0-style",
             "memgpt_style": "MemGPT-style", "sliding_window_10": "Sliding window (10)",
             "naive_truncation": "Naive truncation", "naive_summary": "Naive summary"}
    pts = [(names[m], s["resume_tokens_mean"], 100 * s["resume_runtime_error_coverage"]["value"])
           for m, s in base["summary"].items()]
    s = fix["summary"][TM]
    pts.append(("TokenMizer (after)", s["resume_tokens_mean"], 100 * s["resume_runtime_error_coverage"]["value"]))
    cluster = {"Graphiti-style", "GraphRAG-style", "Mem0-style", "MemGPT-style"}
    offsets = {"Naive summary": (-4, 7), "Naive truncation": (-4, -11)}
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    for name, tok, cov in pts:
        ours = name.startswith("TokenMizer")
        ax.scatter(tok, cov, s=28 if ours else 18, color="#2b6cb0" if ours else "#777777",
                   zorder=3, marker="D" if name == "TokenMizer (after)" else "o")
        if name not in cluster:
            ax.annotate(name, (tok, cov), xytext=offsets.get(name, (5, 2)),
                        textcoords="offset points", fontsize=6.5)
    ctok = [t for n, t, _ in pts if n in cluster]
    ccov = [c for n, _, c in pts if n in cluster]
    ax.annotate("Graphiti-, Mem0-, GraphRAG-,\nMemGPT-style (" + f"{min(ccov):.0f}–{max(ccov):.0f}%)",
                (max(ctok), max(ccov)), xytext=(1000, 6), textcoords="data", fontsize=6.5,
                arrowprops={"arrowstyle": "-", "color": "#999999", "lw": 0.5})
    ax.set_xscale("log")
    ax.set_xlabel("Mean resume size (tokens, log scale)")
    ax.set_ylabel("Runtime errors in resume (%)")
    ax.set_xlim(100, 20000)
    ax.set_ylim(-5, 60)
    ax.grid(True)
    ax.set_axisbelow(True)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig_real_methods.{ext}", dpi=300, metadata={"CreationDate": None})
    plt.close(fig)


def main() -> None:
    base, fix = _load("test_base_all.json"), _load("test_fix.json")
    fig_per_system(base, fix)
    fig_methods(base, fix)
    print("wrote fig_real_per_system and fig_real_methods")


if __name__ == "__main__":
    main()
