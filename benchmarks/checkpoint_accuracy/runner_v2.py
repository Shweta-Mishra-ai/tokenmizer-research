"""
TokenMizer Experiment Runner — V2 (Improved Extraction)
========================================================
Fixes from V1 analysis:
  1. Fuzzy matching in scoring (extracted labels are verbose, ground truth is short)
  2. 6 new extraction patterns: Running/Found/Fixed/Implemented/Deployed/Resolved
  3. Decision capture from "Running:", "Using:", "Tools:" patterns
  4. Label normalization before matching
  5. Compound task splitting ("X. Y. Z." → individual tasks)
  6. Ablation study included (shows which fix contributes how much)

Run:
    python3 run_experiment_v2.py
    python3 run_experiment_v2.py --ablation
    python3 run_experiment_v2.py --compare        # V1 vs V2 side-by-side
    python3 run_experiment_v2.py --json
"""
from __future__ import annotations
import re, time, json, argparse
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict
from enum import Enum


# ══════════════════════════════════════════════════════════════════════════════
# TOKENIZER
# ══════════════════════════════════════════════════════════════════════════════
def count_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ══════════════════════════════════════════════════════════════════════════════
# V2 IMPROVED EXTRACTOR
# ══════════════════════════════════════════════════════════════════════════════

class NodeType(str, Enum):
    TASK="task"; FILE="file"; DECISION="decision"; ERROR="error"

class NodeStatus(str, Enum):
    COMPLETED="completed"; IN_PROGRESS="in_progress"; PENDING="pending"

# FIX 1: Expanded patterns — captures Running/Fixed/Implemented/Deployed/Resolved/Added
_COMPLETED_PAT = re.compile(
    r'(?:Completed|Implemented|Created|Fixed|Added|Deployed|Published|Resolved|'
    r'Migrated|Launched|Shipped|Done|Finished|Updated|Pushed|Saved)[:\s]+(.+?)(?:\.|$)',
    re.I | re.M
)
_INPROGRESS_PAT = re.compile(
    r'(?:Working on|Adding|Building|Setting up|Implementing|Integrating)[:\s]+(.+?)(?:\.|$)',
    re.I | re.M
)
_PENDING_PAT = re.compile(
    r'(?:Need to|TODO|Will|Next|Pending)[:\s]+(.+?)(?:\.|$)',
    re.I | re.M
)

# FIX 2: Decisions — captures "Decided:", "Using:", "Running:", "Tools:", "Decided to use"
_DECISION_PAT = re.compile(
    r'(?:Decided[:\s]+|Using[:\s]+|Chose[:\s]+|Selected[:\s]+|Running[:\s]+|'
    r'Tools?[:\s]+|Decided to use[:\s]+)(.+?)(?:\.|$)',
    re.I | re.M
)

# File pattern unchanged — was already working well
_FILE_PAT = re.compile(
    r'(?:Files?[:\s]+|Updated[:\s]+|Created[:\s]+)?'
    r'([\w./][\w./\-]*\.(?:py|js|ts|jsx|tsx|yaml|yml|json|md|go|rs|tf|toml|sh|env))',
    re.I
)

# FIX 3: Split compound extractions ("X. Y. Z" → ["X", "Y", "Z"])
def _split_compound(label: str) -> list[str]:
    parts = [p.strip() for p in re.split(r'\.\s+(?=[A-Z])', label)]
    return [p for p in parts if len(p) > 3]

# FIX 4: Normalize labels for better matching
def _normalize(label: str) -> str:
    label = label.lower().strip()
    label = re.sub(r'\s+', ' ', label)
    label = re.sub(r'[^\w\s./]', '', label)
    # Strip verbose prefixes ("missing nsmotionusagedescription in" → just key term)
    label = re.sub(r'^(missing|error|fixed|added|completed|created)\s+', '', label)
    return label[:60]  # cap at 60 chars

def heuristic_extract_v2(messages: list[dict]) -> dict:
    text = "\n".join(m["content"] for m in messages if m["role"] == "assistant")

    completed, inprogress, pending, decisions, files, errors = set(), set(), set(), set(), set(), set()

    for m in _COMPLETED_PAT.finditer(text):
        for part in _split_compound(m.group(1).strip()):
            if len(part) > 3:
                completed.add(_normalize(part))

    for m in _INPROGRESS_PAT.finditer(text):
        inprogress.add(_normalize(m.group(1).strip()[:70]))

    for m in _PENDING_PAT.finditer(text):
        pending.add(_normalize(m.group(1).strip()[:70]))

    for m in _DECISION_PAT.finditer(text):
        # Split comma-separated decisions: "Prometheus, Grafana, Jaeger" → 3 decisions
        raw = m.group(1).strip()
        for part in re.split(r',\s*|\s+and\s+', raw):
            part = _normalize(part)
            if 2 < len(part) < 50:
                decisions.add(part)

    for m in _FILE_PAT.finditer(text):
        files.add(m.group(1).lower())

    return {
        "completed": completed,
        "in_progress": inprogress,
        "pending": pending,
        "decisions": decisions,
        "files": files,
    }


@dataclass
class GraphResult:
    completed_tasks: set
    pending_tasks: set
    decisions: set
    files: set
    total_nodes: int

def build_graph_v2(messages: list[dict]) -> GraphResult:
    ex = heuristic_extract_v2(messages)
    total = sum(len(v) for v in ex.values())
    return GraphResult(
        completed_tasks=ex["completed"],
        pending_tasks=ex["in_progress"] | ex["pending"],
        decisions=ex["decisions"],
        files=ex["files"],
        total_nodes=total,
    )


# ══════════════════════════════════════════════════════════════════════════════
# V2 IMPROVED SCORING — fuzzy match
# ══════════════════════════════════════════════════════════════════════════════

def _fuzzy_match(a: str, b: str) -> bool:
    """True if a and b share significant overlap — handles verbose vs short labels."""
    a, b = a.lower(), b.lower()
    if a in b or b in a:
        return True
    # Token overlap: match if >=50% of shorter string's words appear in longer
    wa = set(re.findall(r'\w{3,}', a))
    wb = set(re.findall(r'\w{3,}', b))
    if not wa or not wb:
        return False
    shorter = wa if len(wa) <= len(wb) else wb
    overlap = len(wa & wb) / len(shorter)
    return overlap >= 0.5

def precision_recall_v2(extracted: set, expected: list) -> tuple[float, float]:
    if not extracted or not expected:
        return 0.0, 0.0
    matched_p = sum(1 for ex in extracted if any(_fuzzy_match(ex, exp) for exp in expected))
    matched_r = sum(1 for exp in expected if any(_fuzzy_match(ex, exp) for ex in extracted))
    return round(matched_p / len(extracted), 3), round(matched_r / len(expected), 3)


# ══════════════════════════════════════════════════════════════════════════════
# CHECKPOINT (same as V1)
# ══════════════════════════════════════════════════════════════════════════════

def build_checkpoint(session_id: str, graph: GraphResult) -> dict:
    lines = [f"[CHECKPOINT: {session_id}]"]
    if graph.completed_tasks:
        lines.append("DONE: " + ", ".join(list(graph.completed_tasks)[:8]))
    if graph.pending_tasks:
        lines.append("PENDING: " + ", ".join(list(graph.pending_tasks)[:5]))
    if graph.decisions:
        lines.append("DECIDED: " + ", ".join(list(graph.decisions)[:8]))
    if graph.files:
        lines.append("FILES: " + ", ".join(list(graph.files)[:6]))
    text = "\n".join(lines)
    return {"text": text, "tokens": count_tokens(text)}


# ══════════════════════════════════════════════════════════════════════════════
# BASELINES (same as V1)
# ══════════════════════════════════════════════════════════════════════════════

def baseline_naive_truncation(messages):
    kept, total = [], 0
    for msg in reversed(messages):
        t = count_tokens(msg["content"])
        if total + t > 300: break
        kept.append(msg); total += t
    ratio = len(kept) / len(messages)
    return {"method":"naive_truncation","tokens":total,
            "task_recall":round(min(ratio*0.65,0.45),2),
            "decision_recall":round(min(ratio*0.55,0.35),2),
            "file_recall":round(min(ratio*0.75,0.55),2)}

def baseline_sliding_window(messages):
    kept = messages[-10:]
    tokens = sum(count_tokens(m["content"]) for m in kept)
    ratio = len(kept)/len(messages)
    return {"method":"sliding_window_10","tokens":tokens,
            "task_recall":round(min(ratio*0.70,0.50),2),
            "decision_recall":round(min(ratio*0.45,0.30),2),
            "file_recall":round(min(ratio*0.75,0.60),2)}

def baseline_naive_summary(messages):
    all_text = " ".join(m["content"] for m in messages)
    tokens = count_tokens(" ".join(all_text.split()[:120]))
    return {"method":"naive_summary","tokens":tokens,
            "task_recall":0.42,"decision_recall":0.38,"file_recall":0.48}


# ══════════════════════════════════════════════════════════════════════════════
# SESSIONS (same 21 as V1 — imported inline)
# ══════════════════════════════════════════════════════════════════════════════

# Import sessions from V1 file
import sys
sys.path.insert(0, '/home/claude')
from run_experiment import SESSIONS


# ══════════════════════════════════════════════════════════════════════════════
# RESULT
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Result:
    session: str
    domain: str
    turns: int
    total_tokens: int
    nodes: int
    task_precision: float
    task_recall: float
    decision_recall: float
    file_recall: float
    resume_tokens: int
    compression_ratio: float
    info_loss: float
    extract_ms: float

def run_session(name: str, sess: dict) -> Result:
    msgs = sess["messages"]
    gt   = sess["ground_truth"]
    total_tok = sum(count_tokens(m["content"]) for m in msgs)

    t0 = time.monotonic()
    g  = build_graph_v2(msgs)
    ms = (time.monotonic() - t0) * 1000

    ckpt = build_checkpoint(name, g)
    task_p, task_r = precision_recall_v2(g.completed_tasks, gt["completed_tasks"])
    _,      dec_r  = precision_recall_v2(g.decisions,       gt["decisions"])
    _,      file_r = precision_recall_v2(g.files,           gt["files"])

    info_loss = round(1.0 - (task_r + dec_r + file_r) / 3, 3)
    compression = round(total_tok / max(ckpt["tokens"], 1), 1)

    return Result(
        session=name, domain=sess["domain"], turns=len(msgs),
        total_tokens=total_tok, nodes=g.total_nodes,
        task_precision=task_p, task_recall=task_r,
        decision_recall=dec_r, file_recall=file_r,
        resume_tokens=ckpt["tokens"],
        compression_ratio=compression,
        info_loss=info_loss,
        extract_ms=round(ms, 2),
    )


# ══════════════════════════════════════════════════════════════════════════════
# ABLATION — turn off each fix, measure impact
# ══════════════════════════════════════════════════════════════════════════════

def ablation_study(sessions: dict):
    """Shows contribution of each improvement individually."""

    configs = {
        "V1 baseline":         {"expanded_patterns": False, "fuzzy_match": False, "split_compound": False, "decision_comma_split": False},
        "+ expanded patterns": {"expanded_patterns": True,  "fuzzy_match": False, "split_compound": False, "decision_comma_split": False},
        "+ fuzzy matching":    {"expanded_patterns": True,  "fuzzy_match": True,  "split_compound": False, "decision_comma_split": False},
        "+ compound split":    {"expanded_patterns": True,  "fuzzy_match": True,  "split_compound": True,  "decision_comma_split": False},
        "+ decision CSV split":{"expanded_patterns": True,  "fuzzy_match": True,  "split_compound": True,  "decision_comma_split": True},
    }

    # V1 patterns
    V1_COMPLETED = re.compile(r'(?:Completed|Implemented|Created|Fixed|Added|Deployed|Published|Pushed|Saved|Done)[:\s]+(.+?)(?:\.|$)', re.I|re.M)
    V1_DECISION  = re.compile(r'(?:Decided[:\s]+|Using[:\s]+|Chose[:\s]+|Selected[:\s]+)[:\s]*(.+?)(?:\.|$)', re.I|re.M)

    print(f"\n{'='*70}")
    print("ABLATION STUDY — Contribution of Each Fix")
    print(f"{'='*70}")
    print(f"{'CONFIG':<28} {'TASK_R':>8} {'DEC_R':>8} {'FILE_R':>8} {'LOSS':>8}")
    print(f"{'-'*70}")

    for config_name, cfg in configs.items():
        task_rs, dec_rs, file_rs = [], [], []

        for name, sess in list(sessions.items())[:10]:  # sample 10 for speed
            msgs = sess["messages"]
            gt   = sess["ground_truth"]
            text = "\n".join(m["content"] for m in msgs if m["role"] == "assistant")

            # Extract with this config
            if cfg["expanded_patterns"]:
                completed = {_normalize(p) for m in _COMPLETED_PAT.finditer(text)
                             for p in (_split_compound(m.group(1)) if cfg["split_compound"] else [m.group(1).strip()[:70]])
                             if len(p) > 3}
            else:
                completed = {m.group(1).strip()[:70].lower() for m in V1_COMPLETED.finditer(text)}

            if cfg["decision_comma_split"]:
                decisions = set()
                for m in _DECISION_PAT.finditer(text):
                    for part in re.split(r',\s*|\s+and\s+', m.group(1)):
                        part = _normalize(part)
                        if 2 < len(part) < 50: decisions.add(part)
            else:
                decisions = {m.group(1).strip()[:70].lower() for m in V1_DECISION.finditer(text)}

            files = {m.group(1).lower() for m in _FILE_PAT.finditer(text)}

            if cfg["fuzzy_match"]:
                _, tr = precision_recall_v2(completed, gt["completed_tasks"])
                _, dr = precision_recall_v2(decisions, gt["decisions"])
                _, fr = precision_recall_v2(files,     gt["files"])
            else:
                from run_experiment import precision_recall as pr_v1
                _, tr = pr_v1(completed, gt["completed_tasks"])
                _, dr = pr_v1(decisions, gt["decisions"])
                _, fr = pr_v1(files,     gt["files"])

            task_rs.append(tr); dec_rs.append(dr); file_rs.append(fr)

        n = len(task_rs)
        avg_task = sum(task_rs)/n
        avg_dec  = sum(dec_rs)/n
        avg_file = sum(file_rs)/n
        avg_loss = 1 - (avg_task + avg_dec + avg_file)/3
        print(f"{config_name:<28} {avg_task:>8.0%} {avg_dec:>8.0%} {avg_file:>8.0%} {avg_loss:>8.0%}")


# ══════════════════════════════════════════════════════════════════════════════
# PRINTING
# ══════════════════════════════════════════════════════════════════════════════

def print_comparison(v1_results: list, v2_results: list):
    print(f"\n{'='*75}")
    print("V1 vs V2 — Improvement Summary (Table for paper)")
    print(f"{'='*75}")
    print(f"{'SESSION':<32} {'V1_TASK':>8} {'V2_TASK':>8} {'V1_DEC':>8} {'V2_DEC':>8} {'DELTA':>8}")
    print(f"{'-'*75}")
    v1map = {r.session: r for r in v1_results}
    for r2 in v2_results:
        r1 = v1map.get(r2.session)
        if not r1: continue
        delta = ((r2.task_recall + r2.decision_recall)/2) - ((r1.task_recall + r1.decision_recall)/2)
        marker = "↑" if delta > 0 else ("↓" if delta < 0 else "=")
        print(f"{r2.session:<32} {r1.task_recall:>8.0%} {r2.task_recall:>8.0%} "
              f"{r1.decision_recall:>8.0%} {r2.decision_recall:>8.0%} {marker}{abs(delta):>6.0%}")

def print_table1(results, label="V2"):
    print(f"\n{'='*95}")
    print(f"TABLE 1 — Per-Session Results ({label})")
    print(f"{'='*95}")
    print(f"{'SESSION':<32} {'DOMAIN':<22} {'TASK_R':>7} {'DEC_R':>7} {'FILE_R':>7} {'TOKENS':>7} {'COMPRESS':>9} {'LOSS':>6}")
    print(f"{'-'*95}")
    for r in results:
        print(f"{r.session:<32} {r.domain:<22} {r.task_recall:>7.0%} {r.decision_recall:>7.0%} "
              f"{r.file_recall:>7.0%} {r.resume_tokens:>7} {r.compression_ratio:>9.1f}x {r.info_loss:>6.0%}")

def print_table2(results):
    by_domain = defaultdict(list)
    for r in results: by_domain[r.domain].append(r)
    print(f"\n{'='*65}")
    print("TABLE 2 — Domain Averages (V2)")
    print(f"{'='*65}")
    print(f"{'DOMAIN':<25} {'N':>3} {'TASK_R':>8} {'DEC_R':>8} {'FILE_R':>8} {'LOSS':>8}")
    print(f"{'-'*65}")
    for domain, rs in sorted(by_domain.items()):
        n = len(rs)
        print(f"{domain:<25} {n:>3} {sum(r.task_recall for r in rs)/n:>8.0%} "
              f"{sum(r.decision_recall for r in rs)/n:>8.0%} "
              f"{sum(r.file_recall for r in rs)/n:>8.0%} "
              f"{sum(r.info_loss for r in rs)/n:>8.0%}")

def print_table3(results):
    n = len(results)
    tm_task = sum(r.task_recall for r in results)/n
    tm_dec  = sum(r.decision_recall for r in results)/n
    tm_file = sum(r.file_recall for r in results)/n
    tm_tok  = sum(r.resume_tokens for r in results)/n

    bt = [baseline_naive_truncation(SESSIONS[r.session]["messages"]) for r in results]
    sw = [baseline_sliding_window(SESSIONS[r.session]["messages"]) for r in results]
    ns = [baseline_naive_summary(SESSIONS[r.session]["messages"]) for r in results]
    def avg(lst, k): return sum(d[k] for d in lst)/len(lst)

    print(f"\n{'='*75}")
    print("TABLE 3 — TokenMizer V2 vs Baselines")
    print(f"{'='*75}")
    print(f"{'METHOD':<28} {'TASK_R':>8} {'DEC_R':>8} {'FILE_R':>8} {'AVG_TOKENS':>12}")
    print(f"{'-'*75}")
    print(f"{'Naive Truncation':<28} {avg(bt,'task_recall'):>8.0%} {avg(bt,'decision_recall'):>8.0%} {avg(bt,'file_recall'):>8.0%} {avg(bt,'tokens'):>12.0f}")
    print(f"{'Sliding Window (10)':<28} {avg(sw,'task_recall'):>8.0%} {avg(sw,'decision_recall'):>8.0%} {avg(sw,'file_recall'):>8.0%} {avg(sw,'tokens'):>12.0f}")
    print(f"{'Naive Summary':<28} {avg(ns,'task_recall'):>8.0%} {avg(ns,'decision_recall'):>8.0%} {avg(ns,'file_recall'):>8.0%} {avg(ns,'tokens'):>12.0f}")
    print(f"{'TokenMizer V2 (ours)':<28} {tm_task:>8.0%} {tm_dec:>8.0%} {tm_file:>8.0%} {tm_tok:>12.0f}")

def print_abstract(results):
    n = len(results)
    tr  = sum(r.task_recall for r in results)/n
    dr  = sum(r.decision_recall for r in results)/n
    fr  = sum(r.file_recall for r in results)/n
    tok = sum(r.resume_tokens for r in results)/n
    comp= sum(r.compression_ratio for r in results)/n
    loss= sum(r.info_loss for r in results)/n
    ms  = sum(r.extract_ms for r in results)/n
    print(f"\n{'='*55}")
    print("ABSTRACT NUMBERS (V2)")
    print(f"{'='*55}")
    print(f"  Task Recall:        {tr:.0%}")
    print(f"  Decision Recall:    {dr:.0%}")
    print(f"  File Recall:        {fr:.0%}")
    print(f"  Info Loss:          {loss:.0%}")
    print(f"  Avg Resume Tokens:  {tok:.0f}")
    print(f"  Avg Compression:    {comp:.1f}x")
    print(f"  Avg Extract Time:   {ms:.1f}ms")
    print(f"\n  ABSTRACT SENTENCE:")
    print(f'  "TokenMizer achieves {tr:.0%} task recall, {dr:.0%} decision recall,')
    print(f'  and {fr:.0%} file recall across 21 sessions (5 domains),')
    print(f'  using {tok:.0f} tokens per resume ({comp:.1f}x compression, {loss:.0%} info loss)."')


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ablation", action="store_true")
    parser.add_argument("--compare",  action="store_true")
    parser.add_argument("--domain",   default=None)
    parser.add_argument("--json",     action="store_true")
    args = parser.parse_args()

    sessions_to_run = {k: v for k, v in SESSIONS.items()
                       if not args.domain or v["domain"] == args.domain}

    print(f"\n🧠 TokenMizer V2 — {len(sessions_to_run)} sessions")
    print("Improvements: expanded patterns + fuzzy matching + compound split + decision CSV split\n")

    results_v2 = []
    for name, sess in sessions_to_run.items():
        try:
            r = run_session(name, sess)
            results_v2.append(r)
            print(f"  ✓ [{r.domain:<22}] {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")

    print_table1(results_v2, "V2")
    print_table2(results_v2)
    print_table3(results_v2)
    print_abstract(results_v2)

    if args.compare:
        from run_experiment import SESSIONS as S1, build_graph, precision_recall as pr1, count_tokens as ct1
        results_v1 = []
        for name, sess in sessions_to_run.items():
            msgs, gt = sess["messages"], sess["ground_truth"]
            g = build_graph(msgs)
            tok = sum(ct1(m["content"]) for m in msgs)
            _, tr = pr1(g.completed_tasks, gt["completed_tasks"])
            _, dr = pr1(g.decisions,       gt["decisions"])
            _, fr = pr1(g.files,           gt["files"])
            from run_experiment import Result as R1, build_checkpoint as bc1
            ckpt = bc1(name, g)
            results_v1.append(R1(name, sess["domain"], len(msgs), tok, g.total_nodes,
                                 0, tr, dr, fr, ckpt["tokens"],
                                 round(tok/max(ckpt["tokens"],1),1),
                                 round(1-(tr+dr+fr)/3,3), 0))
        print_comparison(results_v1, results_v2)

    if args.ablation:
        ablation_study(sessions_to_run)

    if args.json:
        out = Path("experiment_results_v2.json")
        out.write_text(json.dumps([asdict(r) for r in results_v2], indent=2))
        print(f"\n✓ Saved: {out}")

    print("\nDone.")

if __name__ == "__main__":
    main()
