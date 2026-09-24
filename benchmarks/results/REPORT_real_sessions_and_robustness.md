# TokenMizer on real agent sessions and hostile input

**Date:** 2026-09-25
**Product commits:** `e38294a`, `b711c58` and `4260983` on branch
`claude/tokenizer-research-oqcgbg` of `Shweta-Mishra-ai/tokenmizer`. Measured
against round 3 (`b6a5422`) and the original baseline (`a184cf1`).

Follows [`REPORT_extraction_rounds.md`](REPORT_extraction_rounds.md). That
report measured labelled corpora. This one tests what those corpora cannot
contain:
1. A **real agent session**: tool calls, tool results, code, tables, quoted
   examples and a Hindi-English mix.
2. **Fuzzing**: malformed and hostile messages sent to every extraction
   entry point.
3. **A regex scan**: every one of the product's 134 regexes, run against
   adversarial inputs.
4. **Hostile HTTP requests and concurrent load** against
   `/v1/chat/completions`.

## Headline

- **Agent tool calls were invisible, and most tool turns were silently
  dropped.** Both are fixed.
- **One denial-of-service bug was confirmed** in the original code (10 s on
  one small message), along with seven more quadratic regexes and a crash
  on one legal JSON character. All are fixed and pinned by tests.
- **On a real session, about 87% of stored facts are genuine**, against
  about 45% at round 3. That figure is my own label-by-label judgement, not
  a labelled score.
- **Labelled corpora are unchanged.** Main corpus 92%, held-out v1 79%,
  held-out v2 51%.
- **Cost:** extraction about 26% slower in isolation (median 15.4 → 19.4 ms
  per session), and about 10% lower throughput under concurrent load.

## 1. The real session

The input was a real Claude Code session (this one), frozen at 914
messages and 1.77 MB. It was fed to `GraphMemory.extract_from_messages` in
the Anthropic message format, incrementally, the way the proxy runs. Nothing
in it is labelled, so every stored node was judged by hand: genuine means it
states something that actually happened in the session.

| Node type | Round 3 (`b6a5422`) | Now (`4260983`) |
|---|---|---|
| Errors | 1 genuine of 6 | 9 of 9 |
| Files | 5 of 7 | 12 of 14 |
| Tasks | ~4 of 21 | 6 of 8 |
| Decisions | 0 of 2 (a false "Changes: 'Use error fragment' → 'Use longer label'") | 0 extracted |
| Dependencies | 0 of 2 ("agentic", "them") | 0 extracted |
| **Total** | **~17 of 38 (45%)** | **~27 of 31 (87%)** |

The nine errors now include every failure that actually happened in the
session and came back as a tool error. Examples: `KeyError: 'decisions'`,
`ModuleNotFoundError: No module named 'matplotlib'`, `JSONDecodeError`,
`SyntaxError: unterminated string literal`. Before, the only one found came
from prose.

**What caused the noise, and the fix for each:**
- **Tool calls were never read.** `_content_to_text` keeps text blocks
  only, so an agent's `Edit(file_path=…)` and the tracebacks in its tool
  results never reached extraction.
  - Fix: `helpers.tool_signals` takes file paths from the arguments of tools
    that change files, and errors from failed tool results.
  - Formats: OpenAI `tool_calls`, Anthropic `tool_use`/`tool_result`, Gemini
    `functionCall`.
- **Most tool turns were skipped.** `_msg_hash` hashed only the *text*. Every
  tool-only turn therefore hashed to `sha1("")`, and every one after the
  first was treated as "already processed". This predates the branch.
  - Fix: a message with any non-text part is hashed whole. Plain-text
    messages keep their old hash, so persisted sessions don't re-scan.
- **Mentions were read as statements.** Quoted examples, table rows and code
  blocks were extracted as facts.
  - Fix: `patterns.mask_mentions` blanks them before the prose patterns run,
    keeping offsets intact. Error lines pasted in code blocks and quoted
    exception names stay visible.
- **Non-English text was misread.** The English prose patterns misfire on a
  Hindi-English mix. "…karogi paid but pending all task" became a to-do.
  - Fix: `patterns.looks_english` detects another language's function words.
    Across the 6,162 English messages in four corpora, it misclassifies none.
    A non-English message gets only language-neutral extraction: paths,
    exception names, checkboxes and headers.
- **Grammar misreads.** Hyphenated compounds were read as keywords
  (`fixed-width`, `pending-task`). A pronoun or gerund was taken as a task's
  subject. Hypothetical failures ("would fail") counted as errors. A pytest
  error line was retyped as a file. "pending" and "adding" were used as
  keywords anywhere, and an edit described with two common nouns became a
  supersession.
- **Stale "Working on" line.** It listed the *oldest* work first. Every task
  has the same importance, so the sort fell back to insertion order.

**What remains on this session:**
- Two example filenames mentioned in prose are listed as files.
- Two tasks are misreadings.
- "Working on" still carries items finished without anyone saying so.

## 2. Hidden bugs from fuzzing and the regex scan

The fuzzer sent 1,000 iterations of random messages to `heuristic_extract`,
to incremental `extract_from_messages`, to `to_context_block`, and to a
reload from disk. The inputs covered:
- wrong types (`None`, integers, dicts)
- broken tool calls
- 3,000-word messages
- NUL bytes, lone surrogates, emoji, and mixed scripts

After the fixes below: **0 exceptions.** The worst case per iteration fell
from 4.7 s to about 1.7 s. Each iteration runs about 8 incremental
extractions plus a reload, over as much as 80 KB of hostile text.

| Defect | Where | Before | After |
|---|---|---:|---:|
| `"x"` + 4,000 spaces + `"x"` (**DoS**) | `_TASK_DONE_PASSIVE`, pre-existing | 10.35 s (16.5 s at 5,000) | 0.02 s |
| 4,000 blank lines | `_DECISION_HEADER`, pre-existing | 1.3 s | linear |
| 4,000-digit run | `_EVIDENCE_NUMBER`, pre-existing | 1.3 s | linear |
| `a-a-a-…` | `_FILE_COMMON`, pre-existing | 0.36 s | linear |
| Blank lines / tabs | `_ERROR_CANNOT_INITIAL`, `_SCHEMA_HEADER`, `summary._CLAUSE`, pre-existing | 0.1–0.4 s | linear |
| Space runs left by masking | three header patterns from this branch | 0.85 s per 79 KB | linear |
| Lone surrogate `"\ud800"` (legal JSON) | `_msg_hash` and every `.encode()`, pre-existing | **crash** (`UnicodeEncodeError`) | scrubbed to U+FFFD |

After the fixes, none of the 134 regexes in the package is super-linear on
any of the 29 adversarial payloads.

## 3. The HTTP boundary

**Hostile requests.** 26 malformed or hostile bodies were sent to
`/v1/chat/completions`. They included a lone surrogate, NUL bytes, 200 KB of
whitespace, 5,000 nested brackets, a `session_id` of `../../etc/passwd`, a
10,000-character model name, broken tool calls and prompt injection.
- **No 5xx.** Every body returned 200 or a clean 4xx, and injection was
  blocked with a 400.
- Session IDs only ever reach parameterised SQL and hashed lock names, so
  path traversal is not possible.
- `max_tokens: -5` used to go all the way to the provider. Sampling values
  are now range-checked and rejected up front with a 422.

**Concurrent load.** 16 threads sent 400 requests: agentic conversations
growing to about 100 messages, with shared and separate sessions, a fake
provider, one process, and the rate limiter off.
- **400/400 OK**, and `/health` reported no persistence failures and no data
  loss.
- Throughput, three alternating runs each: about 214 req/s before, about
  193 req/s after (−10%). p50 51 → 59 ms, p95 about 110 ms on both.
- With the rate limiter on, the same load returns 429s as designed.

## 4. Labelled corpora: no regression

| Corpus | `a184cf1` | round 3 `b6a5422` | now `4260983` |
|---|---:|---:|---:|
| Main (tuned against) | 61% | 92% | 92% |
| Held-out v1 | 40% | 79% | 79% |
| **Held-out v2 (never tuned against)** | **33%** | **51%** | **51%** |

- **Product checks.** Internal eval unchanged at 97%. The checkpoint-accuracy
  benchmarks are unchanged: v1 80/100/100 and v2 82/92/100 for task,
  decision and file recall.
- **Tests.** The product suite went from 1551 to 1616. The new ones are in
  `tests/unit/test_agentic_robustness.py`. The key cases were checked
  against the original code and fail there as they should: 0 of 5 tool-turn
  files found, a crash on the surrogate, and the noise labels present.
- **A regression caught along the way.** One mid-round held-out v1 run showed
  a 3-point pending-recall dip. I had caused it, and it was fixed before the
  final commit.

## 5. What this work did not do

**Understanding other languages.** Pattern matching cannot read Hindi,
Spanish or Chinese. This round only stops it from producing garbage on them.
Real multilingual extraction needs the LLM extraction path. That could not
be run here: there is no model API key, and the network policy blocks
downloading a local model from Hugging Face or Ollama. A free local model
through Ollama, which the product already supports, is the route to try next
on a machine that can download one.

**Pending-task recall on held-out v2 is still 19%.** No pattern work was
aimed at it this round. Tuning further against the corpora would overfit
them (see the earlier report).

**One real session is one session.** The 87% is my judgement on one
transcript, and I wrote much of it. A labelled set of real transcripts,
labelled by someone else, remains the most valuable addition to this
repository.

**Load was tested in-process with a fake provider.** That measures
TokenMizer's own overhead and correctness under concurrency, not provider
latency or a multi-worker deployment.
