#!/usr/bin/env python3
"""
Multi-method memory benchmark — runner.

    python -m benchmarks.memorybench.run                     # full report
    python -m benchmarks.memorybench.run --json OUT.json      # + machine-readable results
    python -m benchmarks.memorybench.run --csv OUT.csv        # + flat per-session-method-category rows
    python -m benchmarks.memorybench.run --skip tokenmizer_v0.5.2   # skip a method (repeatable)
    python -m benchmarks.memorybench.run --threshold 0.6      # match strictness

Runs every registered method (see `methods/__init__.py`) over every
session in the committed 100-session corpus, scores each with the
asymmetric coverage relation in `metrics.py`, and reports:

  - per-method micro precision/recall/F1 per category
  - per-method macro F1 with a bootstrap 95% CI (resampled over sessions)
  - the same broken out by register (explicit/semi/implicit/mixed) and
    by corpus origin (synthetic/real) — because a single aggregate
    number hides exactly the thing a pattern-based method is weakest
    at, which is the point of labelling register in the first place
  - resume-token footprint and extraction latency per method
  - a paired bootstrap comparison of TokenMizer against every other
    method, so "TokenMizer wins" is a number with a confidence interval
    attached to it rather than an assertion

Nothing here should be read as measuring the named vendor libraries
(MemGPT, Mem0, Graphiti, GraphRAG) themselves — see
`methods/common.py` for why, and each `methods/*_style.py` module's
docstring for what specifically was and wasn't reproduced.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmarks.memorybench import corpus as corpus_mod
from benchmarks.memorybench.metrics import score
from benchmarks.memorybench.methods import ORDER, REGISTRY
from benchmarks.memorybench.methods.common import count_tokens

CATEGORIES = corpus_mod.CATEGORIES


@dataclass
class SessionRecord:
    session_id: str
    method: str
    domain: str
    origin: str
    register: str
    total_tokens: int
    resume_tokens: int
    extract_ms: float
    node_count: int
    category_scores: dict = field(default_factory=dict)  # cat -> CategoryScore

    @property
    def macro_f1(self) -> float:
        vals = [sc.f1 for sc in self.category_scores.values()]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def compression_ratio(self) -> float:
        return round(self.total_tokens / max(self.resume_tokens, 1), 2)


def run_all(sessions, threshold: float, skip: set[str]) -> list[SessionRecord]:
    records = []
    for s in sessions:
        total_tokens = sum(count_tokens(m["content"]) for m in s.messages)
        for name in ORDER:
            if name in skip:
                continue
            fn, _desc = REGISTRY[name]
            try:
                result = fn(s)
            except Exception as e:
                print(f"  [FAIL] {name} on {s.id}: {e}", file=sys.stderr)
                continue

            got = result.as_categories()
            cat_scores = {}
            for cat in CATEGORIES:
                want = s.expected(cat)
                if not want and not got.get(cat):
                    continue
                cat_scores[cat] = score(cat, got.get(cat, []), want, threshold)

            records.append(SessionRecord(
                session_id=s.id, method=name, domain=s.domain, origin=s.origin,
                register=s.register, total_tokens=total_tokens,
                resume_tokens=result.resume_tokens, extract_ms=result.extract_ms,
                node_count=result.node_count, category_scores=cat_scores,
            ))
    return records


# ── Aggregation ──────────────────────────────────────────────────────────

def micro_by_category(records: list[SessionRecord]) -> dict:
    totals = {}
    for r in records:
        for cat, sc in r.category_scores.items():
            t = totals.setdefault(cat, {"expected": 0, "extracted": 0, "tp": 0, "spurious": 0})
            t["expected"] += sc.expected
            t["extracted"] += sc.extracted
            t["tp"] += sc.true_positives
            t["spurious"] += len(sc.spurious)
    micro = {}
    for cat, t in totals.items():
        recall = t["tp"] / t["expected"] if t["expected"] else 1.0
        matched = t["extracted"] - t["spurious"]
        precision = matched / t["extracted"] if t["extracted"] else 1.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        micro[cat] = {"precision": precision, "recall": recall, "f1": f1, **t}
    return micro


def bootstrap_macro_f1(session_macro_f1s: list[float], iterations: int, rng: random.Random) -> tuple[float, float, float]:
    """Returns (mean, ci_lo, ci_hi) for the mean macro-F1, bootstrapped
    over sessions. If there's nothing to resample, returns the point value
    with a zero-width interval rather than raising."""
    n = len(session_macro_f1s)
    if n == 0:
        return 0.0, 0.0, 0.0
    point = sum(session_macro_f1s) / n
    if n < 2:
        return point, point, point
    means = []
    for _ in range(iterations):
        sample = [session_macro_f1s[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * iterations)]
    hi = means[min(int(0.975 * iterations), iterations - 1)]
    return point, lo, hi


def paired_bootstrap_diff(a: dict[str, float], b: dict[str, float],
                            iterations: int, rng: random.Random) -> dict:
    """Bootstrap CI on mean(a - b) over the session ids common to both,
    resampled jointly so the pairing is preserved. `a`, `b`: session_id -> macro_f1."""
    common = sorted(set(a) & set(b))
    n = len(common)
    if n == 0:
        return {"n": 0, "mean_diff": 0.0, "ci_lo": 0.0, "ci_hi": 0.0, "p_le_zero": 1.0}
    diffs = [a[k] - b[k] for k in common]
    point = sum(diffs) / n
    boot_means = []
    for _ in range(iterations):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        boot_means.append(sum(sample) / n)
    boot_means.sort()
    lo = boot_means[int(0.025 * iterations)]
    hi = boot_means[min(int(0.975 * iterations), iterations - 1)]
    p_le_zero = sum(1 for m in boot_means if m <= 0) / iterations
    return {"n": n, "mean_diff": round(point, 4), "ci_lo": round(lo, 4),
            "ci_hi": round(hi, 4), "p_le_zero": round(p_le_zero, 4)}


def session_macro_f1_map(records: list[SessionRecord], method: str) -> dict[str, float]:
    return {r.session_id: r.macro_f1 for r in records if r.method == method}


def build_report(sessions, records: list[SessionRecord], threshold: float,
                  bootstrap_iters: int, seed: int) -> dict:
    rng = random.Random(seed)
    by_method = defaultdict(list)
    for r in records:
        by_method[r.method].append(r)

    methods_present = [m for m in ORDER if m in by_method]

    method_summaries = {}
    for m in methods_present:
        recs = by_method[m]
        micro = micro_by_category(recs)
        f1s = [r.macro_f1 for r in recs]
        point, lo, hi = bootstrap_macro_f1(f1s, bootstrap_iters, rng)

        method_summaries[m] = {
            "sessions_scored": len(recs),
            "micro_by_category": micro,
            "macro_f1": round(point, 4),
            "macro_f1_ci95": [round(lo, 4), round(hi, 4)],
            "avg_resume_tokens": round(sum(r.resume_tokens for r in recs) / len(recs), 1),
            "avg_total_tokens": round(sum(r.total_tokens for r in recs) / len(recs), 1),
            "avg_compression_ratio": round(sum(r.compression_ratio for r in recs) / len(recs), 2),
            "avg_extract_ms": round(sum(r.extract_ms for r in recs) / len(recs), 3),
            "avg_node_count": round(sum(r.node_count for r in recs) / len(recs), 1),
        }

        # Breakdown by register and by origin — same macro-F1 metric,
        # sliced. This is where "explicit-text heuristics" gets checked
        # rather than assumed.
        by_register = defaultdict(list)
        by_origin = defaultdict(list)
        by_domain = defaultdict(list)
        for r in recs:
            by_register[r.register].append(r.macro_f1)
            by_origin[r.origin].append(r.macro_f1)
            by_domain[r.domain].append(r.macro_f1)

        method_summaries[m]["macro_f1_by_register"] = {
            k: round(sum(v) / len(v), 4) for k, v in sorted(by_register.items())
        }
        method_summaries[m]["macro_f1_by_origin"] = {
            k: round(sum(v) / len(v), 4) for k, v in sorted(by_origin.items())
        }
        method_summaries[m]["macro_f1_by_domain"] = {
            k: round(sum(v) / len(v), 4) for k, v in sorted(by_domain.items())
        }

    # Paired comparisons: TokenMizer vs every other present method.
    comparisons = {}
    anchor = "tokenmizer_v0.5.2"
    if anchor in methods_present:
        a_map = session_macro_f1_map(records, anchor)
        for m in methods_present:
            if m == anchor:
                continue
            b_map = session_macro_f1_map(records, m)
            comparisons[f"{anchor}_vs_{m}"] = paired_bootstrap_diff(
                a_map, b_map, bootstrap_iters, rng
            )

    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "corpus": corpus_mod.describe(sessions),
        "threshold": threshold,
        "bootstrap_iterations": bootstrap_iters,
        "bootstrap_seed": seed,
        "methods": {m: REGISTRY[m][1] for m in methods_present},
        "results": method_summaries,
        "comparisons_vs_tokenmizer": comparisons,
    }


# ── Reporting ────────────────────────────────────────────────────────────

def _bar(v: float, width: int = 14) -> str:
    filled = int(round(max(0.0, min(1.0, v)) * width))
    return "█" * filled + "·" * (width - filled)


def print_report(report: dict) -> None:
    print("=" * 92)
    print("TokenMizer & graph-memory methods — n=100 benchmark")
    print("=" * 92)
    print(report["corpus"])
    print(f"match threshold: {report['threshold']}  ·  bootstrap: {report['bootstrap_iterations']} "
          f"resamples, seed={report['bootstrap_seed']}")
    print()

    print(f"{'method':<20}{'macro F1':>10}   {'95% CI':<16}{'resume tok':>11}{'compress':>10}{'ms/session':>11}")
    print("-" * 92)
    for m, r in report["results"].items():
        lo, hi = r["macro_f1_ci95"]
        ci = f"[{lo:.0%}, {hi:.0%}]"
        print(f"{m:<20}{r['macro_f1']:>10.0%}   {ci:<16}{r['avg_resume_tokens']:>11.0f}"
              f"{r['avg_compression_ratio']:>9.1f}x{r['avg_extract_ms']:>11.2f}")
    print()

    print("Per-category micro F1 (all methods)")
    print("-" * 92)
    header = f"{'method':<20}" + "".join(f"{c.split('_')[0]:>14}" for c in CATEGORIES)
    print(header)
    for m, r in report["results"].items():
        row = f"{m:<20}"
        for c in CATEGORIES:
            f1 = r["micro_by_category"].get(c, {}).get("f1")
            row += f"{f1:>13.0%} " if f1 is not None else f"{'—':>14}"
        print(row)
    print()

    print("Macro F1 by register — explicit text vs. paraphrase vs. implicit reasoning")
    print("-" * 92)
    registers = sorted({k for r in report["results"].values() for k in r["macro_f1_by_register"]})
    print(f"{'method':<20}" + "".join(f"{reg:>13}" for reg in registers))
    for m, r in report["results"].items():
        row = f"{m:<20}"
        for reg in registers:
            v = r["macro_f1_by_register"].get(reg)
            row += f"{v:>12.0%} " if v is not None else f"{'—':>13}"
        print(row)
    print()

    print("Macro F1 by corpus origin (synthetic vs. real)")
    print("-" * 92)
    origins = sorted({k for r in report["results"].values() for k in r["macro_f1_by_origin"]})
    print(f"{'method':<20}" + "".join(f"{o:>13}" for o in origins))
    for m, r in report["results"].items():
        row = f"{m:<20}"
        for o in origins:
            v = r["macro_f1_by_origin"].get(o)
            row += f"{v:>12.0%} " if v is not None else f"{'—':>13}"
        print(row)
    print()

    if report["comparisons_vs_tokenmizer"]:
        print("TokenMizer vs. each method — paired bootstrap on macro F1 (positive = TokenMizer ahead)")
        print("-" * 92)
        print(f"{'comparison':<42}{'mean Δ':>10}{'95% CI':>20}{'P(Δ<=0)':>12}")
        for k, c in report["comparisons_vs_tokenmizer"].items():
            other = k.split("_vs_", 1)[1]
            ci = f"[{c['ci_lo']:+.1%}, {c['ci_hi']:+.1%}]"
            print(f"{'tokenmizer vs ' + other:<42}{c['mean_diff']:>+9.1%}{ci:>20}{c['p_le_zero']:>12.1%}")
        print()


def write_csv(records: list[SessionRecord], path: Path) -> None:
    rows = []
    for r in records:
        for cat, sc in r.category_scores.items():
            rows.append({
                "session_id": r.session_id, "method": r.method, "domain": r.domain,
                "origin": r.origin, "register": r.register, "category": cat,
                "expected": sc.expected, "extracted": sc.extracted,
                "true_positives": sc.true_positives,
                "precision": round(sc.precision, 4), "recall": round(sc.recall, 4),
                "f1": round(sc.f1, 4), "resume_tokens": r.resume_tokens,
                "total_tokens": r.total_tokens, "compression_ratio": r.compression_ratio,
                "extract_ms": r.extract_ms, "node_count": r.node_count,
            })
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", help="directory of labelled session JSON files (default: committed corpus)")
    ap.add_argument("--threshold", type=float, default=0.6)
    ap.add_argument("--bootstrap-iters", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1729)
    ap.add_argument("--skip", action="append", default=[], help="method name to skip (repeatable)")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--csv", dest="csv_out")
    args = ap.parse_args()

    try:
        sessions = corpus_mod.load(args.corpus)
        corpus_mod.validate_grounding(sessions, args.threshold)
    except corpus_mod.CorpusError as e:
        print(f"corpus error: {e}", file=sys.stderr)
        return 2

    print(f"Loaded {len(sessions)} sessions. Running {len(ORDER) - len(args.skip)} methods...\n")
    records = run_all(sessions, args.threshold, set(args.skip))

    report = build_report(sessions, records, args.threshold, args.bootstrap_iters, args.seed)
    print_report(report)

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(report, indent=2))
        print(f"Saved JSON: {args.json_out}")

    if args.csv_out:
        write_csv(records, Path(args.csv_out))
        print(f"Saved CSV: {args.csv_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
