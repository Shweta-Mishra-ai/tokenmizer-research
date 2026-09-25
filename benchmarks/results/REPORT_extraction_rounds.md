# Improving TokenMizer's extraction: three corpora, two rounds, one honest number

**Date:** 2026-09-24/25
**Product commits measured** (branch `claude/tokenizer-research-oqcgbg` of
`Shweta-Mishra-ai/tokenmizer`, all unreleased, `__version__` still `0.5.4`):

| Label | Commit | What it is |
|---|---|---|
| Before | `a184cf1` | product `main` as of 2026-09-23 |
| Round 2 | `9554b39` | conversational forms + precision fixes |
| Round 3 | `b6a5422` | generic gaps found on held-out v1 |

(The runner records the commit in each result JSON under `tokenmizer_product`.)

## Headline

| Corpus | Before | Round 2 | Round 3 | Paired gain, before → round 3 |
|---|---:|---:|---:|---|
| Main corpus (n=100). **Tuned against it.** | 61% | 92% | **92%** | +31.2 pt [+27.1, +35.2] |
| Held-out v1 (n=80). Read after round 2, **contaminated for round 3.** | 40% | 72% | 79% | +38.2 pt [+35.2, +41.0] |
| **Held-out v2 (n=80). Never tuned against.** | **33%** | **49%** | **51%** | **+17.4 pt [+14.6, +20.4]** |

Macro F1, 95% bootstrap CIs over sessions (3,000 resamples, seed 1729); all
three gains have P(Δ ≤ 0) < 0.001.

**The number to quote is held-out v2's: 33% → 51%.** The main corpus's 92%
is what the extractor scores on the phrasings it was developed against, and
it is not what a user with different phrasing will see. The gap between 92
and 51 is the size of that difference.

Round 3 shows why in miniature. Its fixes came from reading held-out v1's
failures. They gained +7 points on v1 and +2 on v2.

## Protocol — why each number means what it says

1. **The main corpus is the development set.** It renders each fact through
   3–4 fixed sentence templates per register. Every miss on it was
   root-caused, and the fixes target the *construction* behind a template
   ("subject + finished-state predicate") rather than the template string.
   Even so, a score on it after tuning measures fit, not generalisation.
2. **Held-out v1** (`heldout.py`, 83 templates, none shared with
   `generate.py`, plus distractor sentences that must not be extracted) was
   committed with baseline scores in `b1f57b0` *before any product change*.
   It was scored once, on round 2, with only aggregate numbers looked at
   during tuning. Its per-item failures were then read, and that ended its
   use as a held-out set.
3. **Held-out v2** (`heldout2.py`, a third disjoint template set, enforced by
   `_assert_disjoint()`) was committed with baselines at both earlier
   commits in `80acb21`, *before* round 3's fixes were written. Round 3's fix
   list was fixed before v2 was written, and nothing on it was added from
   v2's templates.

**Limits of this protocol.** All three corpora share their fact pools. The
same author wrote the fixes and both held-out sets, and knew v1's failure
list when writing v2. So v2 is an honest check against *this* author's
tuning, and a weaker one than text nobody on the project wrote. It does not
replace real labelled transcripts.

## Per category

Micro F1, before → round 3:

| Category | Main corpus | Held-out v1 | **Held-out v2** |
|---|---|---|---|
| Completed tasks | 68.6 → 92.0 | 47.4 → 69.2 | **33.3 → 52.3** |
| Pending tasks | 53.4 → 92.0 | 0.0 → 88.5 | **2.0 → 32.2** |
| Decisions | 63.9 → 97.3 | 46.7 → 87.7 | **27.1 → 53.1** |
| Files | 98.0 → 100.0 | 97.7 → 100.0 | **98.9 → 99.8** |
| Errors | 45.6 → 86.9 | 28.8 → 69.2 | **21.6 → 44.5** |

Precision on held-out v2, before → round 3: completed 87.9 → 92.8, pending
20.0 → 97.4, decisions 60.4 → 83.8, errors 19.9 → 46.2. Precision rose in
every category, and no v2 session scored lower (73 better, 7 unchanged).

By register on v2: explicit 42.9 → 56.9, semi 32.6 → 58.3, mixed
31.8 → 52.1, implicit 25.9 → 35.4.

## Against the comparison methods

| Corpus | TokenMizer − Graphiti-style | TokenMizer − Mem0-style |
|---|---|---|
| Main, before | +1.7 [−2.0, +5.4]: a tie | +1.6 [−2.1, +5.1]: a tie |
| Main, round 3 | +32.8 [+28.9, +36.6] | +32.7 [+29.1, +36.5] |
| Held-out v2, before | TokenMizer 33% vs 36%: behind | behind |
| **Held-out v2, round 3** | **+14.5 [+10.5, +18.4]** | **+14.5 [+10.5, +18.4]** |

**Read this before quoting it.** Graphiti-style and Mem0-style here are this
repository's deterministic, regex-based reimplementations of one structural
property each. They are **not** the vendor products, which extract with a
language model and would be expected to do far better on implicit phrasing
than any pattern matcher. The comparison methods also lost ~25 points moving
off the main corpus's templates, like TokenMizer did. Nothing here supports
a claim that TokenMizer beats Mem0, Zep/Graphiti or any other product, or
that it is the best system available. It supports "TokenMizer's heuristic
pass now clearly beats these reimplementations, including on unseen
phrasing".

## Cost

| | Before | Round 3 | Change |
|---|---:|---:|---|
| Extraction latency, median per session (in-process, sequential) | 15.3 ms | 18.6 ms | **+22%** |
| Extraction latency, p95 | 24.3 ms | 30.9 ms | +27% |
| Resume block, main corpus (mean tokens) | 102 | 150 | **+47%** |
| Resume block, held-out v2 | 63 | 84 | +33% |
| Compression, main corpus | 4.8× | 2.4× | halved |

The larger resume block is the direct price of carrying more facts. It
stays inside the 400-token budget the benchmark gives `to_context_block`,
but a user who measures value by compression ratio will see it fall.

Latency was measured in-process, sequentially, on both commits (`lat.py`
procedure described below). The runner's own `ms/session` column (~68 →
~230 ms) includes subprocess start-up and was inflated by concurrent runs.
Do not quote it.

On adversarial 15 KB single-token payloads, full extraction takes 0.1–0.9 s,
against 0.24–0.72 s before. That is the same complexity class: the per-match
dedup loop is quadratic in the number of matches, in the old code as in the
new. No pattern is super-linear, and one that was (an unbounded multi-dot
filename repeat, 3.5 s) was bounded before it shipped.

## What changed in the product

Full detail is in the product commits `9554b39` and `b6a5422`.

**New coverage** (`patterns.py`, "Conversational forms"):
- **Completed.** Phrasal verbs ("wrapped up X"), "got X working", subject
  plus finished-state ("X is in and working", "The PR's merged"), and
  checkboxes.
- **Pending.** To-do headers, negated completion ("haven't started X"),
  deferral ("circle back to X"), narrated intent (recent window only),
  subject plus outstanding-state ("X is next on the list"), and fronted "Up
  next is X". To-dos are now read over the whole session instead of the last
  20 messages.
- **Decisions.** User imperatives ("Use X", "Build it with X"), "should use
  X", "we'll go with X", "opting for", "I'd prefer X", and evaluative
  predicates ("X felt like the right call", "X won out"). User proposals
  count only when the next assistant turn accepts, including across
  incremental extraction calls.
- **Errors.** "Bug:/Error:/Issue:" headers, including markdown bold.
  Encounter verbs ("ran into X"). Observation verbs and "there's X", gated on
  defect vocabulary.
- **Files.** Multi-dot names (`vite.config.ts`), extensionless build files
  with their directory (`fastlane/Fastfile`), and JS library names are no
  longer taken as files (`moment.js`).
- **Graph.** A completion now merges into the pending task it finishes, so a
  task is never listed as both done and outstanding.

**Precision bugs fixed.** Each was reproduced first. Several were in code
that predates this work.
- Adjectival "failed" was read as a failure ("retry for failed deliveries").
- Labels started on a contraction's tail ("t started…") or ended mid-word
  ("…NSMotionUsageDescrip").
- Decision verbs matched inside other words: c**using**, watch**OS**
  (`chose?`), be**cause** (`use`).
- "picked up X" was read as a choice. "Logistic regression" and "soft
  deletes" were read as defects.
- Conditions were read as completions ("once X is merged we can deploy",
  "when the backfill is done…"). Pre-existing.
- A negation after a technology name was ignored ("Kafka wasn't the right
  call").
- An intransitive verb produced "Landed in in the last commit".
- `_TASK_WIP` had no word anchor, so "rewriting" matched `writing`.
  Pre-existing.

The product suite went from 1466 to 1551 tests. The new ones are in
`tests/unit/test_extraction_conversational.py`, with a negative twin for
every loose shape. The product's own eval is unchanged at 97% macro F1.

## What is still weak

The results on held-out v2, which is the honest set:
- **Pending tasks: 19% recall.** Outstanding work is phrased in more ways
  than any other category ("I still owe you X", "X keeps slipping", "X is on
  deck"), and the patterns cover a small fraction of them.
- **Errors: 45% F1, 46% precision.** The symptom-vocabulary patterns still
  claim spans inside sentences that merely mention a defect word.
- **Implicit register: 35%.** Facts stated without any marker remain out of
  reach of pattern matching, which is structural, as the paper already says.

Another round of patterns would move these numbers on whatever corpus it was
tuned against, and much less on the next one. Round 3 already showed the
diminishing return (+2 on v2). The next real gains need different evidence:

1. **Evaluate LLM extraction.** The product has an LLM extraction pass
   (`HybridExtractor.llm_extract`, merged with the heuristic pass). This
   benchmark runs the heuristic pass only, because this environment has no
   model API key. That is the path that can reach implicit phrasing.
2. **Real labelled transcripts.** Six of the 100 main-corpus sessions are
   real. More is the single most valuable addition to this repository.
3. **A held-out set written by someone else.** v1 and v2 share an author
   with the fixes.

## Reproducing

```bash
# The three corpora
python -m benchmarks.memorybench.run                                  # main corpus
python -m benchmarks.memorybench.run --corpus benchmarks/corpus_heldout
python -m benchmarks.memorybench.run --corpus benchmarks/corpus_heldout2

# Regenerate the held-out corpora (deterministic; byte-identical to the committed files)
python -m benchmarks.memorybench.heldout
python -m benchmarks.memorybench.heldout2
```

Point `TOKENMIZER_PRODUCT_REPO` at a checkout of the commit to measure.
Result files for every commit and corpus are in this directory:
`memorybench_n100_20260924*.{json,csv}`, `heldout_*.{json,csv}` and
`heldout2_*.{json,csv}`.

Latency was measured as the median of three passes per session. Each pass
timed `GraphMemory.extract_from_messages(messages, incremental=False)` on a
fresh graph, in one process, with the two commits run one after the other.
