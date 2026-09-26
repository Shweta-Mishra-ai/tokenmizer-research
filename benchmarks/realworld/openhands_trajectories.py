"""
Convert public OpenHands CodeAct 2.1 trajectories into benchmark sessions.

A second agent framework, with a different message format: OpenAI-style
function calling (`tool_calls` on assistant turns, `role: "tool"` results),
which is exactly what TokenMizer's proxy receives from a function-calling
agent. The SWE-agent systems speak in text commands instead.

Ground truth follows the same rules as swe_trajectories.py:
  files   paths changed by the submitted patch (the evaluation harness's
          logs/<instance>/patch.diff).
  errors  runtime and lint errors in tool observations (role "tool") only.

In the trajectory files, message content and tool calls are stored as
Python-repr strings of lists; they are parsed with ast.literal_eval and
written as canonical OpenAI messages (string content, structured
tool_calls).

    python -m benchmarks.realworld.openhands_trajectories --src DIR --out DIR
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from benchmarks.realworld.swe_trajectories import _norm, observation_errors, patch_files

SYSTEM = "openhands_codeact21"

# OpenHands' submitted patches include build artifacts its commands left in
# the checkout: 1,096 compiled translation files (.mo) in one patch, Sphinx
# _build/ trees, SQLite databases. They were not worked on, and counting them
# would make "edited-file recall" mostly a measure of build output. Fixed
# before any method was run on this system (see README.md).
_ARTIFACT_DIR = re.compile(
    r"(?:^|/)(?:_build|build|dist|__pycache__|\.pytest_cache|\.tox|node_modules|"
    r"htmlcov|\.mypy_cache)/|\.egg-info/")
_ARTIFACT_EXT = re.compile(
    r"\.(?:mo|pyc|pyo|doctree|pickle|png|jpe?g|gif|svg|pdf|exe|so|dll|whl|"
    r"sqlite3?|db|orig|rej|bak)$", re.IGNORECASE)
# OpenHands appends the interpreter to the last output line:
# "TypeError: ...[Python Interpreter: /opt/miniconda3/envs/testbed/bin/python]".
_INTERPRETER_TAG = re.compile(r"\[Python Interpreter: [^\]]*\]")


def is_artifact(path: str) -> bool:
    return bool(_ARTIFACT_DIR.search(path) or _ARTIFACT_EXT.search(path))


def _parse(value):
    if isinstance(value, str):
        s = value.strip()
        if s[:1] in "[{":
            try:
                return ast.literal_eval(s)
            except (ValueError, SyntaxError):
                return value
    return value


def _text(content) -> str:
    content = _parse(content)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    return ""


def convert(items: list, instance_id: str, patch: str) -> dict | None:
    messages = []
    errors: list[str] = []
    kinds: dict[str, str] = {}
    seen: set[str] = set()
    for it in items:
        role = it.get("role")
        if role not in ("user", "assistant", "tool"):
            continue   # the system prompt is dropped, as in the "task" condition
        msg = {"role": role, "content": _text(it.get("content"))}
        calls = _parse(it.get("tool_calls"))
        if isinstance(calls, list) and calls:
            msg["tool_calls"] = [
                {"id": c.get("id", ""), "type": "function",
                 "function": {"name": (c.get("function") or {}).get("name", ""),
                              "arguments": (c.get("function") or {}).get("arguments", "")}}
                for c in calls if isinstance(c, dict)]
        if role == "tool":
            msg["tool_call_id"] = it.get("tool_call_id", "")
            msg["name"] = it.get("name", "")
            for e, kind in observation_errors(_INTERPRETER_TAG.sub("", msg["content"]),
                                              with_kind=True):
                if _norm(e) not in seen:
                    seen.add(_norm(e))
                    errors.append(e)
                    kinds[e] = kind
        messages.append(msg)
    if len(messages) < 4:
        return None
    return {
        "id": f"{SYSTEM}__{instance_id}",
        "origin": "real",
        "domain": instance_id.split("__")[0],
        "register": "agent-function-calling",
        "notes": (f"OpenHands CodeAct 2.1 (claude-3-5-sonnet-20241022) trajectory, "
                  f"instance={instance_id}. Ground truth derived automatically: files from "
                  f"the submitted patch, errors from tool observations."),
        "messages": messages,
        "ground_truth": {"files": [f for f in patch_files(patch) if not is_artifact(f)],
                         "errors": errors},
        "error_kinds": kinds,
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="directory with <instance>.json and patches/")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    src, out = Path(args.src), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted(src.glob("*.json")):
        patch_path = src / "patches" / f"{p.stem}.diff"
        patch = patch_path.read_text() if patch_path.exists() else ""
        s = convert(json.loads(p.read_text()), p.stem, patch)
        if s is None:
            continue
        (out / f"{s['id']}.json").write_text(json.dumps(s, ensure_ascii=False))
        n += 1
    print(f"Wrote {n} sessions to {out}")


if __name__ == "__main__":
    main()
