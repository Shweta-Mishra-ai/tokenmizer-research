# TokenMizer Benchmarks

All results from the paper are reproducible with these scripts.

## Quick Start

```bash
# No installation needed — pure Python stdlib
python3 benchmarks/checkpoint_accuracy/runner_v2.py
python3 benchmarks/checkpoint_accuracy/runner_v2.py --ablation
python3 benchmarks/checkpoint_accuracy/runner_v2.py --compare
python3 benchmarks/checkpoint_accuracy/runner_v2.py --json
```

## Sessions
- 21 sessions across 5 domains
- Software Engineering (n=6), Data Science (n=5), DevOps (n=4), Research (n=3), Debugging (n=3)

## Results Files
- `results/results_v1.json` — V1 heuristic baseline
- `results/results_v2.json` — V2 improved extractor (reported in paper)
