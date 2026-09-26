"""
Markdown tables for the real-agent report, generated from result JSON files
written by run_real.py, so every number in the report can be regenerated.

    python -m benchmarks.realworld.tables --base BASE.json --fix FIX.json \
        [--base-inc BASE_INC.json --fix-inc FIX_INC.json]

BASE.json holds every method at the product commit before the fixes;
FIX.json holds TokenMizer after them. The comparison methods do not depend
on product code, so their rows come from BASE.json.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import defaultdict

TM = "tokenmizer_v0.5.2"
NAMES = {
    TM: "TokenMizer", "graphiti_style": "Graphiti-style", "graphrag_style": "GraphRAG-style",
    "mem0_style": "Mem0-style", "memgpt_style": "MemGPT-style",
    "sliding_window_10": "Sliding window (10)", "naive_truncation": "Naive truncation",
    "naive_summary": "Naive summary",
}


def _pct(m: dict, key: str) -> str:
    v = m[key]
    val, (lo, hi) = v["value"], v["ci95"]
    if val != val:   # NaN: no ground truth of this kind
        return "–"
    return f"{val * 100:.1f} [{lo * 100:.1f}, {hi * 100:.1f}]"


def main_table(base: dict, fix: dict) -> str:
    rows = [("TokenMizer (after fixes)", fix["summary"][TM]),
            ("TokenMizer (before fixes)", base["summary"][TM])]
    rows += [(NAMES[m], s) for m, s in base["summary"].items() if m != TM]
    out = ["| Method | Edited-file recall | Runtime-error recall | Lint-error recall | "
           "Error precision vs GT (lower bound) | Resume: files | Resume: runtime errors | "
           "Resume tokens |",
           "|---|---|---|---|---|---:|---:|---:|"]
    for name, s in rows:
        out.append(f"| {name} | {_pct(s, 'edited_file_recall')} | {_pct(s, 'runtime_error_recall')} | "
                   f"{_pct(s, 'lint_error_recall')} | {_pct(s, 'error_precision_vs_gt')} | "
                   f"{s['resume_file_coverage']['value'] * 100:.1f}% | "
                   f"{s['resume_runtime_error_coverage']['value'] * 100:.1f}% | "
                   f"{s['resume_tokens_mean']:.0f} |")
    return "\n".join(out)


def _system(session_id: str) -> str:
    return session_id.split("__", 1)[0]


def _ratio(rows, num, den):
    d = sum(r[den] for r in rows)
    return sum(r[num] for r in rows) / d if d else float("nan")


def paired_delta(base_rows: list, fix_rows: list, num: str, den: str,
                 iters: int = 2000, seed: int = 1729):
    """Micro-ratio difference (after - before) with a paired, session-level
    bootstrap: the same resampled sessions are scored before and after."""
    b = {r["session_id"]: r for r in base_rows}
    pairs = [(b[r["session_id"]], r) for r in fix_rows if r["session_id"] in b]
    point = _ratio([p[1] for p in pairs], num, den) - _ratio([p[0] for p in pairs], num, den)
    rng = random.Random(seed)
    boots = []
    for _ in range(iters):
        s = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        boots.append(_ratio([p[1] for p in s], num, den) - _ratio([p[0] for p in s], num, den))
    boots.sort()
    return point, boots[int(0.025 * iters)], boots[int(0.975 * iters) - 1], len(pairs)


def delta_table(base: dict, fix: dict) -> str:
    out = ["| Metric | Before | After | Paired Δ (points) [95% CI] |", "|---|---:|---:|---|"]
    br, fr = base["rows"][TM], fix["rows"][TM]
    for label, num, den in (("Edited-file recall", "files_hit", "files_gt"),
                            ("Edited-file recall, build artifacts removed", "files_clean_hit", "files_clean_gt"),
                            ("Runtime-error recall", "runtime_hit", "runtime_gt"),
                            ("Lint-error recall", "lint_hit", "lint_gt"),
                            ("Error precision vs GT (lower bound)", "errors_grounded", "errors_extracted"),
                            ("Resume coverage: edited files", "resume_files_hit", "files_gt"),
                            ("Resume coverage: runtime errors", "resume_runtime_hit", "runtime_gt")):
        d, lo, hi, n = paired_delta(br, fr, num, den)
        out.append(f"| {label} | {_ratio(br, num, den) * 100:.1f}% | {_ratio(fr, num, den) * 100:.1f}% | "
                   f"{d * 100:+.1f} [{lo * 100:+.1f}, {hi * 100:+.1f}] |")
    return "\n".join(out)


def per_system_table(base: dict, fix: dict) -> str:
    by_b, by_f = defaultdict(list), defaultdict(list)
    for r in base["rows"][TM]:
        by_b[_system(r["session_id"])].append(r)
    for r in fix["rows"][TM]:
        by_f[_system(r["session_id"])].append(r)
    out = ["| System | Sessions | File recall (per session) before → after | "
           "Runtime-error recall before → after | Resume: runtime errors before → after |",
           "|---|---:|---|---|---|"]
    for sysname in sorted(by_f):
        b, f = by_b[sysname], by_f[sysname]

        def macro(rows):
            per = [r["files_hit"] / r["files_gt"] for r in rows if r["files_gt"]]
            return statistics.mean(per) * 100 if per else float("nan")
        out.append(f"| {sysname} | {len(f)} | {macro(b):.1f} → {macro(f):.1f} | "
                   f"{_ratio(b, 'runtime_hit', 'runtime_gt') * 100:.1f} → "
                   f"{_ratio(f, 'runtime_hit', 'runtime_gt') * 100:.1f} | "
                   f"{_ratio(b, 'resume_runtime_hit', 'runtime_gt') * 100:.1f} → "
                   f"{_ratio(f, 'resume_runtime_hit', 'runtime_gt') * 100:.1f} |")
    return "\n".join(out)


def latency_table(base_inc: dict, fix_inc: dict) -> str:
    out = ["| Product | Per-request median | p95 | p99 | Sessions |", "|---|---:|---:|---:|---:|"]
    for name, d in (("Before fixes", base_inc), ("After fixes", fix_inc)):
        s = d["summary"][TM]
        out.append(f"| {name} | {s['per_call_ms_median']:.1f} ms | {s['per_call_ms_p95']:.1f} ms | "
                   f"{s['per_call_ms_p99']:.1f} ms | {s['sessions']} |")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True)
    ap.add_argument("--fix", required=True)
    ap.add_argument("--base-inc")
    ap.add_argument("--fix-inc")
    args = ap.parse_args()
    base, fix = json.load(open(args.base)), json.load(open(args.fix))
    print("### All methods, test split\n")
    print(main_table(base, fix))
    print("\n### TokenMizer before and after the fixes, test split (paired)\n")
    print(delta_table(base, fix))
    print("\n### TokenMizer by system, test split\n")
    print(per_system_table(base, fix))
    if args.base_inc and args.fix_inc:
        bi, fi = json.load(open(args.base_inc)), json.load(open(args.fix_inc))
        print("\n### Incremental (production) condition, test split\n")
        print(delta_table(bi, fi))
        print("\n### Per-request extraction cost, incremental (parallel runs; see text)\n")
        print(latency_table(bi, fi))


if __name__ == "__main__":
    main()
