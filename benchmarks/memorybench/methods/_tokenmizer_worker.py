#!/usr/bin/env python3
"""
Subprocess worker that runs the REAL TokenMizer product engine.

Run standalone (never imported): `tokenmizer_real.py` launches this via
`subprocess` with `PYTHONPATH` pointed at the product repo checkout and
nothing else on the path, so `import tokenmizer` resolves to the actual
product package (currently 0.5.2) rather than the same-named package
that lives inside *this* repo (`tokenmizer-research/tokenmizer/`, an
older, separate implementation). Running in-process risked exactly that
shadowing — whichever `tokenmizer` sys.path found first would silently
win, and a benchmark that quietly ran the wrong engine is worse than one
that fails loudly. The subprocess boundary makes the two packages
unable to collide.

Protocol: one JSON object on stdin —
    {"session_id": "...", "messages": [{"role": "...", "content": "..."}]}
one JSON object on stdout —
    {"completed_tasks": [...], "pending_tasks": [...], "decisions": [...],
     "files": [...], "errors": [...], "extract_ms": 1.23}
"""
from __future__ import annotations

import json
import sys
import tempfile
import time


def main() -> int:
    req = json.loads(sys.stdin.read())
    session_id = req["session_id"]
    messages = req["messages"]

    from tokenmizer.graph_memory.graph import GraphMemory, NodeStatus, NodeType

    t0 = time.monotonic()
    with tempfile.TemporaryDirectory() as d:
        g = GraphMemory(session_id, storage_dir=d)
        g.extract_from_messages(messages, incremental=False)
        nodes = [n for n in g._nodes.values() if not n._evicted]
    elapsed_ms = (time.monotonic() - t0) * 1000

    resume_text = ""
    try:
        resume_text = g.to_context_block(token_budget=400)
    except Exception:
        pass

    selectors = {
        "completed_tasks": lambda n: n.type == NodeType.TASK and n.status == NodeStatus.COMPLETED,
        "pending_tasks": lambda n: n.type == NodeType.TASK and n.status in (
            NodeStatus.IN_PROGRESS, NodeStatus.PENDING),
        "decisions": lambda n: n.type == NodeType.DECISION,
        "files": lambda n: n.type == NodeType.FILE,
        "errors": lambda n: n.type == NodeType.ERROR,
    }
    out = {cat: [n.label for n in nodes if sel(n)] for cat, sel in selectors.items()}
    out["extract_ms"] = elapsed_ms
    out["resume_text"] = resume_text
    out["resume_chars"] = len(resume_text)

    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
