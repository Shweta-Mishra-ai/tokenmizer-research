"""
GraphRAG-style entity/community graph (deterministic reimplementation).

Microsoft's GraphRAG (Edge et al., 2024) builds its graph for a
different job than session memory: it extracts named entities and
relations from a corpus to answer broad thematic questions over
*communities* of entities, not to track a task's lifecycle. It has no
concept of "this task is done vs. pending" — that status distinction
simply is not part of what an entity-relation graph represents.

Reproduced here: strong entity extraction (files, named technologies —
i.e. exactly `decisions` and `files`, which are naturally entity-shaped)
via a wider net than the shared pattern family, but task status
collapsed to a single weak signal. Completed and pending tasks are both
approximated from generic "topic sentence" extraction that has no verb
awareness, so it catches far fewer of them than a method that was
actually built to track status. This predicts the shape GraphRAG-style
should show in the results: comparatively strong on files/decisions,
comparatively weak on completed/pending task recall — a genuine
strategy tradeoff, not a bug.
"""
from __future__ import annotations

import re

from benchmarks.memorybench.methods.common import (
    MethodResult, Timer, build_resume, count_tokens,
    normalize, split_sentences, FILE_PAT,
)

NAME = "graphrag_style"
DESCRIPTION = (
    "Entity/community graph — wide net on files and named-technology "
    "entities (its actual design target); tasks have no status concept "
    "in this strategy, so completion state is only weakly recovered."
)

_DECISION_VERB = re.compile(
    r'(?:Decided|Using|Chose|Selected|Going with|Settled on|Use|Let\'?s go with|'
    r'Build it with)[:\s]+', re.I,
)
# Weak task-status signal: only the two most common explicit verbs,
# reflecting that status was never the extraction target.
_WEAK_DONE = re.compile(r'(?:Completed|Done)[:\s]+(.+?)(?:\.|$)', re.I)
_WEAK_PENDING = re.compile(r'(?:TODO|Next)[:\s]+(.+?)(?:\.|$)', re.I)


def extract(session) -> MethodResult:
    with Timer() as t:
        completed, pending, decisions, files, errors = set(), set(), set(), set(), set()

        for m in session.messages:
            text = m["content"]

            for fm in FILE_PAT.finditer(text):
                files.add(fm.group(1).lower())

            for sent in split_sentences(text):
                dm = _DECISION_VERB.search(sent)
                if dm:
                    rest = sent[dm.end():].strip().rstrip(".")
                    if rest:
                        decisions.add(normalize(rest)[:80])

            for wm in _WEAK_DONE.finditer(text):
                completed.add(normalize(wm.group(1))[:80])
            for wm in _WEAK_PENDING.finditer(text):
                pending.add(normalize(wm.group(1))[:80])

            # errors: GraphRAG has no lifecycle concept for these either,
            # but a named failure is still an entity-shaped fact, so it
            # gets the same broad sentence-level net as decisions.
            for sent in split_sentences(text):
                if re.search(r'\b(error|bug|issue|ran into|crash|fail\w*)\b', sent, re.I):
                    cleaned = re.sub(
                        r'^.*?\b(?:error|bug|issue|ran into|crash|fail\w*)\b[:\s]*',
                        '', sent, flags=re.I,
                    ).strip().rstrip(".")
                    if cleaned:
                        errors.add(normalize(cleaned)[:80])

        cats_sets = {
            "completed": completed, "pending": pending, "decisions": decisions,
            "files": files, "errors": errors,
        }
        resume = build_resume(NAME, cats_sets)

    return MethodResult(
        completed_tasks=sorted(completed),
        pending_tasks=sorted(pending),
        decisions=sorted(decisions),
        files=sorted(files),
        errors=sorted(errors),
        resume_text=resume,
        resume_tokens=count_tokens(resume),
        extract_ms=t.ms,
        node_count=sum(len(v) for v in cats_sets.values()),
    )
