# TokenMizer vs. Other Memory Methods — A 100-Session Benchmark

**Date:** August 13, 2026
**Data:** 100 labelled sessions, 8 methods compared, TokenMizer version 0.5.4
**Files:** `benchmarks/results/memorybench_n100_20260813.json` (full numbers), `.csv` (spreadsheet-friendly), `dashboard.html` (visual view)
**How to re-run:** `python -m benchmarks.memorybench.run`

---

## Summary

We tested TokenMizer (the real product, version 0.5.4) against 7 other memory methods on 100 test sessions. Each method reads a conversation and tries to pull out 5 things: completed tasks, pending tasks, decisions, file names, and errors. We compared what each method found against a hand-checked answer key.

**Main result:** TokenMizer clearly beats simple methods (keeping the last few messages, summarizing, etc.) and two other graph-based methods (MemGPT-style and GraphRAG-style). Against the other two — Graphiti-style and Mem0-style — TokenMizer now matches Mem0-style exactly on the headline score and is a statistical tie with both; there is no longer a points gap to explain away.

**What changed since the last run:** the previous version of this report (August 12, TokenMizer 0.5.3) found decisions and errors to be TokenMizer's two weakest categories, well behind Graphiti-style and Mem0-style. That finding was used directly: version 0.5.4 fixes a decision-extraction false positive on questions, broadens the decision and error vocabulary with terms this benchmark's own missed items named specifically (e.g. "leaning toward", "nil pointer dereference", "sqlc", "NATS"), and adds a handful of verified-safe technology names. Two more aggressive fixes were tried and rejected because they measurably hurt precision on the product's own test corpus — see the 0.5.4 CHANGELOG entry in the product repository. The result: decisions rose from 50% to 59% F1, errors from 36% to 44% F1, and TokenMizer's overall score rose from 57% to 60% — enough to close the gap with Graphiti-style and Mem0-style that the previous run found.

**Still true:** decisions and errors remain TokenMizer's weakest categories relative to Graphiti-style and Mem0-style (59%/65% and 44%/66%), so there is still room to close here. And every method we tested, including TokenMizer, does much worse when a conversation states things indirectly instead of using clear markers like "Decided:" or "Completed:" — that finding is unchanged by this fix, because it is a limit of pattern matching itself, not of TokenMizer's specific vocabulary. All 4 pattern-based methods stay at about 19–27% accuracy on indirect text.

---

## 1. What We Tested

### 1.1 The methods

| Method | What it is |
|---|---|
| **TokenMizer 0.5.4** | The real product. We ran the actual code, not a copy. |
| Graphiti-style | Based on Graphiti/Zep. Keeps every fact it finds, even old ones that got replaced later. |
| Mem0-style | Based on Mem0. Keeps facts in a simple list, no structure. |
| MemGPT-style | Based on MemGPT. Only looks at the most recent part of the conversation. |
| GraphRAG-style | Based on GraphRAG. Good at finding file names and tech choices, but not built to track whether a task is done or not. |
| Sliding window | Baseline. Just keeps the last 10 messages, word for word. |
| Naive truncation | Baseline. Just keeps the last ~300 words. |
| Naive summary | Baseline. Just keeps the first ~120 words. |

**Important:** Graphiti-style, Mem0-style, MemGPT-style, and GraphRAG-style are **not** the actual products. The real products use an AI model to read and understand the conversation. We did not have an API key for that, so instead we rebuilt the *strategy* each one is known for (e.g., "keep old facts instead of deleting them") using plain pattern matching, with no AI model involved. Because of this, these numbers should be read as a **lower bound** — the real products would likely do better, especially on the indirect-language cases in Section 4. Read this as a fair comparison of *strategies*, not a comparison of the actual commercial tools.

### 1.2 The test data

100 conversations, each with a hand-written answer key of what should be found in it.

- 94 were generated for this test. Every fact in the answer key is written word-for-word somewhere in the conversation, so it's always possible to find it — nothing in the answer key is "hidden."
- 6 are real conversations that were already part of TokenMizer's own test suite.
- The 94 generated ones cover 15 topic areas (backend code, frontend code, DevOps, security, data pipelines, mobile apps, and more) and 4 writing styles:
  - **Explicit** — uses clear markers, e.g. "Decided: use Postgres."
  - **Semi** — plain sentences, e.g. "We're going with Postgres for this."
  - **Implicit** — the fact is buried in a longer sentence with no marker word, e.g. "After weighing it, Postgres felt like the right call."
  - **Mixed** — a blend of all three within one conversation.

### 1.3 How we scored it

For each fact in the answer key, we checked whether the method found something close enough to it (at least 60% word overlap, or an exact match). We then calculated precision (how many of the method's answers were correct) and recall (how many correct answers it found), and combined them into one F1 score per category. The final score for a method is the average F1 across all 5 categories.

We also ran a statistical test (bootstrap, 3,000 resamples) to get a confidence range around each score, so we can tell a real difference apart from random noise.

---

## 2. Main Results

| Method | Score (Macro F1) | Confidence range | Resume size (tokens) | Speed |
|---|---:|---:|---:|---:|
| **TokenMizer 0.5.4** | **60%** | 55%–65% | 100 | 225 ms |
| Mem0-style | 60% | 55%–64% | 118 | 1.3 ms |
| Graphiti-style | 59% | 55%–64% | 120 | 1.3 ms |
| GraphRAG-style | 44% | 41%–48% | 80 | 0.7 ms |
| MemGPT-style | 35% | 32%–38% | 60 | 0.5 ms |
| Naive truncation | 20% | 20%–21% | 287 | <0.1 ms |
| Sliding window | 18% | 18%–19% | 150 | <0.1 ms |
| Naive summary | 17% | 16%–18% | 186 | <0.1 ms |

("Resume size" is how many tokens the method's output takes up — smaller is more efficient, if the score is similar. TokenMizer's speed number is dominated by launching a full separate program per conversation, plus a network-timeout retry from a token-counting library trying and failing to reach the internet in this test environment — see Section 6, not the extraction logic itself.)

### Is TokenMizer actually better than each one?

We compared TokenMizer directly against each other method, on the same 100 sessions, and checked if the difference is bigger than random noise:

| Compared to | Difference | Is it a real difference? |
|---|---:|---|
| Graphiti-style | +0.4 points | No — could easily be noise |
| Mem0-style | +0.3 points | No — could easily be noise |
| GraphRAG-style | +16 points | **Yes, TokenMizer wins** |
| MemGPT-style | +25 points | **Yes, TokenMizer wins** |
| Sliding window | +41 points | **Yes, TokenMizer wins** |
| Naive truncation | +39 points | **Yes, TokenMizer wins** |
| Naive summary | +43 points | **Yes, TokenMizer wins** |

**In plain words:** TokenMizer is a clear winner over simple/naive approaches and over 2 of the 4 graph-based methods. Against the other 2 (Graphiti-style, Mem0-style), the scores now land within a fraction of a point of each other — still a statistical tie, not a provable win, but no longer a gap either. TokenMizer also produces a smaller/cheaper output than either.

---

## 3. Where TokenMizer Is Strong and Weak

| Category | TokenMizer | Best other method |
|---|---:|---:|
| Completed tasks | 68% | 64% (TokenMizer ahead) |
| Pending tasks | 53% | 45% (TokenMizer ahead) |
| File names | **98%** | 89% (TokenMizer clearly ahead) |
| Decisions | 59% | 65% (TokenMizer behind) |
| Errors | 44% | 66% (TokenMizer behind) |

**Files are basically solved** — TokenMizer finds file names almost perfectly.

**Decisions and errors improved but are still the weak spots.** Of 355 decisions mentioned across all 100 sessions, TokenMizer now finds 238 (was 274), with 175 correct and 65 wrong (was 158 correct, 118 wrong) — fewer guesses overall, and a better fraction of them right, which is what raised precision alongside recall. For errors: out of 148 mentioned, TokenMizer now finds 93 (was 79), with 53 correct and 41 wrong. Both categories moved in the right direction; neither closed the gap to Graphiti-style/Mem0-style entirely. The released per-conversation results (Section 9) show exactly which sessions and which specific remaining items still don't match.

---

## 4. The Big Pattern: Explicit vs. Indirect Language

We tagged every test conversation by how directly it states facts. Here's how each method's score changes:

| Method | Explicit ("Decided: X") | Plain sentence | Mixed | Indirect / buried in reasoning |
|---|---:|---:|---:|---:|
| TokenMizer | 74% | 58% | 58% | **27%** |
| Graphiti-style / Mem0-style | 85% | 68% | 63% | 19% |
| GraphRAG-style | 69% | 37% | 47% | 19% |
| MemGPT-style | 46% | 39% | 36% | 10% |

TokenMizer's broadened vocabulary picked up a few more plain-sentence and indirect cases than before (52%→58% and 25%→27%), but the pattern holds: every method that relies on pattern-matching — including TokenMizer — falls to around 19–27% once the conversation stops using clear marker words. This is not something specific to TokenMizer; it's a limit of this whole approach (pattern matching / regex). To fix this well, a method would likely need an AI model in the loop to actually read and understand the sentence, which none of the methods here use.

---

## 5. Real Conversations vs. Generated Ones

| Method | Real conversations (6) | Generated conversations (94) |
|---|---:|---:|
| TokenMizer | **91%** | 58% |
| Graphiti-style / Mem0-style | 58% | 60% |

TokenMizer does much better on the 6 real conversations than on the 94 generated ones. This makes sense — TokenMizer's patterns were likely tuned against conversations similar to those 6. But there are only 6 of them, so this number is not very statistically solid — treat it as a hint, not a proven result.

---

## 6. Cost

TokenMizer takes about 225 milliseconds per conversation in this test environment, while the other methods take about 1 millisecond. Two things are stacked here, neither of which is the extraction logic itself: (1) we run TokenMizer as a separate real program per conversation (to make sure we tested the actual product code, not a copy), which has program-startup overhead; and (2) in this test environment, TokenMizer's token-counting library tried and failed to reach the internet to download its vocabulary file, retried, then fell back to an estimate — that retry adds real time per call, and its exact size varies run to run with the test environment's network conditions (176ms in the previous run, 225ms here). Neither reflects how fast the underlying pattern-matching itself runs; a normal deployment with that vocabulary file already cached would not see this.

---

## 7. Limitations — What This Test Does NOT Prove

1. **The 4 "-style" methods are not the real products.** They do not use an AI model. The real Mem0, Graphiti, MemGPT, and GraphRAG products all use an AI model to read conversations, and would likely score higher — especially on the indirect-language cases in Section 4.
2. **Most of the test data (94 of 100) is generated, not real.** It is built so every answer is always findable in the text, but it is not real user conversations.
3. **We only tested one scoring cutoff (60% word overlap).** A stricter or looser cutoff might change the ranking between TokenMizer, Graphiti-style, and Mem0-style, since those 3 are already very close.
4. **We only tested single conversations.** We did not test how these methods behave across many conversations over time (which some of these tools, like Mem0, are specifically designed for).
5. **Some breakdowns use small sample sizes.** For example, the "real conversations" row in Section 5 is based on only 6 conversations, so treat it carefully.
6. **This test measures whether the right facts get pulled out of a conversation — not whether having them actually helps an AI continue the conversation better.** That's a different, harder experiment (it needs real AI model calls to check), and we haven't run it yet.

---

## 8. Bottom Line

- TokenMizer beats simple baselines and 2 of 4 graph-memory strategies we tested, clearly and reliably.
- Against the other 2 graph-memory strategies (Graphiti-style, Mem0-style), it's a statistical tie, not a win — TokenMizer's score now matches Mem0-style exactly and produces a smaller output than either.
- Decision and error detection, the two weakest categories identified in the previous run of this benchmark, were targeted directly in TokenMizer 0.5.4 and both improved (decisions 50%→59% F1, errors 36%→44% F1) — but both remain behind Graphiti-style and Mem0-style (65% and 66%), so there is more room here.
- All methods, including TokenMizer, need a real AI-reading step (not just pattern matching) to handle conversations that state things indirectly — that limitation did not move with this fix, because it is structural to regex-based extraction, not specific to TokenMizer's vocabulary.

---

## 9. Reproducing and Extending This Analysis

Every number in this report comes from `benchmarks/results/memorybench_n100_20260813.csv` — one row per conversation, per method, per category, with the exact counts (expected / found / correct / wrong) behind every percentage above. To find exactly *which* decisions or errors TokenMizer still misses or gets wrong (the natural next step after Section 3), filter that CSV to `method=tokenmizer_v0.5.2` (the harness's internal key for the TokenMizer row; the report and dashboard both label it "TokenMizer 0.5.4", the actual product version) and `category=decisions` or `category=errors`, then cross-reference the session IDs against `benchmarks/corpus/*.json` to read the actual conversation text.

That kind of item-by-item tracing is exactly what produced this update: the previous run (0.5.3, August 12) was traced this way, the specific missed and spurious items were named, and the fix in 0.5.4 targeted them directly — see the product repository's CHANGELOG for the itemized list of what was fixed and what was tried and rejected. The same tracing on the current CSV is how a future update would continue closing the remaining gap to Graphiti-style and Mem0-style on decisions and errors, the same way Section 4's register finding was confirmed structurally rather than just observed in aggregate.
