# TokenMizer vs. Other Memory Methods — A 100-Session Benchmark

**Date:** August 10–11, 2026 (see Section 0 for what changed on the 11th)
**Data:** 100 labelled sessions, 8 methods compared
**Files:** `benchmarks/results/memorybench_n100_20260811.json` (full numbers), `.csv` (spreadsheet-friendly), `dashboard.html` (visual view)
**How to re-run:** `python -m benchmarks.memorybench.run`

---

## 0. What Changed Since the First Run (August 10 → 11)

The first run of this test (August 10) measured TokenMizer at 57% overall, behind two other methods (Graphiti-style, Mem0-style) on points, though not by a reliable margin. Its two weakest categories were decisions (50%) and errors (36%) — both worse than TokenMizer's own other categories *and* worse than those same two methods on the same test.

Instead of stopping there, we read the actual missed and wrong answers behind that 50%/36% and found 4 specific, fixable bugs in TokenMizer's code — not a vague "needs more data" problem. We fixed 3 of them directly, tried a 4th fix that turned out to backfire (see Section 9), and reverted it. Then we re-ran the exact same test.

**Result: decisions went from 50% to 59%, errors went from 36% to 44%, and TokenMizer's overall score went from 57% to 60% — moving it from behind the two closest competitors to essentially tied with them.** Every number below is from this second run (TokenMizer version 0.5.3), except where marked "before."

---

## Summary

We tested TokenMizer (the real product) against 7 other memory methods on 100 test sessions. Each method reads a conversation and tries to pull out 5 things: completed tasks, pending tasks, decisions, file names, and errors. We compared what each method found against a hand-checked answer key.

**Main result:** TokenMizer clearly beats simple methods (keeping the last few messages, summarizing, etc.) and two other graph-based methods (MemGPT-style and GraphRAG-style). Against two other methods — Graphiti-style and Mem0-style — it's now a close tie, with TokenMizer's score edging very slightly ahead on points (60% vs 59–60%), though not by enough to call it a real win.

**Main weakness found, and partly fixed:** TokenMizer was noticeably worse than the other methods at finding **decisions** and **errors** in a conversation. We fixed the concrete bugs we could find (Section 9) and cut roughly a third of the decision gap and a fifth of the error gap to the closest competitors. Both categories are still TokenMizer's weakest.

**Also found, and NOT fixed by the above:** every method we tested, including TokenMizer, does much worse when a conversation states things indirectly instead of using clear markers like "Decided:" or "Completed:". This is not a TokenMizer-only problem — all 4 pattern-based methods dropped to about 20–27% accuracy on indirect text, before and after our fixes. Fixing the specific bugs we found did not move this number, which tells us it needs a different kind of fix (an AI model actually reading the sentence, not more pattern rules).

---

## 1. What We Tested

### 1.1 The methods

| Method | What it is |
|---|---|
| **TokenMizer 0.5.3** | The real product. We ran the actual code, not a copy. |
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
| **TokenMizer 0.5.3** | **60%** | 55%–65% | 100 | 44 ms |
| Mem0-style | 60% | 55%–64% | 117 | 0.9 ms |
| Graphiti-style | 59% | 55%–64% | 119 | 1.0 ms |
| GraphRAG-style | 44% | 41%–48% | 80 | 0.5 ms |
| MemGPT-style | 35% | 32%–38% | 60 | 0.4 ms |
| Naive truncation | 20% | 20%–21% | 287 | <0.1 ms |
| Sliding window | 18% | 18%–19% | 150 | <0.1 ms |
| Naive summary | 17% | 16%–18% | 186 | <0.1 ms |

("Resume size" is how many tokens the method's output takes up — smaller is more efficient, if the score is similar. MemGPT-style's small size is because it only looks at part of the conversation, not because it's more efficient — see Section 6.)

### Is TokenMizer actually better than each one?

We compared TokenMizer directly against each other method, on the same 100 sessions, and checked if the difference is bigger than random noise:

| Compared to | Difference | Is it a real difference? |
|---|---:|---|
| Graphiti-style | +0.4 points | No — could easily be noise |
| Mem0-style | +0.3 points | No — could easily be noise |
| GraphRAG-style | +16 points | **Yes, TokenMizer wins** |
| MemGPT-style | +25 points | **Yes, TokenMizer wins** |
| Sliding window | +42 points | **Yes, TokenMizer wins** |
| Naive truncation | +39 points | **Yes, TokenMizer wins** |
| Naive summary | +43 points | **Yes, TokenMizer wins** |

**In plain words:** TokenMizer is a clear winner over simple/naive approaches and over 2 of the 4 graph-based methods. Against the other 2 (Graphiti-style, Mem0-style), the scores are close enough that we should not claim TokenMizer is better — it's a tie, though TokenMizer's point estimate now edges ahead instead of behind, and it still produces a smaller/cheaper output than either.

---

## 3. Where TokenMizer Is Strong and Weak

| Category | TokenMizer (before → after fix) | Best other method |
|---|---:|---:|
| Completed tasks | 68% (unchanged) | 64% (TokenMizer ahead) |
| Pending tasks | 53% (unchanged) | 45% (TokenMizer ahead) |
| File names | **98%** (unchanged) | 89% (TokenMizer clearly ahead) |
| Decisions | 50% → **59%** | 65% (TokenMizer still behind, gap cut roughly in half) |
| Errors | 36% → **44%** | 66% (TokenMizer still behind, gap narrowed) |

**Files are basically solved** — TokenMizer finds file names almost perfectly.

**Decisions and errors are still the weak spots, but less so.** For errors specifically: out of 148 errors mentioned across all 100 sessions, TokenMizer now finds 93 (was 79), of which 41 don't match a real error (was 39). Both categories improved because we fixed real bugs, not because the test got easier — see Section 9 for exactly what we found and fixed.

---

## 4. The Big Pattern: Explicit vs. Indirect Language

We tagged every test conversation by how directly it states facts. Here's how each method's score changes:

| Method | Explicit ("Decided: X") | Plain sentence | Mixed | Indirect / buried in reasoning |
|---|---:|---:|---:|---:|
| TokenMizer | 74% | 58% | 58% | **27%** |
| Graphiti-style / Mem0-style | 85% | 68% | 63% | 19% |
| GraphRAG-style | 69% | 37% | 47% | 19% |
| MemGPT-style | 46% | 39% | 36% | 10% |

Every method that relies on pattern-matching — including TokenMizer — falls to around 19–27% once the conversation stops using clear marker words. This is not something specific to TokenMizer; it's a limit of this whole approach (pattern matching / regex). **We confirmed this directly:** the bug fixes in Section 9 moved TokenMizer's explicit-text score up 3 points and its indirect-text score up only 2 points (inside noise) — a targeted vocabulary fix reaches explicit and semi-explicit phrasing, not this ceiling. To fix the indirect-language ceiling, a method would likely need an AI model in the loop to actually read and understand the sentence, which none of the methods here use.

---

## 5. Real Conversations vs. Generated Ones

| Method | Real conversations (6) | Generated conversations (94) |
|---|---:|---:|
| TokenMizer | **91%** (unchanged) | 58% (was 55%) |
| Graphiti-style / Mem0-style | 58% | 60% |

TokenMizer does much better on the 6 real conversations than on the 94 generated ones, and the fix in Section 9 didn't change that — the real-conversation score stayed exactly the same while the generated-conversation score went up. This makes sense — TokenMizer's patterns were likely tuned against conversations similar to those 6. But there are only 6 of them, so this number is not very statistically solid — treat it as a hint, not a proven result.

---

## 6. Cost

TokenMizer takes about 44 milliseconds per conversation, while the other methods take under 1 millisecond. This is mostly because we ran TokenMizer as a separate real program (to make sure we tested the actual product code, not a copy), which has startup overhead. It does not mean TokenMizer's underlying method is 45x slower — it means launching a full program 100 times adds overhead that a simple in-process function does not have. The 2 new pattern-matching passes added in Section 9 add a small amount of real work on top of that, but the process-launch overhead dominates either way.

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
- Against the other 2 graph-memory strategies (Graphiti-style, Mem0-style), it's a statistical tie, not a win — though TokenMizer's point score now edges ahead instead of behind, and it produces a smaller output than either.
- We found and fixed 3 concrete bugs behind TokenMizer's weak decision/error scores (Section 9), cutting roughly a third of the decision gap and a fifth of the error gap to the closest competitors — a real, measured improvement, not a guess.
- Both categories are still TokenMizer's weakest, and the indirect-language problem (Section 4) is untouched by this fix — that needs a different kind of solution.

---

## 9. What We Fixed, and What We Tried and Rejected

This section is the detail behind the "before → after" numbers above. All of it happened in the actual TokenMizer product code (not this research repo — see the product repo's `CHANGELOG.md`, version 0.5.3), guided directly by reading the missed/wrong answers this benchmark produced.

**Four causes found**, each confirmed against real text from this test's conversations, not guessed at:

1. **TokenMizer was extracting fake decisions from questions.** A message like "What did you decide on the approach?" was treated the same as an actual decision statement, pulling out "the approach" as a made-up decision. Fixed: decisions are no longer extracted from a sentence that ends in a question mark.
2. **The list of known tool/technology names was too short.** TokenMizer only recognized tools on a fixed list of about 50. Real tools used in our test conversations — `sqlc`, `NATS`, `golangci-lint`, `OpenTelemetry`, `Alembic`, and others — were invisible even when clearly stated as a decision. Fixed: added 8 specific, verified-missing tool names to the list.
3. **TokenMizer's list of "decision" phrases was too narrow.** Phrases like "We're leaning toward NATS" used wording TokenMizer didn't recognize as a decision. Fixed: added a few more common phrasings.
4. **TokenMizer's error vocabulary had real gaps.** It recognized "null pointer" but not "nil pointer" (the term Go programmers actually use). It didn't recognize "GC pressure," "poison message," "consumer lag," or "schema drift" at all. It also cut error descriptions short in cases like "deadlock **between** the two mutexes," because it only kept reading after the words "in/on/from," not "between." Fixed: added the missing words and widened where it keeps reading.

**One fix we tried and reversed, because we measured it hurting the product, not just accepted it:** for cause 2 (missing tool names), the obvious "smart" fix is to stop using a fixed list altogether and instead recognize anything that *looks* like a tool name — words with mixed capitals like "OpenTelemetry," hyphenated words like "golangci-lint," or short all-capitals words. We built this and tested it — not just reasoned about it — against TokenMizer's own separate 14-conversation test set (used for its release checks). It caught more real tools, but it also mistakenly flagged ordinary English as decisions: "per-row" and "pre-download" are hyphenated but aren't tools; "CSS" and "DMS" are short and capitalized but aren't decisions in context. This dropped TokenMizer's decision accuracy on that other test set from 90% down to 81% — a real regression, not a hypothetical one. We reverted it and used the safer, hand-checked list expansion (cause 2's fix above) instead.

We're reporting the failed attempt, not just the ones that worked, because a report that only shows fixes that succeeded makes the problem look easier than it is — and because we left a note in the actual code explaining why that approach was tried and reverted, so nobody has to rediscover the same dead end.

**Checked for regressions before trusting the improvement:** every fix was run against TokenMizer's full test suite (610 tests, all passing) and its own separate 14-conversation benchmark (decision accuracy unchanged at 90% precision / 95% recall) before we re-ran this 100-conversation test. The categories we didn't touch (completed tasks, files) stayed exactly the same score before and after — which is what you'd expect from a real, targeted fix rather than a lucky fluke that happened to move everything.
