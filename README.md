# TokenMizer Research

Research repository for **TokenMizer**, a graph-structured session-memory
system for long-horizon LLM context management. This repository contains
the benchmark suite, the labelled evaluation corpus, all raw results, and
the manuscript for the associated paper. The product itself is maintained
separately at
[`Shweta-Mishra-ai/tokenmizer`](https://github.com/Shweta-Mishra-ai/tokenmizer).

## Paper

**TokenMizer: Graph-Structured Session Memory for Long-Horizon LLM Context
Management** (IEEE Transactions format, journal manuscript)
Shweta Mishra, 2026.

[`paper/tokenmizer_ieee.pdf`](paper/tokenmizer_ieee.pdf) ·
[LaTeX source](paper/tokenmizer_ieee.tex)

The manuscript reports two evaluations plus a fix-and-remeasure cycle
between them: a 21-session pilot against naive truncation,
sliding-window, and summarization baselines; a controlled 100-session,
8-method comparison against deterministic reimplementations of MemGPT,
Mem0, Graphiti/Zep, and GraphRAG, with bootstrap confidence intervals
on every reported comparison; and, after that comparison identified
decision and error extraction as TokenMizer's weakest categories, a
traced-and-fixed error analysis (§XI) that closed part of the gap and
was re-measured on the identical benchmark before being reported.

### Headline results (n = 100, TokenMizer 0.5.3)

![Macro F1 by method, ranked, with 95% bootstrap confidence intervals](paper/figures/fig_n100_overall.png)

| Method | Macro F1 | 95% CI |
|---|---:|---:|
| **TokenMizer 0.5.3** | **60%** | [55%, 65%] |
| Mem0-style | 60% | [55%, 64%] |
| Graphiti-style | 59% | [55%, 64%] |
| GraphRAG-style | 44% | [41%, 48%] |
| MemGPT-style | 35% | [32%, 38%] |
| Naive truncation | 20% | [20%, 21%] |
| Sliding window (10) | 18% | [18%, 19%] |
| Naive summary | 17% | [16%, 18%] |

TokenMizer significantly outperforms GraphRAG-style, MemGPT-style, and
every naive baseline. Against Graphiti-style and Mem0-style, the
paired-difference confidence interval still crosses zero: a statistical
tie, not a win — the same conclusion as the first (0.5.2) measurement,
but the point estimate has moved from trailing both to nominally
leading both, after decision F1 improved 50%→59% and error F1 improved
36%→44% (§XI). TokenMizer's resume block (100 tokens) is smaller than
Graphiti-style's and Mem0-style's (117–119) but larger than
MemGPT-style's (60), which reaches that size by seeing under half the
conversation rather than by encoding it more efficiently. Every
pattern-matching method tested — TokenMizer included — still degrades
to 19–27% macro F1 on sessions that state facts indirectly rather than
with explicit lexical markers, essentially unmoved by the fix cycle: a
shared limitation of regex-based extraction, not a version-specific
gap, quantified here across four independently implemented strategies
on one corpus.

Four of the eight compared methods reproduce one structural property of
a published system, deterministically and with no language-model call —
they are not the vendor products. See `benchmarks/memorybench/methods/`
and the paper's Threats to Validity section (§XII) before quoting any
of these four under the named system's identity.

## Repository layout

```
paper/                    Manuscript source, figures, and compiled PDF
  tokenmizer_ieee.tex        IEEE-format manuscript (this repo's primary output)
  figures/                   Publication figures + generator script
  fig1_architecture.png,     Architecture and pilot-study figures
  fig2_graph.png, ...        (referenced by the manuscript)

benchmarks/
  memorybench/               n=100 multi-method benchmark: corpus loader,
                              scorer, synthetic-session generator, and all
                              eight method implementations
  corpus/                    100 labelled sessions (94 generated, 6 real)
  results/                   Raw results (JSON/CSV), REPORT_n100.md,
                              interactive dashboard.html
  checkpoint_accuracy/       Original 21-session pilot benchmark
```

## Reproducing the results

No installation is required; the benchmark suite is pure standard-library
Python.

```bash
git clone https://github.com/Shweta-Mishra-ai/tokenmizer-research
cd tokenmizer-research

# Run the n=100 multi-method benchmark
python -m benchmarks.memorybench.run --json out.json --csv out.csv

# Regenerate the 94-session synthetic corpus (seeded, deterministic)
python -m benchmarks.memorybench.generate -n 86

# Run the original 21-session pilot
python3 benchmarks/checkpoint_accuracy/runner_v2.py
```

Reproducing TokenMizer's own results additionally requires a checkout of
the product repository (path configurable via `TOKENMIZER_PRODUCT_REPO`,
default `/home/user/tokenmizer`); the other seven methods have no external
dependency.

Regenerating the manuscript's figures requires `matplotlib` and `numpy`;
recompiling the PDF requires a LaTeX distribution with the `IEEEtran`
class (`texlive-publishers` on Debian/Ubuntu):

```bash
pip install matplotlib numpy
python3 paper/figures/generate_figures.py
cd paper && pdflatex tokenmizer_ieee.tex && pdflatex tokenmizer_ieee.tex
```

Full methodology, per-category and per-register breakdowns, and stated
limitations: [`benchmarks/results/REPORT_n100.md`](benchmarks/results/REPORT_n100.md).
Interactive results dashboard: [`benchmarks/results/dashboard.html`](benchmarks/results/dashboard.html).

## Citation

```bibtex
@article{mishra2026tokenmizer,
  author  = {Mishra, Shweta},
  title   = {TokenMizer: Graph-Structured Session Memory for
             Long-Horizon LLM Context Management},
  year    = {2026},
  note    = {Manuscript and reproduction code available at
             \url{https://github.com/Shweta-Mishra-ai/tokenmizer-research}}
}
```

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Priority areas: real labelled
transcripts, LLM-backed variants of the comparison methods, additional
domains and threshold-sensitivity analysis.

## License

MIT License © Shweta Mishra 2026. See [`LICENSE`](LICENSE).
