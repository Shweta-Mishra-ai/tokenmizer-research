"""
Shared primitives for the method implementations in this package.

Every non-baseline method here is an independent, deterministic
reimplementation of a published *strategy*, not a wrapper around the
named vendor library — MemGPT, Mem0, Graphiti and GraphRAG all require
an LLM call to do their real extraction, and this benchmark runs with
no API key and no network dependency on an LLM provider. What's
reproduced instead is the structural behavior the strategy is known
for: MemGPT's core/archival paging, Mem0's flat undifferentiated fact
store, Graphiti's temporal never-delete edges, GraphRAG's untyped
entity graph. Each method module says this again at the top, because a
benchmark that lets "MemGPT-style" quietly get read as "MemGPT" is
worse than one that over-explains.

All five methods here (plus TokenMizer) use variants of the same regex
family defined below, so that differences in the results table reflect
differences in *strategy* (windowing, typing, supersede handling) and
not differences in regex quality between otherwise-similar heuristic
extractors. That control is what makes the comparison mean something —
if TokenMizer used entirely different patterns from its competitors,
a win would tell you as much about the shared vocabulary of the
synthetic corpus as about the strategy actually being scored.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field


def count_tokens(text: str) -> int:
    """char/4 estimate — no tokenizer dependency, consistent across
    every method including the real TokenMizer subprocess, which
    reports its own tiktoken-or-fallback count separately."""
    return max(1, len(text) // 4)


@dataclass
class MethodResult:
    completed_tasks: list = field(default_factory=list)
    pending_tasks: list = field(default_factory=list)
    decisions: list = field(default_factory=list)
    files: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    resume_text: str = ""
    resume_tokens: int = 0
    extract_ms: float = 0.0
    node_count: int = 0

    def as_categories(self) -> dict:
        return {
            "completed_tasks": self.completed_tasks,
            "pending_tasks": self.pending_tasks,
            "decisions": self.decisions,
            "files": self.files,
            "errors": self.errors,
        }


class Timer:
    def __enter__(self):
        self.t0 = time.monotonic()
        return self

    def __exit__(self, *a):
        self.ms = (time.monotonic() - self.t0) * 1000


# ── Shared regex family ──────────────────────────────────────────────────
# Deliberately not the product repo's actual patterns (those live in
# tokenmizer/graph_memory/hybrid_extractor.py and are exercised only via
# the real subprocess in tokenmizer_real.py). This is the "reasonable
# heuristic engineer" baseline pattern set that MemGPT/Mem0/Graphiti/
# GraphRAG-style methods below all build on.

COMPLETED_PAT = re.compile(
    r'(?:Completed|Done|Finished|Implemented|Created|Fixed|Added|Deployed|'
    r'Published|Resolved|Migrated|Launched|Shipped|Updated|Wrapped up|'
    r'Shipped)[:\s]+(.+?)(?:\.|$)',
    re.I,
)
INPROGRESS_PAT = re.compile(
    r'(?:Working on|Adding|Building|Setting up|Implementing|Integrating|'
    r'is next on)[:\s]+(.+?)(?:\.|$)',
    re.I,
)
PENDING_PAT = re.compile(
    r'(?:Need to|TODO|Will|Next|Pending|Still need)[:\s]+(.+?)(?:\.|$)',
    re.I,
)
DECISION_PAT = re.compile(
    r'(?:Decided|Using|Chose|Selected|Running|Going with|Settled on|Tools?|'
    r'Use|Let\'?s go with|Build it with)[:\s]+(.+?)(?:\.|$)',
    re.I,
)
FILE_PAT = re.compile(
    r'([\w./][\w./\-]*\.(?:py|js|ts|jsx|tsx|yaml|yml|json|md|go|rs|tf|toml|'
    r'sh|env|sql|swift|proto|avsc|hcl|tex|cfg|lock|txt|mod))',
    re.I,
)
ERROR_PAT = re.compile(
    r'(?:Error|Bug|Issue|Ran into|Hit (?:a snag|an issue)|we\'?re seeing)[:\s]+(.+?)(?:\.|$)',
    re.I,
)

_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+')


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]


def normalize(label: str) -> str:
    return re.sub(r'\s+', ' ', label).strip().rstrip('.').lower()


def extract_typed(text: str) -> dict[str, set]:
    """Run the shared regex family over `text`, typed by category."""
    completed, inprogress, pending, decisions, files, errors = (
        set(), set(), set(), set(), set(), set()
    )
    for m in COMPLETED_PAT.finditer(text):
        completed.add(normalize(m.group(1))[:80])
    for m in INPROGRESS_PAT.finditer(text):
        inprogress.add(normalize(m.group(1))[:80])
    for m in PENDING_PAT.finditer(text):
        pending.add(normalize(m.group(1))[:80])
    for m in DECISION_PAT.finditer(text):
        decisions.add(normalize(m.group(1))[:80])
    for m in FILE_PAT.finditer(text):
        files.add(m.group(1).lower())
    for m in ERROR_PAT.finditer(text):
        errors.add(normalize(m.group(1))[:80])
    return {
        "completed": completed,
        "pending": pending | inprogress,
        "decisions": decisions,
        "files": files,
        "errors": errors,
    }


def build_resume(name: str, cats: dict[str, set], limits: dict[str, int] | None = None) -> str:
    limits = limits or {"completed": 8, "pending": 5, "decisions": 8, "files": 6, "errors": 5}
    lines = [f"[{name}]"]
    if cats.get("completed"):
        lines.append("DONE: " + ", ".join(list(cats["completed"])[:limits["completed"]]))
    if cats.get("pending"):
        lines.append("PENDING: " + ", ".join(list(cats["pending"])[:limits["pending"]]))
    if cats.get("decisions"):
        lines.append("DECIDED: " + ", ".join(list(cats["decisions"])[:limits["decisions"]]))
    if cats.get("files"):
        lines.append("FILES: " + ", ".join(list(cats["files"])[:limits["files"]]))
    if cats.get("errors"):
        lines.append("ERRORS: " + ", ".join(list(cats["errors"])[:limits["errors"]]))
    return "\n".join(lines)
