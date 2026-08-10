"""
Synthetic corpus generator.

Produces labelled sessions by sampling facts from the domain packs in
`domains.py` and rendering each fact into a message that contains the
fact's canonical text **verbatim**. That is the whole grounding
strategy: `corpus.covers()` accepts a substring match, so embedding the
literal fact string inside a longer sentence makes every generated
label grounded by construction, regardless of how the surrounding
sentence is phrased.

What varies between sessions is the phrasing around that fact — the
`register`:

  explicit — canonical markers a regex was written against directly:
             "Completed: X.", "Decided: X.", "TODO: X."
  semi     — ordinary sentences that still name the fact plainly:
             "Wrapped up X earlier.", "Going with X for this."
  implicit — the fact arrives inside reasoning or a subordinate clause,
             no marker word, sometimes past a hedge or a discourse
             connective: "After going back and forth, X felt like the
             right call given the constraints."
  mixed    — each fact in the session independently rolls explicit,
             semi or implicit — the realistic case, since nobody writes
             an entire session in one register.

This directly targets what the eval documents as the main external
validity gap in the committed 14-session corpus: pattern-based
extractors are fitted to `explicit`-style text, and every method's
score should be expected to fall as register moves toward `implicit`.
Reporting per-register breakdowns (done in the runner) makes that
visible instead of averaging it away.

Determinism: every session is generated from `random.Random(seed)` with
a seed derived from its own id, so re-running this script reproduces
byte-identical output. That matters because the corpus is committed —
regenerating it should be a no-op unless this file changes.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from textwrap import dedent

from benchmarks.memorybench.domains import DOMAINS

OUT_DIR = Path(__file__).resolve().parents[1] / "corpus"

REGISTERS = ("explicit", "semi", "implicit", "mixed")

# ── Fact -> sentence templates ────────────────────────────────────────────

_COMPLETED = {
    "explicit": ["Completed: {f}.", "Done: {f}.", "Implemented: {f}.", "Finished: {f}."],
    "semi": ["Finished up {f} earlier today.", "Wrapped up {f}, all green now.",
             "Shipped {f}.", "{F} is in and working."],
    "implicit": ["So I went ahead and got {f} working, then moved on.",
                 "That's out of the way now — {f} — onto the next thing.",
                 "Turns out {f} wasn't as bad as expected, it's sorted.",
                 "Between the last two messages I also got {f} handled."],
}
_PENDING = {
    "explicit": ["TODO: {f}.", "Next: {f}.", "Pending: {f}.", "Still need: {f}."],
    "semi": ["Still need to get to {f}.", "Haven't started {f} yet, soon though.",
              "{F} is next on the list."],
    "implicit": ["We'll circle back to {f} once the current thing lands.",
                 "I keep meaning to get to {f} but other things keep jumping the queue.",
                 "Not today, but {f} is on my mind for later this week."],
}
_DECISION_ASSISTANT = {
    "explicit": ["Decided: {f}.", "Using: {f}.", "Chose: {f}.", "Selected: {f}."],
    "semi": ["Going with {f} for this.", "We're leaning toward {f}.",
              "Settled on {f}."],
    "implicit": ["After going back and forth, {f} felt like the right call given the constraints.",
                 "It wasn't an obvious choice, but {f} won out in the end.",
                 "Weighing the tradeoffs, {f} made the most sense here."],
}
_DECISION_USER = {
    "explicit": ["Use {f}.", "Let's go with {f}.", "Build it with {f}."],
    "semi": ["I think we should use {f} here.", "Can we do this with {f}?"],
    "implicit": ["Given what happened last time, maybe {f} is worth trying.",
                 "Not sure if it matters, but {f} would probably fit better."],
}
_FILE = {
    "explicit": ["Updated: {f}.", "Files: {f}.", "Created: {f}."],
    "semi": ["Made the changes over in {f}.", "Most of it is in {f} now."],
    "implicit": ["The bulk of the diff ended up living in {f}, of all places.",
                 "Spent most of the afternoon in {f} chasing this down."],
}
_ERROR = {
    "explicit": ["Error: {f}.", "Bug: {f}.", "Issue: {f}."],
    "semi": ["Ran into {f}.", "Hit a snag: {f}.", "We're seeing {f}."],
    "implicit": ["Things were fine until {f} showed up out of nowhere.",
                 "Not sure what changed, but now there's {f}.",
                 "Somewhere in there we picked up {f} and it's been a pain."],
}

_USER_PROMPTS = [
    "What's the status?", "What's next on this?", "Any issues so far?",
    "Where are we on {p}?", "Keep going.", "What did you decide on the approach?",
    "Anything blocking?", "Give me an update.", "How's {p} coming along?",
    "What's left before we can call this done?",
]


def _cap(s: str) -> str:
    return s[0].upper() + s[1:] if s else s


def _render(templates: dict, register: str, rng: random.Random, fact: str) -> str:
    reg = register if register != "mixed" else rng.choice(("explicit", "semi", "implicit"))
    tpl = rng.choice(templates[reg])
    return tpl.format(f=fact, F=_cap(fact))


def _session_id(domain_key: str, idx: int) -> str:
    slug = domain_key.replace("/", "_")
    return f"gen_{slug}_{idx:03d}"


def build_session(domain_key: str, idx: int, register: str, rng: random.Random) -> dict:
    pack = DOMAINS[domain_key]
    project = rng.choice(pack["projects"])

    n_completed = rng.randint(3, 7)
    n_pending = rng.randint(1, 4)
    n_decisions = rng.randint(2, 6)
    n_files = rng.randint(2, 6)
    n_errors = rng.randint(0, 3)

    completed = rng.sample(pack["completed"], min(n_completed, len(pack["completed"])))
    pending = rng.sample(pack["pending"], min(n_pending, len(pack["pending"])))
    decisions = rng.sample(pack["decisions"], min(n_decisions, len(pack["decisions"])))
    files = rng.sample(pack["files"], min(n_files, len(pack["files"])))
    errors = rng.sample(pack["errors"], min(n_errors, len(pack["errors"])))

    # Roughly a third of decisions arrive as a user instruction rather
    # than an assistant statement — the labelling rule counts both, and
    # a corpus that only ever has the assistant decide would understate
    # how often extractors must read the user turn.
    user_decision_flags = [rng.random() < 0.35 for _ in decisions]

    messages = [
        {"role": "user", "content": f"Let's work on {project}."},
        {"role": "assistant", "content": f"Sounds good, starting on {project} now."},
    ]

    events: list[tuple[str, str]] = (
        [("completed", f) for f in completed]
        + [("pending", f) for f in pending]
        + [("decision", f) for f in decisions]
        + [("file", f) for f in files]
        + [("error", f) for f in errors]
    )
    rng.shuffle(events)

    # Group into assistant turns of 1-2 facts each, interleaved with
    # short user prompts — a real session is not one fact per turn.
    i = 0
    while i < len(events):
        batch = events[i:i + rng.choice((1, 1, 2))]
        i += len(batch)

        default_user_line = rng.choice(_USER_PROMPTS).format(p=project)
        user_decision_lines = []
        assistant_parts = []
        for kind, fact in batch:
            if kind == "decision":
                idx_d = decisions.index(fact)
                if user_decision_flags[idx_d]:
                    # Carries the decision on the user turn instead of the
                    # assistant turn. Appended, never overwritten — a batch
                    # can contain more than one such decision, and replacing
                    # the user line each time would silently drop every
                    # fact but the last one from ever appearing in a message.
                    user_decision_lines.append(_render(_DECISION_USER, register, rng, fact))
                    assistant_parts.append(rng.choice([
                        "Sounds good, going with that.", "Agreed, that works.",
                        "OK, running with it.",
                    ]))
                    continue
                assistant_parts.append(_render(_DECISION_ASSISTANT, register, rng, fact))
            elif kind == "completed":
                assistant_parts.append(_render(_COMPLETED, register, rng, fact))
            elif kind == "pending":
                assistant_parts.append(_render(_PENDING, register, rng, fact))
            elif kind == "file":
                assistant_parts.append(_render(_FILE, register, rng, fact))
            elif kind == "error":
                assistant_parts.append(_render(_ERROR, register, rng, fact))

        user_line = " ".join(user_decision_lines) if user_decision_lines else default_user_line
        messages.append({"role": "user", "content": user_line})
        messages.append({"role": "assistant", "content": " ".join(assistant_parts)})

    return {
        "id": _session_id(domain_key, idx),
        "origin": "synthetic",
        "domain": domain_key,
        "register": register,
        "notes": (
            f"Generated session — domain pack {domain_key!r}, register={register!r}. "
            "Facts are embedded verbatim in each message, so every ground-truth "
            "label is substring-grounded regardless of surrounding phrasing."
        ),
        "messages": messages,
        "ground_truth": {
            "completed_tasks": completed,
            "pending_tasks": pending,
            "decisions": decisions,
            "files": files,
            "errors": errors,
        },
    }


def generate(n: int, seed: int = 20260810) -> list[dict]:
    """Generate `n` sessions, round-robin across domains and registers."""
    domain_keys = list(DOMAINS)
    sessions = []
    counter_per_domain = {k: 0 for k in domain_keys}

    for i in range(n):
        domain_key = domain_keys[i % len(domain_keys)]
        register = REGISTERS[i % len(REGISTERS)]
        counter_per_domain[domain_key] += 1
        idx = counter_per_domain[domain_key]
        seed_i = seed + hash((domain_key, register, idx)) % 1_000_003
        rng = random.Random(seed_i)
        sessions.append(build_session(domain_key, idx, register, rng))

    return sessions


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-n", type=int, default=86, help="number of sessions to generate")
    ap.add_argument("--seed", type=int, default=20260810)
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    sessions = generate(args.n, args.seed)
    for s in sessions:
        (out / f"{s['id']}.json").write_text(json.dumps(s, indent=1) + "\n")

    print(f"Wrote {len(sessions)} sessions to {out}")


if __name__ == "__main__":
    main()
