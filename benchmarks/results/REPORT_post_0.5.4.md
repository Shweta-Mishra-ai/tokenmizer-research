# What changed in TokenMizer since 0.5.4 — n=100 re-measurement

**Date:** 2026-09-24
**Before:** TokenMizer 0.5.4 release, product commit `cd2cc90` (tag `v0.5.4`) —
the engine behind the published results in
[`memorybench_n100_20260813.*`](memorybench_n100_20260813.json) and the paper.
**After:** product `main` at `a184cf1` (2026-09-23). Unreleased: `__version__`
still reads `0.5.4`, the changes sit under `[Unreleased]` in the product
CHANGELOG. Raw results: [`memorybench_n100_20260924.*`](memorybench_n100_20260924.json).

Same 100-session corpus, same scorer, same threshold (0.6), same seed. Only
the product checkout differs. The seven comparison methods produce
identical scores in both runs, as they should: they do not depend on the
product.

**Reproduction check.** The "before" engine was re-run from `v0.5.4` for this
report and its per-session, per-category scores are identical to the
committed 2026-08-13 CSV. The delta below is therefore attributable only to
product code changes between `cd2cc90` and `a184cf1`, not to benchmark drift.

## Bottom line

TokenMizer got **slightly and measurably better**: macro F1 **60.0% → 61.3%**,
a paired gain of **+1.25 points, 95% CI [+0.46, +2.12]** (3,000 bootstrap
resamples over sessions, seed 1729; P(Δ ≤ 0) = 0.001). The improvement is
real, but it is small: 26 sessions improved, 68 were unchanged, 6 got worse.

It does **not** change the headline conclusion of the paper. TokenMizer is
still a statistical tie with Graphiti-style and Mem0-style (both CIs still
cross zero), and still clearly ahead of GraphRAG-style, MemGPT-style and the
naive baselines.

| | 0.5.4 (`cd2cc90`) | main (`a184cf1`) | Change |
|---|---:|---:|---:|
| Macro F1 | 60.0% [55, 65] | **61.3%** [56, 66] | **+1.25 pt** [+0.46, +2.12] |
| vs Graphiti-style (paired Δ) | +0.4% [−3.3, +4.2] | +1.7% [−2.0, +5.4] | still a tie |
| vs Mem0-style (paired Δ) | +0.3% [−3.4, +3.8] | +1.6% [−2.1, +5.1] | still a tie |
| vs GraphRAG-style | +15.6% | +16.8% | significant win, both |
| vs MemGPT-style | +24.6% | +25.9% | significant win, both |
| Resume block (mean tokens) | 100.3 | 102.1 | +1.8 tokens |
| Extraction latency (median ms/session) | 44.6 | 67.8 | **+52% slower** |

## Where the gain came from — per category (micro, summed over 100 sessions)

| Category | Precision | Recall | F1 | True positives |
|---|---|---|---|---|
| **Decisions** | 73.5 → **78.0** | 49.3 → **54.1** | 59.0 → **63.9** (+4.9) | 175 → 192 of 355 |
| Errors | 57.0 → 55.9 (↓) | 35.8 → 38.5 | 44.0 → 45.6 (+1.6) | 53 → 57 of 148 |
| Completed tasks | 96.6 → 96.7 | 52.1 → 53.2 | 67.7 → 68.6 (+0.9) | 256 → 261 of 491 |
| Pending tasks | 94.3 | 37.2 | 53.4 (unchanged) | 83 of 223 |
| Files | 98.0 | 98.0 | 98.0 (unchanged) | 395 of 403 |

- **Decisions carry almost the whole improvement**, and they improved on both
  precision and recall. This is consistent with the product CHANGELOG's
  "Improved — decision and error extraction" entry (superseded-dependency
  names with `/` and `@`, "should use/adopt X" as adoption, Pass 4 given the
  Pass 3 context gate).
- **Errors gained 4 true positives but added 9 extractions**, so precision
  fell. The new "plain failure verb" pattern widened recall at a cost (see
  regressions below).
- **Decisions are now level with Graphiti/Mem0-style (64% vs 65%).** At
  0.5.4 they were 6 points behind. This was one of the paper's two named
  weaknesses; it is now essentially closed.
- **Errors remain the weak spot: 46% vs 66%** for Graphiti/Mem0-style. That
  gap narrowed by only ~1.6 points. The paper's other named weakness is
  still open.
- Pending tasks did not move at all (37% recall).

## By register (macro F1)

| Register | n | 0.5.4 | main |
|---|---:|---:|---:|
| explicit | 22 | 73.7% | 75.7% |
| implicit | 21 | 26.8% | 28.5% |
| mixed | 21 | 57.6% | 58.2% |
| semi | 22 | 58.3% | 58.6% |
| unspecified (incl. real) | 14 | 93.6% | 95.4% |

Implicit-register sessions — facts stated without lexical markers — moved
by under 2 points. The paper's "every pattern-matching method collapses on
implicit text" finding stands unchanged. Nothing in these commits was aimed
at it, and none of the changes is architectural.

## Regressions — root-caused

> **Update, 2026-09-25:** both defects below are fixed in product commit
> `9554b39` (adjectival "failed" and the contraction-tail label), with
> tests. See [`REPORT_extraction_rounds.md`](REPORT_extraction_rounds.md)
> for the follow-up work and its measurement on held-out phrasing.

Six sessions scored lower. The two large ones share one cause, and it is a
**product bug** introduced by the new error patterns, not benchmark noise:

| Session | Δ macro F1 | Extracted as an "error" | Source text |
|---|---:|---|---|
| `gen_backend_python_003` | −17.0 | `background retry for failed webhook deliveries` | "Done: background retry for failed webhook deliveries" (a *completed task*) |
| `gen_devops_ci_003` | −11.5 | `t started a rollback job for failed deploys yet` | "Haven't started a rollback job for failed deploys yet" (a *pending task*) |

Neither session has any labelled error. The new error category with F1 = 0
therefore pulls both sessions' macro F1 down.

**Cause.** `_ERROR_FAILED_SUBJECT` in `tokenmizer/graph_memory/patterns.py`
(added in product commit `ef04703`, after 0.5.4) matches `<subject> failed <rest>`, and it
cannot tell the verb ("the deploy failed") from the adjective ("retry for
failed deliveries"). Reproduced directly against the pattern:

```
"We still need a background retry for failed webhook deliveries."
  -> ['We still need a background retry for failed webhook deliveries']
"We haven't started a rollback job for failed deploys yet."
  -> ['t started a rollback job for failed deploys yet']
"Deploy failed, rolled back"
  -> ['Deploy failed']          # the intended case
```

**A second, smaller defect is visible in the same output.** The subject run
`[\w./\- ]{1,40}` does not include an apostrophe. A subject that follows a
contraction therefore starts mid-word: `t started …` from "Haven't started …".
The pattern's own comment says `_drop_leading_sentence` cleans this up, but
it did not here.

Suggested fix, for the product repo (not applied here, since this
repository measures the product and does not modify it): reject a match
when `failed` is directly preceded by a preposition or determiner (`for`,
`of`, `on`, `the`, `a`, `all`, `any`, `retry`/`retries`), or when it is
followed by a plural noun with no verb after it. Also add `'` to the
subject run, or trim a leading single-letter fragment. Both sentences above
belong in `tests/unit/test_extraction_generalisation.py` as negative
cases.

The remaining four regressions are small (−4.0 to −1.3 points) and were
not individually investigated.

## Cost side

- **Extraction is ~52% slower**: median 44.6 → 67.8 ms per session. At these
  absolute values that is still negligible next to an LLM call. It is
  reported because it is a real regression and was not mentioned in the
  CHANGELOG.
- The resume block grew by ~2 tokens on average (100 → 102). Compression is
  4.8× instead of 5.0×.

## What this report does not claim

- **The product CHANGELOG's own numbers are not comparable to these.** Figures
  such as "macro F1 96%, decisions 97%" come from the product's internal
  `benchmarks/eval` corpus, on which the patterns were developed. This
  independent 100-session corpus measures 61%. Neither number is wrong. The
  gap between them is the size of the generalisation problem.
- Most of the other `[Unreleased]` work — the output-trimmer fix, message
  hashing, load handling, memory bounds, retrieval, the graph UI and MCP
  changes — is not exercised by this benchmark. This benchmark scores
  extraction into a resume block only. "No change here" does not mean
  "those changes did nothing".
- The comparison methods are deterministic reimplementations, not vendor
  products. See the paper's Threats to Validity section.

## Why the paper was not updated

The manuscript evaluates the **released** 0.5.4. Current `main` is
unreleased and still reports `__version__ = "0.5.4"`. Swapping the paper's
numbers to an unreleased commit under the same version string would make
the paper describe software nobody can install. When the next release is
tagged, re-run with:

```bash
TOKENMIZER_PRODUCT_REPO=/path/to/tokenmizer \
  python -m benchmarks.memorybench.run --json out.json --csv out.csv
```

and update the manuscript from that run. The JSON now records the exact
product commit it measured (`tokenmizer_product`). The 2026-08-13 run did
not record it, so its commit had to be reconstructed for this report.

## Known cosmetic issue

The TokenMizer method key is still `tokenmizer_v0.5.2` in the benchmark
code, the results files and the CI `--skip` flag, for all runs, including
this one. It is a stable identifier, not a version claim. The measured
version is in `tokenmizer_product`. It has been left alone so that result
files stay comparable across runs.
