"""
MemGPT-style paged memory (deterministic reimplementation).

MemGPT's defining move (Packer et al., 2023, "MemGPT: Towards LLMs as
Operating Systems") is a two-tier memory split: a small **core context**
the model always sees, and an **archival store** the model must issue an
explicit tool call to search. Facts that scroll out of core are not
gone, but they are not *spontaneously recalled* either — they only
resurface if something prompts a targeted archival query.

This reimplementation keeps that asymmetry and nothing else: it does
not attempt the paging *policy* (MemGPT evicts by an LLM-driven
relevance judgment; there is no LLM here), just the *consequence* —
extraction only runs over a bounded recent window, and older turns
contribute zero facts unless the harness happens to re-query them,
which nothing here does. Everything that ages out of the window is
simply unavailable, which is the behavior worth measuring: recall on
early-session facts should degrade as sessions get longer, in a way
none of the other methods here reproduce.
"""
from __future__ import annotations

from benchmarks.memorybench.methods.common import (
    MethodResult, Timer, build_resume, count_tokens, extract_typed,
)

NAME = "memgpt_style"
DESCRIPTION = (
    "Core/archival paging — only the most recent ~40% of turns are in the "
    "always-visible core context; everything older requires an archival "
    "query this benchmark never issues, so it contributes nothing."
)

CORE_FRACTION = 0.4
MIN_CORE_MESSAGES = 6


def extract(session) -> MethodResult:
    with Timer() as t:
        msgs = session.messages
        core_n = max(MIN_CORE_MESSAGES, round(len(msgs) * CORE_FRACTION))
        core = msgs[-core_n:] if core_n < len(msgs) else msgs

        text = "\n".join(m["content"] for m in core)
        cats = extract_typed(text)
        resume = build_resume(NAME, cats)

    return MethodResult(
        completed_tasks=sorted(cats["completed"]),
        pending_tasks=sorted(cats["pending"]),
        decisions=sorted(cats["decisions"]),
        files=sorted(cats["files"]),
        errors=sorted(cats["errors"]),
        resume_text=resume,
        resume_tokens=count_tokens(resume),
        extract_ms=t.ms,
        node_count=sum(len(v) for v in cats.values()),
    )
