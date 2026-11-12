# TokenMizer on long sessions, and a re-measurement of product `main`

**Date:** 2026-11-12
**Product commits** (`Shweta-Mishra-ai/tokenmizer`):
- `6b26679`: `main`, 0.6.1 plus #97. The baseline here.
- `80fe9c0`: branch `ccr-9cfc1c20-if05z2` at the start of this round. It carries six earlier rounds of audit work on prompt caching, extraction quality, the Ollama extraction path, Hinglish, and others.
- `100545f`, `f0ac2dc`, `f1ef922`, `943b7cd`: this round. `943b7cd` is final.

Follows [`REPORT_real_sessions_and_robustness.md`](REPORT_real_sessions_and_robustness.md). The last product commit measured there was `e600678` (round 8). That commit is not an ancestor of today's `main`, which was reached by squash merges, so the comparison here is against `main` itself.

## Headline

- **Labelled corpora are flat.** n=100: 92.4% macro F1. Held-out v1: 92.3%, v2: 93.0%, v3: 64.2%, v4: 58.5%. The audit work since `main` did not move them, and no session got worse except one on v3, explained in §1.
- **On 716 real agent sessions, error handling improved.** Production mode, paired 95% CIs:
  - error precision: +1.8 points [+1.0, +2.6];
  - runtime errors in the resume: +2.8 [+1.4, +4.3];
  - recall: unchanged.

  Whole-session mode: files in the resume +2.1 [+0.9, +3.2]. See §2.
- **A new long-session benchmark found six defects that no corpus could show.** At 120 turns the graph kept 23 of 50 planted facts. At 1,000 turns, 19.7 MB of history and a 4 MB tool output, it now keeps 50 of 50, recalls 50 of 50 into the request that asks, and keeps 50 of 50 across a restart.
- **Long sessions were slow because of a bug.** Once a session passed 500 messages, every request re-extracted old history whenever an old message was identical to a recent one. One request at 300 turns took 12.2 s and now takes 0.25 s.
- **Reproducing the real-agent study needed a fix.** The S3 bucket now refuses listing, so `fetch.py --sessions-from` downloads the sessions by key. The download is byte-identical to a direct one.

## 1. Labelled corpora

`python -m benchmarks.memorybench.run --corpus …`, all eight methods.

| Corpus | `main` | `943b7cd` | Paired Δ [95% CI] | Sessions worse / better |
|---|---:|---:|---|---|
| Main (n=100, tuned against) | 92.4% | 92.4% | 0.00 | 0 / 0 |
| Held-out v1 (n=80) | 92.3% | 92.3% | 0.00 | 0 / 0 |
| Held-out v2 (n=80) | 93.0% | 93.0% | 0.00 | 0 / 0 |
| Held-out v3 (n=80, frozen before round 5) | 64.3% | 64.2% | −0.05 [−0.14, 0.00] | 1 / 0 |
| Held-out v4 (n=80, frozen before round 8) | 58.3% | 58.5% | +0.13 [+0.03, +0.27] | 0 / 6 |

The comparison methods are unchanged by construction. On the main corpus
they score 59% (Graphiti-style), 60% (Mem0-style), 44%, 35% and under 21%.
On v3 they score at most 35%, and on v4 at most 25%.

**The one session that got worse** is `ho3_debug_production_001`, down 3.8
points. It gains two wrong pending tasks: "an outage root cause analysis",
and "structured logging around the suspect path done". The second is
finished work read as open.

The per-request path, which is how the proxy actually runs, already
produced both on `main`, on `80fe9c0`, and on `943b7cd`. Whole-session mode
used to read tasks only from the last 20 messages, which hid them. This
round removed that window (see §3), so whole-session mode now agrees with
production.

The misreads themselves were **not** fixed: v3 is held out, and tuning on
it would spend it.

## 2. Real agent sessions (716-session test split)

The pre-registered test split of [`REPORT_real_agents.md`](REPORT_real_agents.md):
- 716 sessions from five public SWE-bench Lite submissions;
- automatic ground truth: the files from the submitted patch, the errors from tracebacks and linter output.

The protocol and scoring are unchanged. The data was fetched by key (see §6)
and converted with the committed converters. Paired bootstrap over
sessions, 2,000 resamples.

| Test split, 716 sessions | Whole session: `main` → `943b7cd` | Production (one message per call): `main` → `943b7cd` |
|---|---|---|
| Runtime-error recall | 91.9% → 92.2% (+0.2 [−0.2, +0.7]) | 95.7% → 95.7% (0.0) |
| Lint-error recall | 95.7% → 95.7% | 99.8% → 99.8% |
| Error precision (vs automatic labels, a lower bound) | 30.9% → **33.6%** (**+2.7 [+1.6, +3.9]**) | 33.3% → **35.1%** (**+1.8 [+1.0, +2.6]**) |
| Runtime errors in the resume | 50.3% → 52.6% (+2.3 [0.0, +4.5]) | 52.3% → **55.2%** (**+2.8 [+1.4, +4.3]**) |
| Edited files in the resume | 67.9% → **70.0%** (**+2.1 [+0.9, +3.2]**) | 74.2% → 74.9% (+0.7 [−0.0, +1.6]) |
| Edited-file recall | 77.5% → 78.0% (+0.5 [0.0, +1.2]) | 78.7% → 79.1% (+0.4 [0.0, +1.1]) |
| Resume size | 222 → 240 tokens | 244 → 242 tokens |

**Where the gains come from:**
- Errors that differ only in an identifier are no longer merged. Sessions gaining a correctly grounded error: 24 in production mode, 40 in whole-session mode. None lose one in either mode.
- Files from bulk listings are ranked below the files the agent named, so more edited files reach the resume.
- Whole-session mode now reads every message, which costs 18 more resume tokens. Production mode always did.

**One loss was found and fixed during this round.** `sweagent_claude3opus__django__django-14608` lost its only labelled error at the intermediate commit `100545f`. The failing test names in a test run were no longer merged, so they filled the per-message error limit, and the traceback after them was dropped. At `943b7cd` it is recovered; see §3, item 4.

Per-session times in these runs come from parallel jobs on a shared VM, so
they are not compared.

## 3. Long sessions — a new benchmark, six defects

`python -m benchmarks.soak` is in the product repository. It drives the real
proxy the way a chat client does, resending the whole history on every
request. Windowing, compression, extraction, SQLite and recall all run as
in production. Only the provider is replaced, by a stand-in that records
what it was sent.

The session contains:
- filler from the captured transcripts;
- tool output of 1–200 KB;
- one 4 MB tool output, at 75% of the way through;
- **50 planted facts**: 10 each of decisions, errors, pending tasks, edited
  files and finished tasks.

Each planted fact carries an answer token that appears nowhere else. At the
end, each fact is asked about, long after its turn left the window. A fact
counts as recalled if its answer is in the request the proxy sends upstream.

**Defects found.** Each one is fixed, and each has a test that fails without
the fix.

1. **Merging was blind to identifiers.** "RuntimeError: amber_billing … overflowed the batch buffer" and the same sentence about marble_ledger share 5 of 6 words, so they became one node.
   - The same rule merged decisions about different keys.
   - Inside the extractor, it collapsed "write the A docs" with "write the B docs".
   - Labels that name different identifiers are now kept apart. Paths, snake_case, camelCase and file names count as identifiers. Line numbers, memory addresses, temp paths and technology spellings (Next.js / NextJS) do not.
2. **One call over a long history kept almost nothing.** This is the proxy's first request on an existing conversation.
   - It read tasks and errors only from the last 20 messages.
   - It kept at most 15 items per category.
   - Result: 30 TODOs came out as 1. Both limits are gone.
3. **Listings pushed real work out of the graph.**
   - A message naming more than 12 paths (`wc -l`, `git diff --stat`) added every path at full weight.
   - Every re-listing then raised the path's importance further.
   - At 1,000 turns, 402 re-listed paths at importance 1.0 had pushed out every file the agent named. Those files went to cold storage, so they were recoverable but no longer live.
   - Listed paths are now ranked 0.35 and are not raised by being listed again.
4. **A test run's failure list hid the failure.** The per-message error limit kept the first labels it saw. Those were failing test names, so the traceback after them was dropped. A named exception now outranks a bare name.
5. **Late requests re-extracted old history.** Found while profiling, and reported under Speed below.
6. **Questions in words never found files named in code.**
   - Retrieval matched whole tokens, so "the quartz uploader" shared nothing with `src/quartz_uploader/…`.
   - Function words ("for", "the") counted as overlap, which let unrelated decisions outrank the answer.
   - Identifiers are now also matched by their parts, and function words no longer count.
   - On the product's own retrieval eval, recall@6 went from 90% to 92% (37/40).

**Results, 1,000 turns** (19.7 MB of history at the end):

| | `80fe9c0` (start of round) | `943b7cd` |
|---|---:|---:|
| Planted facts in the graph | 23 / 50 *(at 120 turns)* | **50 / 50** |
| Recalled into the request that asks | 35 / 50 *(at 120 turns)* | **50 / 50** |
| In the graph after a restart (reloaded from disk) | — | **50 / 50** |
| Newest client message altered | — | 0 of 1,000 requests |
| Latency, first / last 10% of requests (median) | did not finish in an hour | 70 / 652 ms |
| Latency, last 10%, 95th percentile; slowest request | — | 1.16 s; 1.95 s (the 4 MB turn) |
| Process memory, start → end | — | 109 → 410 MB |

The process memory includes the client's own copy of the history, which
lives in the same process in this benchmark.

`--concurrent 8 --turns 200` runs eight sessions in parallel threads in one
process, 1,600 requests in all.
- Each session's own facts: 79 of 80 recalled.
- Another session's facts: **0 of 80 leaked** into a session asked about them.

## 4. Speed

**One request at 300 turns** (4 MB of history; one new user message):

| Step | Time |
|---|---:|
| Start of this round | 12.2 s |
| After fixing the processed-history boundary | 0.79 s |
| After caching tool-output path indexes | 0.25 s |

The 12.2 s request extracted about 60 old messages, twice. The cause: past
500 remembered messages, the boundary between processed and new history
was taken at the first recognised message. A repeated "ok", or the same
tool output said twice, put that boundary near the start of the session.
The boundary is now the longest run of recognised messages.

**Cold start**, one call over the whole history:

| History | `main` | `943b7cd` |
|---|---:|---:|
| Soak, 300 turns, 4 MB | 22.8 s | 4.6 s |
| Soak, 1,000 turns, 15 MB | 72 s | 14.8 s |
| SWE-agent `sphinx-doc-8282`, 6.5 MB (one 6.3 MB HTML observation) | 57 s | 1.5 s |
| SWE-agent `astropy-6938`, 643 KB | 3.1 s | 3.1 s |

The cold-start gains came from four changes:
- File nodes are indexed by basename during an extraction. Finding another spelling of a path had been quadratic: 7 M comparisons at 300 turns.
- Pattern extraction reads only the first and last 100 KB of a message. Across the 716 test sessions, every labelled error in a message that long sits in those parts, and 1 of 30 labelled items does not: a file named by coincidence inside the HTML dump.
- Four prefix-less regexes are gated by their own keywords.
- The quadratic library-name scan was removed.

The full text of every message still goes to the model, and to the turn
archive.

Warm whole-session extraction on the n=100 corpus takes 14 ms per session,
the same as on `main`. The 287 ms in the method table includes starting a
fresh Python process for every session.

## 5. Still wrong — found here, not fixed

- **Decision scope.** The decision extractor drops "for the billing service" from the label. A later decision in the same slot for a *different* component therefore supersedes it. `main` has the same behaviour.
  - A reproduction: "the billing service uses `billing_events`" is superseded by "the ledger service uses `ledger_events`".
  - In the soak, 16 of 18 planted decision nodes end up superseded. They are still recalled, because the resume carries supersessions, but `query()` skips superseded nodes and so finds only 2 of 10.
- **Changes of mind are missed.** "Change of plan: switch the partition key to `account_id`" and "Actually, let's store sessions in X instead" extract nothing, so the old choice stays current. `main` has the same behaviour.
- **Held-out v3 / v4 are still at 64% / 58%.** Pattern matching has reached its ceiling on implicit phrasing (round 8). The LLM extraction path, now runnable locally on Ollama, could not be measured here: no Ollama in this environment.
- **A 15 MB cold start still costs about 15 s** of extraction on the first request.
- **Memory growth was not separated from the harness.** The 109 → 410 MB includes the client's own history.
- **Measurement limits:**
  - Token counts use the character/4 fallback, because the tokenizer files could not be downloaded.
  - All timings come from one shared 4-core VM.
  - Soak facts are planted in explicit wording.

## 6. Reproducing

```bash
# product: git clone …/tokenmizer && git checkout 943b7cd   (or 6b26679 for main)
export TOKENMIZER_PRODUCT_REPO=/path/to/tokenmizer
python -m benchmarks.memorybench.run --corpus benchmarks/corpus_heldout4 --json out.json

# real agent sessions: listing is refused, so fetch by key
python -m benchmarks.realworld.fetch --out DATA --sessions-from benchmarks/results/realworld/test_fix.json
python -m benchmarks.realworld.swe_trajectories --src DATA/sweagent_gpt4 --system sweagent_gpt4 --out CONV/sweagent_gpt4   # each system
python -m benchmarks.realworld.openhands_trajectories --src DATA/openhands_codeact21 --out CONV/openhands_codeact21
python -m benchmarks.realworld.run_real --data CONV/… --split test --method tokenmizer_v0.5.2 [--incremental] --json out.json

# long sessions (in the product repository)
python -m benchmarks.soak --turns 1000 --giant-mb 4
python -m benchmarks.soak --concurrent 8 --turns 200
```

`benchmarks/` is now a regular package (`benchmarks/__init__.py`). With the
product installed in the same environment, its own `benchmarks` package
used to win the import, and `python -m benchmarks.memorybench.run` failed
with `No module named benchmarks.memorybench`.

Raw results for this report:
- `results/*_6b26679.*` and `results/*_943b7cd.*`: the five corpora.
- `results/realworld/test_6b26679{,_inc}.json` and `test_943b7cd{,_inc}.json`: the 716 real sessions, in both conditions.
