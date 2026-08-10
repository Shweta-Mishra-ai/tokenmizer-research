# TokenMizer vs. graph-memory methods — n=100 benchmark

**Date:** 2026-08-10
**Corpus:** `benchmarks/corpus/` — 100 sessions (94 synthetic, 6 real), 2,516 turns, 1,620 labelled ground-truth items, 23 domains
**Harness:** `benchmarks/memorybench/` (this repo)
**Raw results:** `benchmarks/results/memorybench_n100_20260810.json` (full), `.csv` (flat, per session × method × category)
**Reproduce:** `python -m benchmarks.memorybench.run --json out.json --csv out.csv`

---

## 1. What this measures, and what it doesn't

Eight methods are scored against the same 100-session corpus with the same asymmetric coverage scorer (`benchmarks/memorybench/metrics.py`, ported from the product repo's eval harness): a ground-truth item is "found" when some extracted string covers ≥60% of its tokens (or contains it verbatim), and precision is the same relation reversed. No embeddings, no LLM judge — deterministic and re-runnable.

**TokenMizer** (`tokenmizer_v0.5.2`) is the actual product engine — `GraphMemory.extract_from_messages()` + `HybridExtractor`'s heuristic pass, run out-of-process against a real checkout of the product repo so its package can't be shadowed by this repo's own (older, separate) `tokenmizer/` directory.

The other seven are **not** the named vendor libraries. MemGPT, Mem0, Graphiti and GraphRAG all do their real extraction with an LLM call, and this benchmark runs with no API key and no network dependency on a provider — that was an explicit scope decision (see the two `AskUserQuestion` answers this run was built under: generate a synthetic corpus rather than wait on labelling, and reimplement strategies deterministically rather than require a key). What's reproduced for each is the *structural property the strategy is known for*, using the same shared regex family so a score difference reflects strategy, not regex quality:

| Method | Structural property reproduced | Source |
|---|---|---|
| `memgpt_style` | Core/archival paging — only the most recent ~40% of turns are visible; nothing recalls older facts without a query | Packer et al. 2023 |
| `mem0_style` | Flat undifferentiated fact store, whole transcript, last-write-wins dedup, no typed relationships | Chhikara et al. 2025 |
| `graphiti_style` | Bi-temporal graph — facts are never deleted, only marked superseded | Rasmussen et al. 2024 (Zep/Graphiti) |
| `graphrag_style` | Entity/community graph — strong on named entities (files, tech), no task-lifecycle concept at all | Edge et al. 2024 |
| `sliding_window_10`, `naive_truncation`, `naive_summary` | No extraction — raw kept text, scored as one untyped bag against every category | — |

Every module's docstring repeats this; treat every "-style" row as a lower bound on what the real, LLM-backed system would do — these are the floor a deterministic approximation gets to, not a ceiling on the actual product.

---

## 2. Headline result

| Method | Macro F1 | 95% CI | Resume tokens | Compression | ms/session |
|---|---:|---:|---:|---:|---:|
| **tokenmizer_v0.5.2** | **57%** | [52%, 62%] | 99 | 5.1× | 38.0 |
| graphiti_style | 59% | [55%, 64%] | 120 | 4.6× | 0.9 |
| mem0_style | 60% | [55%, 64%] | 118 | 4.7× | 0.9 |
| graphrag_style | 44% | [41%, 48%] | 80 | 5.8× | 0.5 |
| memgpt_style | 35% | [32%, 38%] | 60 | 11.1× | 0.4 |
| sliding_window_10 | 18% | [18%, 19%] | 150 | 2.5× | 0.0 |
| naive_truncation | 20% | [20%, 21%] | 287 | 1.2× | 0.0 |
| naive_summary | 17% | [16%, 18%] | 186 | 1.9× | 0.0 |

**Paired bootstrap, TokenMizer vs. each method** (3,000 resamples, positive = TokenMizer ahead):

| Comparison | Mean Δ | 95% CI | P(Δ≤0) |
|---|---:|---:|---:|
| vs. graphiti_style | −2.7% | [−6.4%, +1.0%] | 91.2% |
| vs. mem0_style | −2.8% | [−6.4%, +1.2%] | 91.7% |
| vs. graphrag_style | +12.5% | [+8.8%, +16.1%] | 0.0% |
| vs. memgpt_style | +21.6% | [+18.3%, +25.0%] | 0.0% |
| vs. sliding_window_10 | +38.4% | [+34.1%, +42.8%] | 0.0% |
| vs. naive_truncation | +36.3% | [+31.9%, +40.7%] | 0.0% |
| vs. naive_summary | +40.1% | [+35.7%, +44.2%] | 0.0% |

**Reading it straight:** TokenMizer clearly and significantly beats every naive baseline and both non-graph strategies (GraphRAG-style, MemGPT-style). It is **not** distinguishable from `graphiti_style` or `mem0_style` at this sample size and threshold — the 95% CI on the difference straddles zero for both (P(Δ≤0) ≈ 91%, i.e. a coin-flip-adjacent result, not a win). TokenMizer wins on resume-token footprint (99 tokens vs. 118–120) but not on recall against these two.

This is a real, checkable finding, not a hedge: at n=21 in the original product README, TokenMizer's V2 engine reported 51/47/59% task/decision/file recall against three much weaker baselines (naive truncation, sliding window, naive summary) — a comparison this benchmark reproduces directionally (TokenMizer beats all three naive baselines by 36–40 points here too). What n=21 never tested is a graph-memory method built to solve the same problem. At n=100 against `graphiti_style` and `mem0_style`, that gap closes to statistical noise.

---

## 3. Per-category breakdown (micro F1, all 100 sessions)

| Method | completed | pending | decisions | files | errors |
|---|---:|---:|---:|---:|---:|
| tokenmizer_v0.5.2 | 68% | 53% | 50% | **98%** | 36% |
| graphiti_style | 64% | 43% | **65%** | 89% | **66%** |
| mem0_style | 64% | 45% | **65%** | 89% | **66%** |
| graphrag_style | 28% | 16% | 70% | 89% | 46% |
| memgpt_style | 42% | 28% | 34% | 59% | 37% |
| baselines | 22–29% | 12–15% | 18–25% | 21–25% | 10–11% |

TokenMizer's file-extraction is essentially solved (98% F1, best of any method) and its completed-task recall leads the graph methods. Its two weak categories are **decisions** (50% vs. 65% for graphiti/mem0-style) and **errors** (36% vs. 66%). The raw counts explain why:

- **Decisions:** 355 expected, 274 extracted, but only 118 of those extractions are spurious *matches-to-nothing* — precision is 57%, well below graphiti/mem0-style's implied precision on the same recall level. TokenMizer's decision patterns appear to be firing on non-decision sentences at a meaningfully higher rate than the reimplemented graph methods, on this corpus.
- **Errors:** 148 expected, only 79 extracted (recall 28%), and of those, 39 are spurious. This is the method's worst category by a wide margin and the clearest concrete lead for engineering follow-up — the product repo's error-pattern coverage looks materially behind its decision and completed-task patterns.

Both are visible directly in `memorybench_n100_20260810.csv` per session, filterable to `method=tokenmizer_v0.5.2 AND category=errors` for the exact missed/spurious sessions.

---

## 4. Register breakdown — the corpus's central design choice

Every generated session is tagged `explicit`, `semi`, `implicit`, or `mixed`, recording how directly it states its facts. All labels are grounded (substring-verifiable) regardless of register — what varies is whether a pattern-matcher's trigger words ("Completed:", "Decided:") are present, or whether the same fact arrives inside a hedge or a subordinate clause.

| Method | explicit | semi | mixed | implicit |
|---|---:|---:|---:|---:|
| tokenmizer_v0.5.2 | 71% | 52% | 55% | **25%** |
| graphiti_style / mem0_style | 85% | 68% | 63% | 19% |
| graphrag_style | 69% | 37% | 47% | 19% |
| memgpt_style | 46% | 39% | 36% | 10% |
| baselines | 16–19% | 15–17% | 18–20% | 14–19% |

Every pattern-based method — including TokenMizer — collapses on implicit text: all four regex-driven methods land in a narrow 19–25% band once the marker words disappear, a >45-point drop from their explicit-register score. This is not a new finding; it is the exact limitation the product README already names ("Implicit conversational assertions... escape traditional trigger matching"), now quantified across 4 methods and confirmed to be a shared ceiling of the *entire pattern-matching approach*, not a TokenMizer-specific gap. Only an LLM-in-the-loop extraction pass — which none of these methods run here — would be expected to move this number, and that is untested by this benchmark on principle (see §1).

---

## 5. Origin breakdown — synthetic vs. real transcripts

| Method | real (n=6) | synthetic (n=94) |
|---|---:|---:|
| tokenmizer_v0.5.2 | **91%** | 55% |
| graphiti_style / mem0_style | 58% | 60% |
| graphrag_style | 52% | 44% |
| memgpt_style | 47% | 34% |

TokenMizer's 91% on the 6 real sessions (captured audit transcripts, carried over unchanged from the product repo's own eval corpus) is the one place it clearly leads every other method — and the one place sample size is smallest (n=6, no CI reported per-method here because the harness only bootstraps the pooled macro F1, not this slice; treat 91% as directional). It's consistent with those patterns having been iterated against exactly this kind of transcript. The synthetic majority (n=94), built from scratch for this run and never seen by any method's pattern set, is where the graphiti/mem0-style tie shows up. Whichever number is more representative of a real deployment is an open question this benchmark doesn't resolve — it's why both splits are reported separately rather than folded into one aggregate.

---

## 6. Domain variance

Domain-level macro F1 for TokenMizer ranges from 20% (`devops/kubernetes`) to 100% (`audit/python`, `audit/security`, `audit/systems` — the real-transcript domains). The weakest synthetic domains are infra/networking-flavored: `devops/kubernetes` (20%), `infra/terraform` (21%), `data/streaming` (25%) — plausibly because those domains' decision and error vocabulary (Helm charts, IAM roles, Kafka partitions) diverges further from whatever the product patterns were tuned against than backend/API vocabulary does. `frontend/typescript` and `audit/nlp` land at 96% and 89% respectively. Full per-domain numbers for every method are in the JSON's `macro_f1_by_domain`.

---

## 7. Cost picture

TokenMizer is ~40–80× slower per session than any of the reimplemented methods (38ms vs. 0.4–0.9ms) because it runs a real subprocess launching the actual product package per session, not because the underlying algorithm is inherently heavier — the reimplementations are plain in-process regex over already-loaded text. This number should not be read as "TokenMizer is slow"; it's dominated by Python interpreter startup once per session, an artifact of the isolation strategy in §1, not the extraction algorithm itself.

---

## 8. Limitations

1. **Reimplementations are a floor, not the products.** Every non-TokenMizer graph method here is a deterministic approximation of a published strategy with no LLM call. Real Mem0/Graphiti/MemGPT/GraphRAG deployments use an LLM for extraction and would very plausibly score higher, particularly on implicit-register text where every method here caps near 20%. This benchmark answers "how do these structural strategies compare on identical inputs with identical regex quality," not "how do the actual products compare."
2. **94 of 100 sessions are synthetic**, generated by `benchmarks/memorybench/generate.py` from domain fact-pools for this run specifically (seed `20260810`, fully reproducible). They are grounded (every label is a verbatim substring of some message) but they are not captured transcripts — the report keeps the synthetic/real split visible throughout for exactly this reason (§5).
3. **Match threshold (0.6) and bootstrap settings are choices**, not neutral facts — the harness's `--sweep`-equivalent hasn't been run for this corpus (unlike the product repo's own eval harness, which ships one). A stricter or looser threshold could plausibly move the TokenMizer/graphiti-style/mem0-style ordering, which is already inside noise at 0.6.
4. **No cross-session memory tested.** Every method here processes one session's full transcript in one pass. None of the "-style" methods' actual multi-session consolidation behavior (Mem0's cross-conversation fact merging, Graphiti's graph growing over weeks) is exercised — this is a single-session extraction benchmark only.
5. **Domain and register cells get thin fast.** 23 domains × ~4 registers over 100 sessions means many cells in §4/§6 rest on single-digit session counts; the CIs reported are only for the pooled macro F1, not these slices.

---

## 9. Where this leaves the product claim

The product README's line — TokenMizer beats naive truncation/sliding-window/naive-summary baselines — holds up at n=100 with a wider corpus and a formal CI (§2). The claim this benchmark does **not** support, and that nothing before it tested, is superiority over other graph/structured-memory approaches: against `graphiti_style` and `mem0_style` specifically, the honest read is a statistical tie with a token-budget edge, not a win. The concrete, actionable finding is §3: TokenMizer's decision-extraction precision and error-extraction recall are its two weakest and most improvable categories relative to its own file/completed-task performance, and relative to the graph-method peer group.
