"""
Held-out phrasing corpus.

The committed 94-session synthetic corpus renders every fact through a
small, fixed set of sentence templates (`generate.py`, three to four per
register per category). Any extractor tuned against that corpus can
learn the templates rather than the task: add a pattern for "Haven't
started X yet" and the benchmark rewards it, whether or not a real
session ever says that.

This module builds a second corpus that shares the fact pools and the
session shape with `generate.py` but shares **none of its sentence
templates**. It was written and frozen before any extractor change was
tuned against the main corpus (see REPORT_heldout.md for the commit
order). Scores here are the honest estimate of whether an improvement
generalises past the templates it was developed on; scores on the main
corpus after tuning are not.

Two things it adds that the main corpus lacks:

  - A wider template pool per register (five to seven), including the
    markdown forms assistants actually write: checkboxes, bold labels,
    emoji status markers, backticked paths.
  - Distractor sentences. The main corpus contains no text that should
    NOT be extracted apart from short user prompts, so it cannot see
    false positives from hypotheticals ("if the migration fails…"),
    negations ("no errors on the last run") or adjectival uses ("retry
    for failed requests"). Every held-out assistant turn has a chance of
    carrying one. They add no ground truth; they only cost precision.

What it still shares with the main corpus, and so cannot test: the fact
pools themselves (domain vocabulary), and the assumption that every fact
appears verbatim. The facts are sampled with a different seed.

Determinism: seeds come from `zlib.crc32`, not the built-in `hash()`,
which is salted per process for strings.

    python -m benchmarks.memorybench.heldout            # writes benchmarks/corpus_heldout/
    python -m benchmarks.memorybench.run --corpus benchmarks/corpus_heldout
"""
from __future__ import annotations

import json
import random
import zlib
from pathlib import Path

from benchmarks.memorybench.domains import DOMAINS

OUT_DIR = Path(__file__).resolve().parents[1] / "corpus_heldout"

REGISTERS = ("explicit", "semi", "implicit", "mixed")

# ── Templates — none of these strings appear in generate.py ───────────────

_COMPLETED = {
    "explicit": ["✅ {F}.", "- [x] {f}", "**Done:** {f}.", "Changes made: {f}.",
                 "Status: {f} — complete.", "Merged: {f}."],
    "semi": ["I've added {f}.", "{F} is now in place.", "{F} works now.",
             "{F} is done and tested.", "I've finished {f}.", "Just merged {f}.",
             "{F} landed in the last commit."],
    "implicit": ["With {f} sorted, the rest should go quicker.",
                 "{F} took longer than planned but it's behind us now.",
                 "Once {f} was in, the flaky tests stopped.",
                 "Crossed {f} off the list this morning.",
                 "No more worrying about {f}, that part's handled."],
}
_PENDING = {
    "explicit": ["- [ ] {f}", "**Next steps:** {f}.", "Remaining: {f}.",
                 "Open item: {f}.", "Follow-up: {f}.", "Left to do: {f}."],
    "semi": ["Next I'll pick up {f}.", "We still have to do {f}.",
             "{F} hasn't been done yet.", "I'll tackle {f} tomorrow.",
             "{F} is still outstanding.", "Up next is {f}."],
    "implicit": ["Before release, somebody needs to look at {f}.",
                 "{F} can wait until after the demo.",
                 "Let's not forget about {f}.",
                 "Parking {f} for now, it's not urgent.",
                 "At some point {f} has to happen too."],
}
_DECISION_ASSISTANT = {
    "explicit": ["Decision: {f}.", "**Decision:** {f}.", "Final choice: {f}.",
                 "We decided on {f}.", "Approach: {f}."],
    "semi": ["We'll go with {f}.", "I picked {f}.", "Opting for {f}.",
             "Sticking with {f}.", "Let's standardise on {f}."],
    "implicit": ["{F} ended up being the pragmatic option.",
                 "In the end {f} was simpler than the alternatives.",
                 "The team agreed {f} is the way forward.",
                 "Rather than overthinking it, {f} it is."],
}
_DECISION_USER = {
    "explicit": ["Go with {f}.", "Decision: {f}.", "Please use {f}."],
    "semi": ["I'd prefer {f}.", "Let's do {f}.", "How about {f}?"],
    "implicit": ["My gut says {f} is the safer bet.",
                 "Honestly {f} seems like less hassle."],
}
_FILE = {
    "explicit": ["Modified: {f}.", "Files changed: {f}.", "- `{f}`",
                 "Edited `{f}`.", "New file: {f}."],
    "semi": ["The change is in {f}.", "I touched {f} as well.",
             "Look at {f} for the details.", "Most of the edits went into {f}."],
    "implicit": ["Ended up rewriting half of {f} along the way.",
                 "The fix lives in {f}, near the top.",
                 "Had to open up {f} again for a small tweak."],
}
_ERROR = {
    "explicit": ["Failure: {f}.", "Exception: {f}.", "❌ {F}.", "Problem: {f}.",
                 "Blocker: {f}.", "**Error:** {f}."],
    "semi": ["We hit {f}.", "Seeing {f} in the logs.", "The build broke with {f}.",
             "Getting {f} on every run.", "Noticed {f} in staging."],
    "implicit": ["Everything looked green, then {f} again.",
                 "CI is unhappy — {f}.",
                 "The on-call page last night was {f}.",
                 "Tracked the flakiness down to {f}."],
}

# Sentences that must NOT produce a node. Each is a known false-positive
# shape for pattern extractors: hypothetical, negated, adjectival, generic
# explanation, or a question.
_DISTRACTORS = [
    "If the migration fails, we roll back automatically.",
    "No errors on the last run.",
    "The retry wrapper handles failed requests with exponential backoff.",
    "Let me know if you want me to keep going.",
    "I'll explain the reasoning below.",
    "Worth noting: nothing here changes the public API.",
    "That should be it for this part.",
    "We could also consider caching, but it's not needed yet.",
    "The error handling path is covered by the existing tests.",
    "Should we decide on naming later?",
    "Here's a quick summary of where things stand.",
    "Tests pass locally; CI will confirm.",
]

_USER_PROMPTS = [
    "Where do things stand?", "Continue.", "Anything I should know?",
    "What's the plan for {p}?", "Status on {p}?", "Go ahead.",
    "What's still open?", "Any surprises?", "Summarise the last hour.",
]

_OPENERS = [
    ("Can you help with {p}?", "Sure, picking up {p}."),
    ("Today we're on {p}.", "Got it, looking at {p} now."),
    ("Resume {p} please.", "Resuming {p}."),
]


def _cap(s: str) -> str:
    return s[0].upper() + s[1:] if s else s


def _render(templates: dict, register: str, rng: random.Random, fact: str) -> str:
    reg = register if register != "mixed" else rng.choice(("explicit", "semi", "implicit"))
    tpl = rng.choice(templates[reg])
    return tpl.format(f=fact, F=_cap(fact))


def _seed(*parts) -> int:
    return zlib.crc32("|".join(map(str, parts)).encode())


V1 = {
    "completed": _COMPLETED, "pending": _PENDING,
    "decision_assistant": _DECISION_ASSISTANT, "decision_user": _DECISION_USER,
    "file": _FILE, "error": _ERROR, "distractors": _DISTRACTORS,
    "user_prompts": _USER_PROMPTS, "openers": _OPENERS,
    "acks": ["Makes sense, doing that.", "OK, will do.", "Fine by me."],
}


def build_session(domain_key: str, idx: int, register: str, rng: random.Random,
                  T: dict = V1, prefix: str = "ho", label: str = "Held-out") -> dict:
    pack = DOMAINS[domain_key]
    project = rng.choice(pack["projects"])

    completed = rng.sample(pack["completed"], min(rng.randint(3, 7), len(pack["completed"])))
    pending = rng.sample(pack["pending"], min(rng.randint(1, 4), len(pack["pending"])))
    decisions = rng.sample(pack["decisions"], min(rng.randint(2, 6), len(pack["decisions"])))
    files = rng.sample(pack["files"], min(rng.randint(2, 6), len(pack["files"])))
    errors = rng.sample(pack["errors"], min(rng.randint(0, 3), len(pack["errors"])))
    user_decision = {d: rng.random() < 0.35 for d in decisions}

    opener_u, opener_a = rng.choice(T["openers"])
    messages = [
        {"role": "user", "content": opener_u.format(p=project)},
        {"role": "assistant", "content": opener_a.format(p=project)},
    ]

    events = ([("completed", f) for f in completed] + [("pending", f) for f in pending]
              + [("decision", f) for f in decisions] + [("file", f) for f in files]
              + [("error", f) for f in errors])
    rng.shuffle(events)

    i = 0
    while i < len(events):
        batch = events[i:i + rng.choice((1, 1, 2, 3))]
        i += len(batch)
        user_lines, parts = [], []
        for kind, fact in batch:
            if kind == "decision" and user_decision[fact]:
                user_lines.append(_render(T["decision_user"], register, rng, fact))
                parts.append(rng.choice(T["acks"]))
            elif kind == "decision":
                parts.append(_render(T["decision_assistant"], register, rng, fact))
            elif kind == "completed":
                parts.append(_render(T["completed"], register, rng, fact))
            elif kind == "pending":
                parts.append(_render(T["pending"], register, rng, fact))
            elif kind == "file":
                parts.append(_render(T["file"], register, rng, fact))
            else:
                parts.append(_render(T["error"], register, rng, fact))
        if rng.random() < 0.5:
            parts.insert(rng.randint(0, len(parts)), rng.choice(T["distractors"]))
        # Markdown-style templates (checkbox, bullet) only read as intended
        # on their own line; everything else joins as prose.
        sep = "\n" if any(p.startswith(("- ", "✅", "❌", "**")) for p in parts) else " "
        user = " ".join(user_lines) if user_lines else rng.choice(T["user_prompts"]).format(p=project)
        messages.append({"role": "user", "content": user})
        messages.append({"role": "assistant", "content": sep.join(parts)})

    return {
        "id": f"{prefix}_{domain_key.replace('/', '_')}_{idx:03d}",
        "origin": "synthetic",
        "domain": domain_key,
        "register": register,
        "notes": (f"{label} session — templates disjoint from generate.py, with "
                  f"distractor sentences. domain={domain_key!r}, register={register!r}."),
        "messages": messages,
        "ground_truth": {"completed_tasks": completed, "pending_tasks": pending,
                         "decisions": decisions, "files": files, "errors": errors},
    }


def generate(n: int, seed: int = 20260924, T: dict = V1, prefix: str = "ho",
             label: str = "Held-out") -> list[dict]:
    domain_keys = list(DOMAINS)
    counters = {k: 0 for k in domain_keys}
    out = []
    for i in range(n):
        dk = domain_keys[i % len(domain_keys)]
        # Offset register by domain so a domain does not always pair with
        # the same register.
        reg = REGISTERS[(i + i // len(domain_keys)) % len(REGISTERS)]
        counters[dk] += 1
        out.append(build_session(dk, counters[dk], reg,
                                 random.Random(_seed(seed, dk, reg, counters[dk])),
                                 T=T, prefix=prefix, label=label))
    return out


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-n", type=int, default=80)
    ap.add_argument("--seed", type=int, default=20260924)
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sessions = generate(args.n, args.seed)
    for s in sessions:
        (out / f"{s['id']}.json").write_text(json.dumps(s, indent=1, ensure_ascii=False) + "\n")
    print(f"Wrote {len(sessions)} sessions to {out}")


if __name__ == "__main__":
    main()
