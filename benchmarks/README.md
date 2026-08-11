# Benchmarks

Two benchmark suites are maintained in this repository. `memorybench` is
current and is the basis of the paper in `paper/`. `checkpoint_accuracy`
is the original 21-session evaluation, kept for provenance.

## `memorybench` — n=100 multi-method benchmark

Compares the TokenMizer 0.5.3 product engine against seven other memory
strategies (deterministic reimplementations of MemGPT, Mem0,
Graphiti/Zep, and GraphRAG, plus three naive baselines) on a 100-session
labelled corpus (94 generated, 6 real), using one shared scorer.

```bash
# No installation required — pure standard-library Python.
python3 -m benchmarks.memorybench.run
python3 -m benchmarks.memorybench.run --json out.json --csv out.csv
python3 -m benchmarks.memorybench.run --skip memgpt_style   # skip a method
python3 -m benchmarks.memorybench.generate -n 86            # regenerate the corpus
```

Results write-up: [`results/REPORT_n100.md`](results/REPORT_n100.md).
Interactive dashboard: [`results/dashboard.html`](results/dashboard.html).
Raw results: `results/memorybench_n100_20260811.json` and matching `.csv`.

The four "-style" methods reproduce one structural property of the named
system deterministically, with no model call — see
`benchmarks/memorybench/methods/common.py` and each method module's
docstring before quoting a result under the vendor's name. Section 1 of
`REPORT_n100.md` states precisely what these numbers do and do not
support.

## `checkpoint_accuracy` — original 21-session evaluation

The initial V1/V2 heuristic comparison. Superseded by `memorybench` as the
primary evaluation, kept here for provenance since earlier reported
figures were computed against it.

```bash
python3 benchmarks/checkpoint_accuracy/runner_v2.py
python3 benchmarks/checkpoint_accuracy/runner_v2.py --ablation
python3 benchmarks/checkpoint_accuracy/runner_v2.py --compare
python3 benchmarks/checkpoint_accuracy/runner_v2.py --json
```

- 21 sessions across 5 domains: software engineering (n=6), data science
  (n=5), DevOps (n=4), research (n=3), debugging (n=3).
- `results/results_v1.json` — V1 heuristic baseline.
- `results/results_v2.json` — V2 improved extractor.
- `results/results_v3_code-0.3.1.json` — spot check against product v0.3.1.
