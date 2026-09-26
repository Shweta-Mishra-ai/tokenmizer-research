"""
TokenMizer — the real product engine (`tokenmizer` 0.5.2), run out of
process against the actual `GraphMemory.extract_from_messages()` +
`HybridExtractor` heuristic pass. See `_tokenmizer_worker.py` for why
this runs as a subprocess rather than an in-process import.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from benchmarks.memorybench.methods.common import MethodResult, count_tokens

NAME = "tokenmizer_v0.5.2"
DESCRIPTION = "Real product engine — GraphMemory + HybridExtractor heuristic pass (out of process)."

_WORKER = Path(__file__).resolve().with_name("_tokenmizer_worker.py")
PRODUCT_REPO = Path(os.environ.get("TOKENMIZER_PRODUCT_REPO", "/home/user/tokenmizer"))


def _resolve_version() -> str:
    try:
        text = (PRODUCT_REPO / "tokenmizer" / "__init__.py").read_text()
        for line in text.splitlines():
            if line.strip().startswith("__version__"):
                return line.split("=")[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return "unknown"


VERSION = _resolve_version()


def product_revision() -> dict:
    """The product checkout actually measured. `__version__` alone is not
    enough: unreleased commits on main keep the last release's version
    string, so two different engines can both report "0.5.4"."""
    try:
        commit = subprocess.run(
            ["git", "-C", str(PRODUCT_REPO), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip() or "unknown"
        dirty = bool(subprocess.run(
            ["git", "-C", str(PRODUCT_REPO), "status", "--porcelain", "--", "tokenmizer"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        commit, dirty = "unknown", False
    return {"version": VERSION, "commit": commit, "dirty": dirty}


def available() -> bool:
    return _WORKER.exists() and (PRODUCT_REPO / "tokenmizer" / "__init__.py").exists()


def extract(session, incremental: bool = False, timeout: int = 60) -> MethodResult:
    """Run the product on one session. `incremental=True` feeds the history
    one message per call, the way the proxy sees it in production; the
    default extracts the whole session at once."""
    payload = json.dumps({"session_id": session.id, "messages": session.messages,
                          "incremental": incremental})
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PRODUCT_REPO)
    env.pop("PYTHONSTARTUP", None)

    proc = subprocess.run(
        [sys.executable, str(_WORKER)],
        input=payload, capture_output=True, text=True, env=env,
        cwd=str(PRODUCT_REPO), timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"tokenmizer_real worker failed on {session.id} (exit {proc.returncode}):\n"
            f"{proc.stderr[-2000:]}"
        )
    out = json.loads(proc.stdout)

    resume_text = out.get("resume_text", "")
    return MethodResult(
        completed_tasks=out["completed_tasks"],
        pending_tasks=out["pending_tasks"],
        decisions=out["decisions"],
        files=out["files"],
        errors=out["errors"],
        resume_text=resume_text,
        resume_tokens=count_tokens(resume_text) if resume_text else 0,
        extract_ms=out.get("extract_ms", 0.0),
        per_call_ms=out.get("per_call_ms", []),
        node_count=sum(len(out[c]) for c in
                        ("completed_tasks", "pending_tasks", "decisions", "files", "errors")),
    )
