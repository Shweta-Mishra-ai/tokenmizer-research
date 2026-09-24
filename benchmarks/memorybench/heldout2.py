"""
Second held-out phrasing corpus (v2).

Held-out v1 (`heldout.py`) was used once as an untouched generalisation
check, and its per-item failures were then read to find the remaining
defects. From that point it is no longer held out: a fix informed by its
failures will score better on it for that reason alone. This corpus
replaces it as the untouched check for the next round of fixes.

Same construction as v1 — same fact pools, same session shape, distractor
sentences — with a THIRD template set, disjoint from both `generate.py` and
v1 (checked by `_assert_disjoint()` below). It was written and committed,
with baseline scores, before any fix informed by v1's failures was made.

Limits, stated plainly: it was written by the same author as the fixes it
evaluates, who knew v1's failure list when writing it. That makes it a
weaker check than text nobody on the project wrote. The fact pools are
shared with the other two corpora. Real labelled transcripts remain the
check this cannot replace.

    python -m benchmarks.memorybench.heldout2       # writes benchmarks/corpus_heldout2/
    python -m benchmarks.memorybench.run --corpus benchmarks/corpus_heldout2
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from benchmarks.memorybench import heldout

OUT_DIR = Path(__file__).resolve().parents[1] / "corpus_heldout2"

V2 = {
    "completed": {
        "explicit": ["Completed — {f}.", "[done] {f}", "Resolved: {f}.", "Delivered: {f}.",
                     "✔ {F}", "**Completed:** {f}."],
        "semi": ["{F} is finished.", "{F} went out this morning.", "I've wrapped {f}.",
                 "{F} is live now.", "Managed to finish {f}.", "{F}: done."],
        "implicit": ["{F} is no longer on my plate.", "Glad to report {f} is sorted.",
                     "After a couple of tries, {f} finally works.",
                     "That leaves {f} behind us."],
    },
    "pending": {
        "explicit": ["**TODO:** {f}.", "Still open: {f}.", "Next task: {f}.", "[ ] {f}",
                     "Planned: {f}.", "Queued: {f}."],
        "semi": ["I still owe you {f}.", "{F} is on deck.", "Haven't gotten to {f}.",
                 "We need to do {f} next.", "{F} is waiting on me.", "Tomorrow: {f}."],
        "implicit": ["Eventually {f} has to get done too.", "{F} keeps slipping.",
                     "I'd like to get {f} in before Friday.", "Someone should pick up {f}."],
    },
    "decision_assistant": {
        "explicit": ["Chosen: {f}.", "Decision made: {f}.", "**Choice:** {f}.",
                     "We are going with {f}.", "Resolution: {f}."],
        "semi": ["I'd go with {f}.", "We'll use {f}.", "Settling on {f}.",
                 "Our pick is {f}.", "{F} is what we're using."],
        "implicit": ["{F} is the clear winner here.", "All things considered, {f} wins.",
                     "Between the options, {f} came out ahead.", "We landed on {f}."],
    },
    "decision_user": {
        "explicit": ["Let's use {f}.", "Stick with {f}.", "I want {f}."],
        "semi": ["Could we use {f}?", "What about {f}?", "I'd rather have {f}."],
        "implicit": ["Personally {f} feels right to me.", "I lean towards {f}."],
    },
    "file": {
        "explicit": ["Touched: {f}.", "Changed files: {f}.", "* `{f}`", "Path: {f}."],
        "semi": ["See {f}.", "I put it in {f}.", "Edits are in {f}.",
                 "Check {f} for the change."],
        "implicit": ["Turned out {f} was the culprit file.",
                     "Most of the afternoon went into {f}.", "{f} got a few more lines."],
    },
    "error": {
        "explicit": ["Error — {f}.", "Bug found: {f}.", "Known issue: {f}.", "Failing: {f}.",
                     "**Bug:** {f}.", "Defect: {f}."],
        "semi": ["Running into {f}.", "We keep getting {f}.", "Users reported {f}.",
                 "There's {f} in production.", "Found {f} during testing."],
        "implicit": ["Turns out the flakiness was {f}.",
                     "The dashboards lit up because of {f}.", "Root of the pain: {f}.",
                     "Pager went off for {f} again."],
    },
    "distractors": [
        "If the tests fail, the pipeline blocks the merge.",
        "Nothing failed on the last run.",
        "Retries only apply to failed jobs.",
        "Happy to dig into this more.",
        "Here's what I found.",
        "Should we add more logging?",
        "Let me check the docs first.",
        "We might revisit this later if needed.",
        "The error budget is fine this month.",
        "Decisions like this usually need a design doc.",
        "No regressions so far.",
        "Once the build is green we can merge.",
    ],
    "user_prompts": [
        "How are we doing?", "Next?", "Anything broken?", "Recap please.",
        "Where did we land on {p}?", "Carry on.", "Blockers?", "What changed?",
    ],
    "openers": [
        ("Picking {p} back up.", "OK, back on {p}."),
        ("Let's continue {p}.", "Continuing {p}."),
        ("I need help finishing {p}.", "Happy to help with {p}."),
    ],
    "acks": ["Sure thing.", "Yep, doing that.", "Good call, switching."],
}


def _templates(T: dict) -> set[str]:
    out = set()
    for key, val in T.items():
        if isinstance(val, dict):
            for reg in val.values():
                out.update(reg)
    return out


def _assert_disjoint() -> None:
    """No v2 template may appear in generate.py or in v1."""
    gen = Path(__file__).with_name("generate.py").read_text()
    gen_t = set(re.findall(r'"([^"]*\{[fF]\}[^"]*)"', gen))
    shared = _templates(V2) & (gen_t | _templates(heldout.V1))
    if shared:
        raise AssertionError(f"v2 templates overlap earlier corpora: {sorted(shared)}")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-n", type=int, default=80)
    ap.add_argument("--seed", type=int, default=20260925)
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()
    _assert_disjoint()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sessions = heldout.generate(args.n, args.seed, T=V2, prefix="ho2",
                                label="Held-out v2")
    for s in sessions:
        (out / f"{s['id']}.json").write_text(json.dumps(s, indent=1, ensure_ascii=False) + "\n")
    print(f"Wrote {len(sessions)} sessions to {out}")


if __name__ == "__main__":
    main()
