# TokenMizer Benchmarks

All results from the paper are reproducible with these scripts.

## `memorybench` — n=100 multi-method benchmark (current)

The main benchmark suite: the real TokenMizer 0.5.2 engine vs. seven other
memory strategies (deterministic reimplementations of MemGPT, Mem0,
Graphiti/Zep, GraphRAG, plus three naive baselines), scored identically
against a 100-session labelled corpus (94 synthetic + the 6 real sessions
carried over from the product repo's own eval harness).

```bash
# No installation needed — pure Python stdlib
python3 -m benchmarks.memorybench.run
python3 -m benchmarks.memorybench.run --json out.json --csv out.csv
python3 -m benchmarks.memorybench.run --skip memgpt_style   # skip a method
python3 -m benchmarks.memorybench.generate -n 86            # regenerate the synthetic corpus
```

Full writeup: **[`results/REPORT_n100.md`](results/REPORT_n100.md)**.
Latest results: `results/memorybench_n100_20260810.json` (aggregates) and
`.csv` (flat, per session × method × category — filter/pivot directly).
Dashboard: `results/dashboard.html`.

Read `benchmarks/memorybench/methods/common.py` and each
`methods/*_style.py` docstring before quoting a "MemGPT" or "Mem0" number —
none of the non-TokenMizer methods call an LLM or run the actual vendor
library; each reproduces one structural property of the named strategy
deterministically. The report's §1 and §8 spell out exactly what that
does and doesn't license you to claim.

## `checkpoint_accuracy` — legacy 21-session runner (superseded)

The original V1/V2 heuristic comparison this repo shipped with. Superseded
by `memorybench` (10x the sessions, real product engine instead of an
inline reimplementation, formal CIs) but kept for history — the paper's
originally-reported numbers came from here.

```bash
python3 benchmarks/checkpoint_accuracy/runner_v2.py
python3 benchmarks/checkpoint_accuracy/runner_v2.py --ablation
python3 benchmarks/checkpoint_accuracy/runner_v2.py --compare
python3 benchmarks/checkpoint_accuracy/runner_v2.py --json
```

- 21 sessions across 5 domains: Software Engineering (n=6), Data Science
  (n=5), DevOps (n=4), Research (n=3), Debugging (n=3)
- `results/results_v1.json` — V1 heuristic baseline
- `results/results_v2.json` — V2 improved extractor (reported in paper)
- `results/results_v3_code-0.3.1.json` — spot-check against product repo v0.3.1
