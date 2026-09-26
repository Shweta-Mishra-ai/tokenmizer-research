"""
Score memory methods on the real-agent sessions (see README.md in this
folder for the protocol, which was committed before this runner was run).

    python -m benchmarks.realworld.run_real --data DIR [--data DIR ...] \
        --json out.json [--incremental] [--limit N]

DIR holds sessions written by swe_trajectories.py (one JSON per session).
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
import zlib
from pathlib import Path

from benchmarks.memorybench.corpus import Session
from benchmarks.memorybench.methods import ORDER, REGISTRY, tokenmizer_real
from benchmarks.memorybench.methods.common import count_tokens
from benchmarks.memorybench.metrics import covers
from benchmarks.realworld.openhands_trajectories import is_artifact

THRESHOLD = 0.6


def _norm_path(p: str) -> str:
    """Strip a leading '/', and the SWE-bench checkout directory
    ("/astropy__astropy/..."), so an absolute path compares with a patch path."""
    p = p.strip().strip("`'\"").lstrip("/")
    head, _, rest = p.partition("/")
    if "__" in head and rest:
        p = rest
    return p


def path_match(extracted: str, truth: str) -> bool:
    a, b = _norm_path(extracted), _norm_path(truth)
    if not a or not b:
        return False
    short, long_ = sorted((a, b), key=len)
    return long_ == short or long_.endswith("/" + short)


def split_of(instance_id: str) -> str:
    """Dev/test split by issue (README.md): every system's attempt at one
    issue lands on the same side."""
    return "test" if zlib.crc32(instance_id.encode()) % 2 else "dev"


def load_sessions(dirs: list[str], limit: int | None,
                  split: str | None = None) -> list[tuple[Session, dict]]:
    out = []
    for d in dirs:
        for p in sorted(Path(d).glob("*.json")):
            raw = json.loads(p.read_text())
            instance = raw["id"].split("__", 1)[1]
            if split and split_of(instance) != split:
                continue
            s = Session(id=raw["id"], origin=raw["origin"], domain=raw["domain"],
                        messages=raw["messages"], ground_truth=raw["ground_truth"],
                        register=raw.get("register", "agent"), notes=raw.get("notes", ""))
            out.append((s, raw.get("error_kinds", {})))
    if limit:
        rng = random.Random(1729)
        out = rng.sample(out, min(limit, len(out)))
    return out


def score_session(result, session: Session, kinds: dict) -> dict:
    files_gt = session.expected("files")
    errs_gt = session.expected("errors")
    ext_files = [f for f in result.files if f and f.strip()]
    ext_errs = [e for e in result.errors if e and e.strip()]
    resume = result.resume_text or ""
    resume_lines = [ln for ln in resume.replace(" | ", "\n").splitlines() if ln.strip()]

    def err_hit(g):
        return any(covers(e, g, THRESHOLD) for e in ext_errs)

    def resume_has_file(g):
        n = _norm_path(g)
        return n in resume or n.rsplit("/", 1)[-1] in resume

    def resume_has_err(g):
        return any(covers(line, g, THRESHOLD) for line in resume_lines) or g in resume

    files_clean = [g for g in files_gt if not is_artifact(g)]
    runtime = [g for g in errs_gt if kinds.get(g) == "runtime"]
    lint = [g for g in errs_gt if kinds.get(g) == "lint"]
    return {
        "files_gt": len(files_gt),
        "files_hit": sum(any(path_match(f, g) for f in ext_files) for g in files_gt),
        "files_extracted": len(ext_files),
        # Secondary (post hoc for the SWE-agent systems): build artifacts removed.
        "files_clean_gt": len(files_clean),
        "files_clean_hit": sum(any(path_match(f, g) for f in ext_files) for g in files_clean),
        "runtime_gt": len(runtime), "runtime_hit": sum(err_hit(g) for g in runtime),
        "lint_gt": len(lint), "lint_hit": sum(err_hit(g) for g in lint),
        "errors_extracted": len(ext_errs),
        "errors_grounded": sum(any(covers(e, g, THRESHOLD) for g in errs_gt) for e in ext_errs),
        "resume_files_hit": sum(resume_has_file(g) for g in files_gt),
        "resume_runtime_hit": sum(resume_has_err(g) for g in runtime),
        "resume_tokens": result.resume_tokens,
        "session_tokens": sum(count_tokens(m["content"]) for m in session.messages),
        "extract_ms": result.extract_ms,
        "per_call_ms": result.per_call_ms,
    }


def _ratio_ci(rows: list[dict], num: str, den: str, iters: int = 2000, seed: int = 1729):
    """Micro ratio sum(num)/sum(den) with a session-level bootstrap CI."""
    tot_d = sum(r[den] for r in rows)
    point = sum(r[num] for r in rows) / tot_d if tot_d else float("nan")
    rng = random.Random(seed)
    boots = []
    for _ in range(iters):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        d = sum(r[den] for r in sample)
        if d:
            boots.append(sum(r[num] for r in sample) / d)
    boots.sort()
    lo = boots[int(0.025 * len(boots))] if boots else float("nan")
    hi = boots[int(0.975 * len(boots)) - 1] if boots else float("nan")
    return point, lo, hi


def summarise(rows: list[dict]) -> dict:
    out = {}
    for key, num, den in (("edited_file_recall", "files_hit", "files_gt"),
                          ("runtime_error_recall", "runtime_hit", "runtime_gt"),
                          ("lint_error_recall", "lint_hit", "lint_gt"),
                          ("error_precision_vs_gt", "errors_grounded", "errors_extracted"),
                          ("resume_file_coverage", "resume_files_hit", "files_gt"),
                          ("resume_runtime_error_coverage", "resume_runtime_hit", "runtime_gt")):
        p, lo, hi = _ratio_ci(rows, num, den)
        out[key] = {"value": p, "ci95": [lo, hi]}
    p, lo, hi = _ratio_ci(rows, "files_clean_hit", "files_clean_gt")
    out["edited_file_recall_no_artifacts"] = {"value": p, "ci95": [lo, hi]}
    # Per-session (macro) file recall: a session whose patch created a
    # thousand files would otherwise dominate the pooled ratio.
    per = [r["files_hit"] / r["files_gt"] for r in rows if r["files_gt"]]
    rng = random.Random(1729)
    boots = sorted(statistics.mean(per[rng.randrange(len(per))] for _ in per)
                   for _ in range(2000)) if per else []
    out["edited_file_recall_macro"] = {
        "value": statistics.mean(per) if per else float("nan"),
        "ci95": [boots[50], boots[1949]] if boots else [float("nan")] * 2}
    per_resume = [r["resume_files_hit"] / r["files_gt"] for r in rows if r["files_gt"]]
    out["resume_file_coverage_macro"] = statistics.mean(per_resume) if per_resume else float("nan")
    out["resume_tokens_mean"] = statistics.mean(r["resume_tokens"] for r in rows)
    out["compression_median"] = statistics.median(
        r["session_tokens"] / max(r["resume_tokens"], 1) for r in rows)
    out["extract_ms_median"] = statistics.median(r["extract_ms"] for r in rows)
    calls = sorted(c for r in rows for c in r["per_call_ms"])
    if calls:
        out["per_call_ms_median"] = statistics.median(calls)
        out["per_call_ms_p95"] = calls[int(0.95 * len(calls))]
        out["per_call_ms_p99"] = calls[int(0.99 * len(calls))]
    out["sessions"] = len(rows)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", action="append", required=True)
    ap.add_argument("--json", required=True)
    ap.add_argument("--method", action="append", help="default: all")
    ap.add_argument("--incremental", action="store_true",
                    help="TokenMizer only: one message per call (production condition)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--split", choices=("dev", "test"), required=True)
    args = ap.parse_args()

    sessions = load_sessions(args.data, args.limit, args.split)
    methods = args.method or [m for m in ORDER]
    per_method: dict[str, list[dict]] = {m: [] for m in methods}
    failures: dict[str, int] = {m: 0 for m in methods}
    started = time.monotonic()
    for i, (s, kinds) in enumerate(sessions):
        for m in methods:
            try:
                if m == tokenmizer_real.NAME:
                    result = tokenmizer_real.extract(s, incremental=args.incremental,
                                                     timeout=1800 if args.incremental else 300)
                else:
                    result = REGISTRY[m][0](s)
            except Exception as e:
                failures[m] += 1
                print(f"  [FAIL] {m} on {s.id}: {str(e)[:300]}", file=sys.stderr)
                continue
            row = score_session(result, s, kinds)
            row["session_id"] = s.id
            per_method[m].append(row)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(sessions)} sessions, {time.monotonic() - started:.0f}s",
                  file=sys.stderr)

    report = {
        "sessions": len(sessions),
        "data": args.data,
        "incremental": args.incremental,
        "split": args.split,
        "tokenmizer_product": tokenmizer_real.product_revision(),
        "failures": failures,
        "summary": {m: summarise(rows) for m, rows in per_method.items() if rows},
        "rows": per_method,
    }
    Path(args.json).write_text(json.dumps(report, indent=1))
    print(f"{'method':22} {'files R':>18} {'runtime R':>18} {'lint R':>18} {'err P(gt)':>18} "
          f"{'resume files':>14} {'resume err':>12} {'tok':>5} {'ms':>7}")
    for m, sm in report["summary"].items():
        def f(k):
            v = sm[k]
            return f"{v['value']*100:5.1f} [{v['ci95'][0]*100:4.1f},{v['ci95'][1]*100:4.1f}]"
        print(f"{m:22} {f('edited_file_recall'):>18} {f('runtime_error_recall'):>18} "
              f"{f('lint_error_recall'):>18} {f('error_precision_vs_gt'):>18} "
              f"{sm['resume_file_coverage']['value']*100:13.1f}% "
              f"{sm['resume_runtime_error_coverage']['value']*100:11.1f}% "
              f"{sm['resume_tokens_mean']:5.0f} {sm['extract_ms_median']:7.1f}")
    if any(failures.values()):
        print("failures:", failures)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
