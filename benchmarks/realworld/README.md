# Real-agent benchmark (SWE-bench trajectories)

**Status: protocol frozen before any method was run on this data.** The
converter, the fetch script and this file were committed first. Results are
added in a later commit, and they are computed with exactly the rules below.

## Data

These are the public SWE-agent trajectories on SWE-bench Lite, from four
submissions to github.com/SWE-bench/experiments. They are stored in the
public S3 bucket `swe-bench-submissions`.

| System | Model | Sessions |
|---|---|---:|
| `20240402_sweagent_gpt4` | GPT-4 | 300 |
| `20240402_sweagent_claude3opus` | Claude 3 Opus | 300 |
| `20240620_sweagent_claude3.5sonnet` | Claude 3.5 Sonnet | 289 |
| `20240728_sweagent_gpt4o` | GPT-4o | 278 |

That is 1,167 sessions in all: real GitHub issues from 12 Python
repositories, and about 101 M characters of message history.

- `fetch.py` downloads the raw trajectories. They are not committed
  (about 280 MB).
- `swe_trajectories.py` converts them into sessions in the benchmark's JSON
  format.

## Fifth system: OpenHands (added before any method was run on it)

| System | Model | Sessions | Format |
|---|---|---:|---|
| `20241025_OpenHands-CodeAct-2.1-sonnet-20241022` | Claude 3.5 Sonnet (2024-10-22) | 300 | OpenAI function calling (`tool_calls`, `role: "tool"`) |

- **Why it was added.** It is a second agent framework and a second message
  format. It is what TokenMizer's proxy receives from a function-calling
  agent, and it exercises the tool-call reading path the SWE-agent systems
  never reach.
- **Converter:** `openhands_trajectories.py`. Fetch it with
  `fetch.py --openhands`.
- **Ground truth:**
  - Errors use the same rules. The interpreter tag OpenHands appends to the
    last output line (`[Python Interpreter: …]`) is stripped first.
  - Files come from `logs/<instance>/patch.diff`, **with build artifacts
    removed**. OpenHands patches include command side effects: 1,096
    compiled `.mo` files in one patch, Sphinx `_build/` trees, SQLite
    databases. The filter (`is_artifact`) is fixed here, before measurement.
- **Secondary metrics, added at the same time and reported for every
  system:**
  - edited-file recall with the same artifact filter. For the SWE-agent
    systems this is *post hoc*: the filter would remove 327 of their 3,098
    ground-truth files, and their primary metric stays as frozen above;
  - per-session (macro) file recall, because a few patches create hundreds
    of files and would otherwise dominate the pooled ratio.
- The same dev/test split applies.

## Dev / test split (added before any full measurement)

Product bugs found on this data will be fixed. To keep the reported results
honest, the sessions are split by **issue**, never by system, so a GitHub
issue and all four systems' attempts at it land on the same side:

- `split(instance) = "test" if crc32(instance_id) % 2 else "dev"`

Rules:
- **dev** is used for finding and fixing bugs.
- **test** is never inspected session by session. It is scored once at the
  product commit before any fix (`50a2952`) and once after, and those are the
  reported numbers.
- Disclosure: before this split was fixed, a 5-session smoke test of the
  runner was run on random `sweagent_gpt4o` sessions. Only aggregate numbers
  were read.

## Ground truth (automatic; no hand labels)

- **files**: the paths changed by the patch the agent finally submitted
  (`diff --git a/X b/X`).
- **errors**: read from tool observations only, never from the agent's
  prose.
  - *runtime*: the final exception line of each Python traceback.
  - *lint*: each linter error the environment reported for a proposed
    edit (SWE-agent's E9xx/F8xx lines).
  - Deduplicated per session.

Completed tasks, pending tasks and decisions have no objective label in this
data and are not scored here.

## Conditions

- **task** (primary): the system prompt and the demonstration are dropped.
  The session starts at the issue text.
- **as-sent** (secondary): the system prompt and the demonstration are kept,
  exactly as the model received them. This is noisier: the demonstration is a
  complete trajectory for a different issue.

TokenMizer is run two ways: on the whole session at once, and one message
per call (incremental). Incremental is the way the proxy runs it in
production. The other methods run once per session.

## Metrics (per method; 95% bootstrap CIs over sessions, 2,000 resamples, seed 1729)

1. **Edited-file recall.** The share of ground-truth files that match some
   extracted file. A match means one path ends with the other at a `/`
   boundary, after stripping a leading `/` and the repository checkout
   directory (for example `/astropy__astropy/`).
2. **Error recall.** The share of ground-truth errors covered by some
   extracted error, using the benchmark's standard `covers()` rule at a
   threshold of 0.6. Reported separately for runtime and lint errors.
3. **Error precision against the automatic ground truth.** The share of
   extracted errors that cover some ground-truth error. This is a lower
   bound on true precision: prose can report a real failure that no
   traceback shows.
4. **Resume coverage at 400 tokens.** The share of ground-truth files and
   runtime errors that appear in the method's resume text. A file counts
   when its path or its base name appears; an error counts when the
   `covers()` rule holds against any line of the resume.
5. **Cost.** Resume tokens; compression (session tokens ÷ resume tokens);
   extraction time per session and, for incremental TokenMizer, per request.

## Threats to validity (stated in advance)

- All four systems use one agent framework (SWE-agent) and one language
  (Python). The message format is text commands, not structured tool calls.
- Linter errors dominate some sessions. That is why the two error kinds are
  reported separately.
- The submitted patch can include helper scripts the agent created (for
  example `reproduce.py`). They are real edits and stay in the ground truth.
- Error precision is a lower bound, as described above.
