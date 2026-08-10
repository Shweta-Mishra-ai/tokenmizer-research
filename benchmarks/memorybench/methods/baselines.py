"""
Naive baselines. None of these do typed extraction, so all three are
scored the same way: whatever raw text they keep is split into
sentences, and that flat sentence list stands in for every one of the
five ground-truth categories. That's not a handicap applied to make
them lose — it's the honest consequence of a method that has no notion
of "this sentence is a decision". Scoring them against every category
with their one untyped list is the fairest read of what they actually
retain.
"""
from __future__ import annotations

from benchmarks.memorybench.methods.common import (
    MethodResult, Timer, count_tokens, split_sentences,
)

TOKEN_BUDGET = 300  # naive_truncation and sliding_window both target this


def _untyped_result(name: str, kept_text: str, ms: float) -> MethodResult:
    sentences = split_sentences(kept_text)
    return MethodResult(
        completed_tasks=sentences, pending_tasks=sentences, decisions=sentences,
        files=sentences, errors=sentences,
        resume_text=kept_text, resume_tokens=count_tokens(kept_text),
        extract_ms=ms, node_count=len(sentences),
    )


NAME_TRUNCATION = "naive_truncation"
DESCRIPTION_TRUNCATION = f"Keep the last ~{TOKEN_BUDGET} tokens of raw transcript verbatim, drop the rest."


def extract_truncation(session) -> MethodResult:
    with Timer() as t:
        kept, total = [], 0
        for msg in reversed(session.messages):
            tok = count_tokens(msg["content"])
            if total + tok > TOKEN_BUDGET:
                break
            kept.append(msg["content"])
            total += tok
        kept_text = "\n".join(reversed(kept))
    return _untyped_result(NAME_TRUNCATION, kept_text, t.ms)


NAME_SLIDING = "sliding_window_10"
DESCRIPTION_SLIDING = "Keep the last 10 raw messages verbatim, drop everything earlier."


def extract_sliding_window(session, window: int = 10) -> MethodResult:
    with Timer() as t:
        kept = session.messages[-window:]
        kept_text = "\n".join(m["content"] for m in kept)
    return _untyped_result(NAME_SLIDING, kept_text, t.ms)


NAME_SUMMARY = "naive_summary"
DESCRIPTION_SUMMARY = "Concatenate the whole transcript and truncate to the first ~120 words."


def extract_naive_summary(session, word_budget: int = 120) -> MethodResult:
    with Timer() as t:
        all_text = " ".join(m["content"] for m in session.messages)
        kept_text = " ".join(all_text.split()[:word_budget])
    return _untyped_result(NAME_SUMMARY, kept_text, t.ms)
