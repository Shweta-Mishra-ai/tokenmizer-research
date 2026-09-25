"""
Fourth held-out phrasing corpus (v4).

Held-out v3 (`heldout3.py`) was the untouched check for rounds 5 to 7. The
next round targets marker-free ("implicit") phrasing, the weakest register
on v3 (40%), and reading v3's implicit failures to do that would make v3 a
development set. This corpus was written and committed, with baseline
scores, before any change of that round was made, and is the honest check
for it.

Same construction as v1 to v3 (fact pools, session shape, distractors),
with a FIFTH template set, disjoint from `generate.py`, v1, v2 and v3
(enforced by `_assert_disjoint()`). The implicit templates are the reason
it exists, so they are as many as the other registers' and written the
way people report work without naming its state: outcomes, consequences,
things that no longer need attention.

The same limits apply as before: same author as the fixes, shared fact
pools, and no substitute for real labelled transcripts.

    python -m benchmarks.memorybench.heldout4      # writes benchmarks/corpus_heldout4/
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from benchmarks.memorybench import heldout, heldout2, heldout3

OUT_DIR = Path(__file__).resolve().parents[1] / "corpus_heldout4"

V4 = {
    "completed": {
        "explicit": ["Complete: {f}.", "Delivered — {f}.", "Landed {f}.", "- [X] {f}",
                     "**Finished work:** {f}.", "Wrapped: {f}."],
        "semi": ["{F} is finished and deployed.", "{F} went in this morning.", "I got {f} over the line.",
                 "{F} is up and working.", "{F} has shipped.", "We have {f} now."],
        "implicit": ["{F} is behind us now.", "{F} came off the board this morning.",
                     "{F} has been live since Tuesday with no complaints.",
                     "Nobody needs to think about {f} anymore.",
                     "Thanks to {f}, the on-call pages stopped.",
                     "{F} held up fine through the whole load test."],
    },
    "pending": {
        "explicit": ["Still open — {f}.", "Todo — {f}.", "In the queue: {f}.", "- [ ] TODO {f}",
                     "**Pending:** {f}.", "Left to do — {f}."],
        "semi": ["{F} hasn't been started.", "{F} is next up.", "We haven't done {f} yet.",
                 "{F} is still owed to the client.", "{F} remains open.", "{F} is waiting on us."],
        "implicit": ["Somebody has to own {f} before Friday.",
                     "{F} keeps getting pushed to next sprint.",
                     "We can't call this finished while {f} is missing.",
                     "{F} is the piece nobody has picked up.",
                     "Once the release settles, {f} is where attention goes.",
                     "Without {f} the launch checklist stays red."],
    },
    "decision_assistant": {
        "explicit": ["Final call: {f}.", "We resolved to use {f}.", "**Chosen:** {f}.",
                     "Going forward: {f}.", "Consensus: {f}."],
        "semi": ["We're standardising on {f}.", "I've locked in {f}.", "We'll run with {f}.",
                 "The team picked {f}.", "{F} won the vote."],
        "implicit": ["After the spike, {f} was the clear winner.",
                     "{F} is what everything will be built on from here.",
                     "The trade-offs all pointed to {f}.",
                     "{F} is the direction we committed to.",
                     "Nobody argued once they saw the numbers for {f}."],
    },
    "decision_user": {
        "explicit": ["Use {f} please.", "Pick {f}.", "Let's commit to {f}."],
        "semi": ["What if we went with {f}?", "My preference would be {f}.", "Could {f} work for us?"],
        "implicit": ["{F} feels like the right fit here.", "I keep coming back to {f}."],
    },
    "file": {
        "explicit": ["File changed — {f}.", "Touched file: {f}.", "* {f}", "Path: `{f}`."],
        "semi": ["I updated {f}.", "See the diff in {f}.", "The fix lives in {f}.",
                 "Details are in {f}."],
        "implicit": ["The bulk of the diff sits in {f}.",
                     "{f} grew by a couple hundred lines.",
                     "Had to untangle {f} first."],
    },
    "error": {
        "explicit": ["Failing now: {f}.", "Known defect — {f}.", "Outage: {f}.", "Broken: {f}.",
                     "**Fault:** {f}.", "Crash: {f}."],
        "semi": ["We keep seeing {f}.", "Got hit by {f} in staging.", "Spotted {f} today.",
                 "Support tickets mention {f}.", "Production is showing {f}."],
        "implicit": ["The pager went off twice overnight because of {f}.",
                     "Most of yesterday disappeared into {f}.",
                     "The dashboard lit up red with {f}.",
                     "Turns out the slowdown was {f} all along."],
    },
    "distractors": [
        "If this breaks later we can roll back.",
        "No incidents were reported this week.",
        "The logs are easier to read now.",
        "Ping me if anything seems wrong.",
        "Here's where things stand.",
        "Should we add more coverage?",
        "I'll post a recap later.",
        "Nothing is waiting on anyone at the moment.",
        "We might revisit this next quarter.",
        "Flaky jobs get one automatic retry.",
        "CI is passing.",
        "After review I'll deploy.",
    ],
    "user_prompts": [
        "Where are we?", "Status please.", "Anything broken?", "What landed?",
        "How is {p} going?", "Carry on.", "Blockers?", "Next steps for {p}?",
    ],
    "openers": [
        ("Let's continue {p}.", "Continuing {p}."),
        ("Resume {p}.", "Resuming {p} now."),
        ("Can you take {p}?", "Yes, taking {p}."),
    ],
    "acks": ["Sure, on it.", "Makes sense, doing that.", "Fine by me."],
}

def _assert_disjoint() -> None:
    gen = Path(__file__).with_name("generate.py").read_text()
    gen_t = set(re.findall(r'"([^"]*\{[fF]\}[^"]*)"', gen))
    earlier = (gen_t | heldout2._templates(heldout.V1) | heldout2._templates(heldout2.V2)
               | heldout2._templates(heldout3.V3))
    shared = heldout2._templates(V4) & earlier
    if shared:
        raise AssertionError(f"v4 templates overlap earlier corpora: {sorted(shared)}")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-n", type=int, default=80)
    ap.add_argument("--seed", type=int, default=20260927)
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()
    _assert_disjoint()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sessions = heldout.generate(args.n, args.seed, T=V4, prefix="ho4", label="Held-out v4")
    for s in sessions:
        (out / f"{s['id']}.json").write_text(json.dumps(s, indent=1, ensure_ascii=False) + "\n")
    print(f"Wrote {len(sessions)} sessions to {out}")


if __name__ == "__main__":
    main()
