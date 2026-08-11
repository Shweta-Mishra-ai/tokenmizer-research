"""
Mem0-style flat fact store (deterministic reimplementation).

Mem0 (Chhikara et al., 2025) extracts short natural-language "memories"
from a conversation and stores them as a flat, undifferentiated list —
no schema, no node types, no graph edges. Its real system uses an LLM
both to extract each fact and to decide, memory-by-memory, whether a new
fact ADDs, UPDATEs or DELETEs an existing one (its conflict-resolution
step). Reimplemented deterministically here: every fact from the shared
regex family is kept in one pool across the whole transcript (no
windowing, unlike MemGPT-style), and conflict resolution is approximated
as last-write-wins between near-duplicate facts — decided by word
overlap, not semantics, which is the honest ceiling of doing this
without an LLM in the loop.

The structural weakness this reproduces: with no typed relationships,
"decided X, then later decided Y instead" collapses to two loosely
related strings unless they're lexically close enough for the
near-duplicate filter to catch — Mem0 has no notion of SUPERSEDES the
way a temporal graph does, and neither does this.
"""
from __future__ import annotations

from benchmarks.memorybench.methods.common import (
    MethodResult, Timer, build_resume, count_tokens, extract_typed,
)


NAME = "mem0_style"
DESCRIPTION = (
    "Flat fact store, whole transcript, last-write-wins dedup on lexically "
    "similar facts — no node types, no graph edges, no supersede tracking."
)

_DEDUP_OVERLAP = 0.75


def _dedup_last_write_wins(items_in_order: list[str]) -> list[str]:
    """Later items win over earlier lexically-similar ones — the closest
    a bag of strings can get to Mem0's UPDATE operation without an LLM
    to judge semantic equivalence."""
    kept: list[str] = []
    for item in items_in_order:
        wi = set(item.split())
        dupe_at = None
        for idx, existing in enumerate(kept):
            we = set(existing.split())
            if not wi or not we:
                continue
            smaller = wi if len(wi) <= len(we) else we
            if len(wi & we) / len(smaller) >= _DEDUP_OVERLAP:
                dupe_at = idx
                break
        if dupe_at is not None:
            kept[dupe_at] = item  # last write wins
        else:
            kept.append(item)
    return kept


def extract(session) -> MethodResult:
    with Timer() as t:
        cats = {"completed": [], "pending": [], "decisions": [], "files": [], "errors": []}
        # Process turn by turn (not one pooled blob) so "last write wins"
        # has a real chronological order to resolve against.
        for m in session.messages:
            per_msg = extract_typed(m["content"])
            for k in cats:
                cats[k].extend(sorted(per_msg[k]))  # sorted only for determinism within a turn

        for k in cats:
            cats[k] = _dedup_last_write_wins(cats[k])

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
