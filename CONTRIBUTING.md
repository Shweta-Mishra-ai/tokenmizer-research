# Contributing

This repository holds the benchmark suite, evaluation corpus, and published
results for TokenMizer. It does not contain the product — that is
[`Shweta-Mishra-ai/tokenmizer`](https://github.com/Shweta-Mishra-ai/tokenmizer).
Contributions here should improve the evaluation itself: more sessions,
more comparison methods, better statistics, or corrections to the analysis.

## Priority areas

1. **Real transcripts.** The corpus is 94 generated sessions and 6 real
   ones. Every additional real, hand-labelled session strengthens the
   `origin: real` split reported throughout the benchmark.
2. **LLM-backed comparison methods.** `benchmarks/memorybench/methods/`
   currently reimplements MemGPT, Mem0, Graphiti, and GraphRAG
   deterministically, with no model call (see the limitations section of
   `benchmarks/results/REPORT_n100.md`). An LLM-backed extraction pass for
   any of these, gated behind an API key, would answer the open question
   the current results leave unresolved.
3. **Additional domains or registers.** `benchmarks/memorybench/domains.py`
   holds the fact pools the generator samples from; new domain packs are
   dropped in the same format.
4. **Threshold and statistical sensitivity.** The benchmark reports one
   match threshold (0.6) and one bootstrap configuration. A `--sweep`
   analysis across thresholds, run against the n=100 corpus, is not yet
   in the repository.

## Adding a labelled session

Add a JSON file to `benchmarks/corpus/` in this format:

```json
{
  "id": "your_session_id",
  "origin": "real",
  "domain": "backend/python",
  "register": "semi",
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "ground_truth": {
    "completed_tasks": ["..."],
    "pending_tasks": ["..."],
    "decisions": ["..."],
    "files": ["..."],
    "errors": ["..."]
  }
}
```

Every ground-truth label must be recoverable from a single message in the
transcript — the harness enforces this and refuses to score a corpus that
fails it:

```bash
python3 -c "
from benchmarks.memorybench import corpus
sessions = corpus.load()
corpus.validate_grounding(sessions)
print(corpus.describe(sessions))
"
```

Then re-run the benchmark to confirm it scores as expected:

```bash
python -m benchmarks.memorybench.run
```

## Adding a comparison method

Add a module to `benchmarks/memorybench/methods/` exposing
`NAME`, `DESCRIPTION`, and `extract(session) -> MethodResult` (see
`methods/common.py`), then register it in `methods/__init__.py`. If the
method reproduces a published system's strategy rather than calling that
system directly, say so in the module docstring — this is the standard
the four existing "-style" methods follow, and it is load-bearing for how
the results are allowed to be read.

## Setup

No installation is required. The benchmark suite is pure standard-library
Python:

```bash
git clone https://github.com/Shweta-Mishra-ai/tokenmizer-research
cd tokenmizer-research
python -m benchmarks.memorybench.run
```

`matplotlib` and `numpy` are only needed to regenerate the figures in
`paper/figures/`. A LaTeX distribution with the `IEEEtran` class
(`texlive-publishers` on Debian/Ubuntu) is only needed to rebuild the
paper PDF.
