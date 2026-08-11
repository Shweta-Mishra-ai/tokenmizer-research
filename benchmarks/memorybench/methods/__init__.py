"""
Method registry for the multi-method memory benchmark.

`REGISTRY` maps a method name to a `(extract_fn, description)` pair.
`extract_fn(session) -> MethodResult`. Adding a method means writing one
module with an `extract(session)` function and registering it here —
the runner iterates this dict, nothing else needs to change.
"""
from __future__ import annotations

from benchmarks.memorybench.methods import (
    baselines,
    graphiti_style,
    graphrag_style,
    mem0_style,
    memgpt_style,
    tokenmizer_real,
)

REGISTRY: dict[str, tuple] = {
    tokenmizer_real.NAME: (tokenmizer_real.extract, tokenmizer_real.DESCRIPTION),
    memgpt_style.NAME: (memgpt_style.extract, memgpt_style.DESCRIPTION),
    mem0_style.NAME: (mem0_style.extract, mem0_style.DESCRIPTION),
    graphiti_style.NAME: (graphiti_style.extract, graphiti_style.DESCRIPTION),
    graphrag_style.NAME: (graphrag_style.extract, graphrag_style.DESCRIPTION),
    baselines.NAME_SLIDING: (baselines.extract_sliding_window, baselines.DESCRIPTION_SLIDING),
    baselines.NAME_TRUNCATION: (baselines.extract_truncation, baselines.DESCRIPTION_TRUNCATION),
    baselines.NAME_SUMMARY: (baselines.extract_naive_summary, baselines.DESCRIPTION_SUMMARY),
}

# Ordered for report printing — real engine first, then the graph/memory
# strategies it's being compared against, then the naive baselines.
ORDER = [
    tokenmizer_real.NAME,
    graphiti_style.NAME,
    graphrag_style.NAME,
    mem0_style.NAME,
    memgpt_style.NAME,
    baselines.NAME_SLIDING,
    baselines.NAME_TRUNCATION,
    baselines.NAME_SUMMARY,
]
