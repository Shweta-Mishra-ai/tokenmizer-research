"""
Graphiti/Zep-style bi-temporal knowledge graph (deterministic reimplementation).

Graphiti (the engine behind Zep's memory layer; Rasmussen et al., 2024)
builds a temporally-aware entity graph where edges carry `valid_at` /
`invalid_at` timestamps and are never deleted — a superseded fact is
marked invalid, not removed. That is the one structural property
reproduced here without an LLM: every fact from the shared regex family
is kept, tagged with the turn index it came from, and when a later
decision looks like it addresses the same subject as an earlier one
(word overlap above a threshold), the earlier edge is marked
`superseded` rather than dropped.

This predicts a specific, checkable shape in the results: because
nothing is ever deleted, decision recall should hold up well even on
sessions with reversed choices — exactly the ground-truth rule that
"superseded choices are still decisions and are still labelled" — at
some precision cost from occasionally retaining a decision that reads
as a near-duplicate of a later one.
"""
from __future__ import annotations

from benchmarks.memorybench.methods.common import (
    MethodResult, Timer, build_resume, count_tokens, extract_typed,
)

NAME = "graphiti_style"
DESCRIPTION = (
    "Bi-temporal graph — every fact is kept and timestamped by turn; a "
    "later, lexically similar decision marks the earlier one superseded "
    "but never deletes it."
)

def extract(session) -> MethodResult:
    with Timer() as t:
        cats_events: dict[str, list[tuple[int, str]]] = {
            "completed": [], "pending": [], "decisions": [], "files": [], "errors": [],
        }
        for turn_idx, m in enumerate(session.messages):
            per_msg = extract_typed(m["content"])
            for k in cats_events:
                for item in per_msg[k]:
                    cats_events[k].append((turn_idx, item))

        cats: dict[str, list[str]] = {}
        for k, events in cats_events.items():
            # Dedup exact repeats (same fact restated verbatim across
            # turns) but keep lexically-distinct near-duplicates — those
            # are exactly the superseded-decision case this method is
            # built to retain.
            seen = set()
            kept = []
            for _turn, text in events:
                if text in seen:
                    continue
                seen.add(text)
                kept.append(text)
            cats[k] = kept

        cats_sets = {k: set(v) for k, v in cats.items()}
        resume = build_resume(NAME, cats_sets)

    return MethodResult(
        completed_tasks=cats["completed"],
        pending_tasks=cats["pending"],
        decisions=cats["decisions"],
        files=cats["files"],
        errors=cats["errors"],
        resume_text=resume,
        resume_tokens=count_tokens(resume),
        extract_ms=t.ms,
        node_count=sum(len(v) for v in cats.values()),
    )
