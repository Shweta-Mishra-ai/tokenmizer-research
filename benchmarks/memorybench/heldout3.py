"""
Third held-out phrasing corpus (v3).

Held-out v2 (`heldout2.py`) was read item by item after TokenMizer 4260983
was scored on it, to find what the next round should fix — so from that
round on v2 is a development set, and this corpus is the untouched check.
It was written and committed, with baseline scores, before any fix of that
round was made.

Same construction as v1 and v2 (fact pools, session shape, distractors),
with a FOURTH template set, disjoint from `generate.py`, v1 and v2
(enforced by `_assert_disjoint()`). The same limits apply: same author as
the fixes, shared fact pools, and no substitute for real labelled
transcripts.

    python -m benchmarks.memorybench.heldout3      # writes benchmarks/corpus_heldout3/
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from benchmarks.memorybench import heldout, heldout2

OUT_DIR = Path(__file__).resolve().parents[1] / "corpus_heldout3"

V3 = {
    "completed": {
        "explicit": ["Closed: {f}.", "Finished — {f}.", "Implemented {f}.", "* [x] {f}",
                     "**Shipped:** {f}.", "Result: {f} done."],
        "semi": ["{F} has been merged.", "{F} is working now.", "We completed {f} yesterday.",
                 "I've got {f} up and running.", "{F} was rolled out.", "{F} is sorted."],
        "implicit": ["Good news: {f} made it in before the freeze.",
                     "{F}? Taken care of.", "We can stop worrying about {f} now.",
                     "{F} went smoothly in the end."],
    },
    "pending": {
        "explicit": ["TO DO: {f}.", "Backlog: {f}.", "Action item: {f}.", "* [ ] {f}",
                     "Outstanding: {f}.", "Next task — {f}."],
        "semi": ["{F} still needs doing.", "{F} is on the backlog.", "Still to do: {f}.",
                 "I plan to do {f} next.", "{F} is still open.", "We need {f} before launch."],
        "implicit": ["{F} is the obvious next step.", "Nobody has touched {f} yet.",
                     "{F} is waiting for someone to pick it up.",
                     "Don't let {f} slip through the cracks."],
    },
    "decision_assistant": {
        "explicit": ["Choice: {f}.", "We've decided on {f}.", "**Decided:** {f}.",
                     "Agreed approach: {f}.", "Chose {f}."],
        "semi": ["We're going to use {f}.", "I've gone with {f}.", "Let's settle on {f}.",
                 "The plan is {f}.", "{F} is the pick."],
        "implicit": ["{F} beat the alternatives on every axis we care about.",
                     "Having compared the options, {f} is the best fit.",
                     "{F} is what we'll ship with.", "Everyone was happy with {f}."],
    },
    "decision_user": {
        "explicit": ["Choose {f}.", "Switch to {f}.", "Go ahead with {f}."],
        "semi": ["Should we go with {f}?", "Can we try {f}?", "I'd like {f}."],
        "implicit": ["{F} sounds like the better deal to me.", "I'm leaning towards {f}."],
    },
    "file": {
        "explicit": ["Edited: {f}.", "Affected file: {f}.", "- {f}", "File: `{f}`."],
        "semi": ["Changes are in {f}.", "I edited {f}.", "Have a look at {f}.",
                 "The relevant code is in {f}."],
        "implicit": ["Most of the work happened inside {f}.",
                     "{f} ended up with most of the changes.", "Rewrote parts of {f} as well."],
    },
    "error": {
        "explicit": ["Errors: {f}.", "Bug report: {f}.", "Incident: {f}.", "Failed: {f}.",
                     "**Issue:** {f}.", "Regression: {f}."],
        "semi": ["We ran into {f}.", "Hitting {f} in CI.", "We found {f}.",
                 "Customers are hitting {f}.", "There is {f} on the main branch."],
        "implicit": ["The alerts this morning came from {f}.",
                     "What broke the release was {f}.",
                     "Half the afternoon went to {f}.", "The root cause turned out to be {f}."],
    },
    "distractors": [
        "If this fails again we will revisit the design.",
        "There were no failures in the nightly run.",
        "The error messages are now clearer.",
        "Let me know if anything looks off.",
        "Here is the updated plan.",
        "Do we need more tests?",
        "I'll summarise at the end.",
        "Nothing is blocking us right now.",
        "We may decide to change this later.",
        "Failed jobs are retried twice.",
        "The build is green.",
        "Once CI passes I'll merge.",
    ],
    "user_prompts": [
        "Progress?", "Update me.", "Any errors?", "What's done?",
        "What about {p}?", "Keep going.", "Issues?", "Plan for {p}?",
    ],
    "openers": [
        ("Let's pick up {p}.", "Picking up {p}."),
        ("Back to {p}.", "Back on {p} now."),
        ("Help me with {p}.", "Sure, working on {p}."),
    ],
    "acks": ["Okay, doing it.", "Sounds right, on it.", "Agreed."],
}


def _assert_disjoint() -> None:
    gen = Path(__file__).with_name("generate.py").read_text()
    gen_t = set(re.findall(r'"([^"]*\{[fF]\}[^"]*)"', gen))
    earlier = gen_t | heldout2._templates(heldout.V1) | heldout2._templates(heldout2.V2)
    shared = heldout2._templates(V3) & earlier
    if shared:
        raise AssertionError(f"v3 templates overlap earlier corpora: {sorted(shared)}")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-n", type=int, default=80)
    ap.add_argument("--seed", type=int, default=20260926)
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()
    _assert_disjoint()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sessions = heldout.generate(args.n, args.seed, T=V3, prefix="ho3", label="Held-out v3")
    for s in sessions:
        (out / f"{s['id']}.json").write_text(json.dumps(s, indent=1, ensure_ascii=False) + "\n")
    print(f"Wrote {len(sessions)} sessions to {out}")


if __name__ == "__main__":
    main()
