"""
Labelled session corpus for the multi-method memory benchmark.

FORMAT
------
One JSON file per session in `benchmarks/corpus/`:

```json
{
  "id": "fastapi_auth",
  "origin": "synthetic",
  "domain": "backend/python",
  "register": "explicit",
  "notes": "free text — what this session is meant to stress",
  "messages": [{"role": "user", "content": "..."}],
  "ground_truth": {
    "completed_tasks": ["..."],
    "pending_tasks":   ["..."],
    "decisions":       ["..."],
    "files":           ["..."],
    "errors":          ["..."]
  }
}
```

This is the same format the product repo's `benchmarks/eval` harness uses,
so the 14 sessions committed there load here unchanged and the two
harnesses stay comparable.

`register` is an addition specific to this benchmark. It records how
explicitly the session states its facts — `explicit`, `semi` or
`implicit` — because that single variable dominates the score of every
pattern-based memory method, and a corpus that does not record it will
report one aggregate number that hides the whole story. It is optional;
sessions without it are reported as `unspecified`.

LABELLING RULE
--------------
Identical to the product harness, and mechanical rather than editorial:

* **completed_tasks** — work a turn states as finished.
* **pending_tasks** — work a turn states as in progress or planned.
* **decisions** — a choice a turn commits to, or a user instruction
  naming the technology to use. Superseded choices are still decisions.
* **files** — a path named in a turn.
* **errors** — a distinct failure, exception, status code or stated
  malfunction named in a turn, counted once however often it recurs.

Two constraints make it checkable:

1. **Grounded.** Every label must be recoverable from a *single*
   message. `validate_grounding()` enforces this and the runner refuses
   to score a corpus that fails it. An ungrounded label is unreachable
   for every method, so it caps recall at a number no implementation
   change can move — and it does so silently, which is worse.
2. **Exhaustive.** If the rule matches, it gets labelled. Cherry-picking
   which of several stated decisions "counts" turns precision into a
   measure of the annotator's taste.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from benchmarks.memorybench.metrics import covers

CORPUS_DIR = Path(__file__).resolve().parents[1] / "corpus"

VALID_ORIGINS = ("synthetic", "real")
CATEGORIES = ("completed_tasks", "pending_tasks", "decisions", "files", "errors")


class CorpusError(ValueError):
    """A corpus file is malformed. Raised rather than skipped — a
    silently-dropped session would quietly change every score."""


@dataclass
class Session:
    id: str
    origin: str
    domain: str
    messages: list[dict]
    ground_truth: dict
    register: str = "unspecified"
    notes: str = ""
    path: Path | None = field(default=None, repr=False)

    @property
    def turns(self) -> int:
        return len(self.messages)

    @property
    def label_count(self) -> int:
        return sum(len(v) for v in self.ground_truth.values())

    def expected(self, category: str) -> list[str]:
        return list(self.ground_truth.get(category, []))


def _validate(raw: dict, path: Path) -> Session:
    for key in ("id", "origin", "messages", "ground_truth"):
        if key not in raw:
            raise CorpusError(f"{path.name}: missing required key {key!r}")

    if raw["origin"] not in VALID_ORIGINS:
        raise CorpusError(
            f"{path.name}: origin must be one of {VALID_ORIGINS}, got {raw['origin']!r}"
        )

    msgs = raw["messages"]
    if not isinstance(msgs, list) or not msgs:
        raise CorpusError(f"{path.name}: messages must be a non-empty list")
    for i, m in enumerate(msgs):
        if not isinstance(m, dict) or "role" not in m or "content" not in m:
            raise CorpusError(f"{path.name}: message {i} needs 'role' and 'content'")

    gt = raw["ground_truth"]
    unknown = set(gt) - set(CATEGORIES)
    if unknown:
        raise CorpusError(
            f"{path.name}: unknown ground_truth categories {sorted(unknown)}; "
            f"valid: {list(CATEGORIES)}"
        )
    for cat, items in gt.items():
        if not isinstance(items, list) or any(not isinstance(x, str) for x in items):
            raise CorpusError(f"{path.name}: ground_truth.{cat} must be a list of strings")

    return Session(
        id=raw["id"],
        origin=raw["origin"],
        domain=raw.get("domain", "unspecified"),
        messages=msgs,
        ground_truth=gt,
        register=raw.get("register", "unspecified"),
        notes=raw.get("notes", ""),
        path=path,
    )


def load(corpus_dir: str | Path | None = None) -> list[Session]:
    """Load every session in `corpus_dir`, sorted by id so runs are diffable."""
    d = Path(corpus_dir) if corpus_dir else CORPUS_DIR
    if not d.exists():
        raise CorpusError(f"corpus directory not found: {d}")

    files = sorted(d.glob("*.json"))
    if not files:
        raise CorpusError(f"no .json session files in {d}")

    sessions = []
    for f in files:
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise CorpusError(f"{f.name}: invalid JSON — {e}") from e
        sessions.append(_validate(raw, f))

    ids = [s.id for s in sessions]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise CorpusError(f"duplicate session ids in {d}: {sorted(dupes)}")
    return sessions


def ungrounded(session: Session, threshold: float = 0.6) -> list[tuple[str, str]]:
    """Ground-truth labels of `session` that no single message supports.

    Checked one message at a time, not against the pooled transcript:
    tokens scattered over ten turns are not evidence that any turn stated
    the fact, and pooling them would let almost any label pass.

    Uses the same `covers()` relation the scorer uses, so "grounded"
    means exactly "a method that copied this message verbatim would be
    scored as having found this label".
    """
    bad = []
    for cat in CATEGORIES:
        for label in session.expected(cat):
            if not any(covers(m.get("content", ""), label, threshold)
                       for m in session.messages):
                bad.append((cat, label))
    return bad


def validate_grounding(sessions: list[Session], threshold: float = 0.6) -> None:
    """Raise if any label in any session is unsupported by its transcript."""
    problems = []
    for s in sessions:
        for cat, label in ungrounded(s, threshold):
            problems.append(f"  {s.id}.{cat}: {label!r}")
    if problems:
        raise CorpusError(
            f"ground-truth labels not supported by their transcript ({len(problems)}):\n"
            + "\n".join(problems[:40])
            + ("\n  …" if len(problems) > 40 else "")
            + "\n\nEvery label must be recoverable from a single message."
        )


def describe(sessions: list[Session]) -> str:
    """One-line provenance summary, printed above every report so a
    number is never quoted without its sample size and origin."""
    real = sum(1 for s in sessions if s.origin == "real")
    synth = len(sessions) - real
    turns = sum(s.turns for s in sessions)
    labels = sum(s.label_count for s in sessions)
    domains = sorted({s.domain for s in sessions})
    registers = sorted({s.register for s in sessions})
    return (
        f"{len(sessions)} sessions ({synth} synthetic, {real} real) · "
        f"{turns} turns · {labels} labelled items · "
        f"{len(domains)} domains · registers: {', '.join(registers)}"
    )
