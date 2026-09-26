"""
Convert public SWE-bench agent trajectories into benchmark sessions.

Why this data. Every other corpus in this repository is synthetic and written
by the same author as the extractor, which is the first threat to validity a
reviewer raises. SWE-bench submissions publish complete agent trajectories:
the exact message history the model saw on a real GitHub issue, plus the
patch it finally submitted. That gives two kinds of ground truth that need
no human labelling and cannot be tuned to the extractor:

  files   the files changed by the submitted patch (``diff --git a/X b/X``).
          A memory layer that cannot recall which files the agent edited has
          failed at the most basic resume question.
  errors  the failures the agent hit, read from tool OBSERVATIONS only (never
          from the agent's own prose): the final exception line of every
          Python traceback, and every linter error the environment reported
          for a proposed edit (SWE-agent's "E999 IndentationError: ...").

Completed tasks, pending tasks and decisions have no objective label in this
data and are NOT scored here; results for them come from the labelled
corpora only.

The derivation rules below were written and committed before any extractor
was run on this data.

    python -m benchmarks.realworld.swe_trajectories --src DIR --out DIR
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_PATCH_FILE = re.compile(r"^diff --git a/(\S+) b/(\S+)$", re.MULTILINE)
_TRACEBACK = "Traceback (most recent call last):"
# The last line of a traceback: a (possibly dotted) exception class, then
# an optional message.
_EXC_LINE = re.compile(
    r"^((?:[A-Za-z_][\w]*\.)*[A-Za-z_]\w*(?:Error|Exception|Exit|Interrupt|Warning))"
    r"(?::\s?(.*))?$"
)
# SWE-agent's edit linter: "- E999 IndentationError: unexpected indent"
_LINT_LINE = re.compile(r"^\s*-?\s*(E9\d\d|F8\d\d)\s+(.+)$")


def patch_files(patch: str) -> list[str]:
    seen: list[str] = []
    for a, b in _PATCH_FILE.findall(patch or ""):
        path = b if b != "/dev/null" else a
        if path not in seen:
            seen.append(path)
    return seen


def observation_errors(text: str, with_kind: bool = False) -> list:
    """Exception lines ending tracebacks ("runtime"), and linter errors
    ("lint"), in one tool observation."""
    found: list = []
    lines = text.splitlines()
    in_tb = False
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith(_TRACEBACK):
            in_tb = True
            continue
        if in_tb:
            m = _EXC_LINE.match(s)
            if m and not line.startswith((" ", "\t")):
                msg = (m.group(2) or "").strip()
                label = f"{m.group(1)}: {msg}"[:160] if msg else m.group(1)
                found.append((label, "runtime") if with_kind else label)
                in_tb = False
            continue
        m = _LINT_LINE.match(line)
        if m:
            label = m.group(2).strip()[:160]
            found.append((label, "lint") if with_kind else label)
    return found


def _norm(err: str) -> str:
    return re.sub(r"\s+", " ", err.lower())[:100]


def convert(traj: dict, instance_id: str, system: str, keep_prompt: bool) -> dict | None:
    history = traj.get("history") or []
    messages = []
    errors: list[str] = []
    kinds: dict[str, str] = {}
    seen_err: set[str] = set()
    issue_seen = False
    for h in history:
        role = h.get("role")
        content = h.get("content")
        if role not in ("system", "user", "assistant") or not isinstance(content, str):
            continue
        is_prompt = role == "system" or h.get("is_demo")
        if is_prompt and not keep_prompt:
            continue
        messages.append({"role": role, "content": content})
        # Ground truth errors: tool observations only, i.e. user turns after
        # the issue statement that are not the system prompt or a demo.
        if role == "user" and not h.get("is_demo"):
            if not issue_seen:
                issue_seen = True
                continue
            for e, kind in observation_errors(content, with_kind=True):
                k = _norm(e)
                if k not in seen_err:
                    seen_err.add(k)
                    errors.append(e)
                    kinds[e] = kind
    if len(messages) < 4:
        return None
    submission = (traj.get("info") or {}).get("submission") or ""
    return {
        "id": f"{system}__{instance_id}",
        "origin": "real",
        "domain": instance_id.split("__")[0],
        "register": "agent",
        "notes": (f"SWE-bench trajectory, system={system}, instance={instance_id}, "
                  f"exit_status={(traj.get('info') or {}).get('exit_status')!r}, "
                  f"prompt={'kept' if keep_prompt else 'dropped'}. Ground truth derived "
                  f"automatically: files from the submitted patch, errors from tool "
                  f"observations."),
        "messages": messages,
        "ground_truth": {"files": patch_files(submission), "errors": errors},
        "error_kinds": kinds,
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="directory of .traj files")
    ap.add_argument("--system", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--keep-prompt", action="store_true",
                    help="keep the system prompt and demonstration, as the model saw them")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted(Path(args.src).glob("*.traj")):
        s = convert(json.loads(p.read_text()), p.stem, args.system, args.keep_prompt)
        if s is None:
            continue
        (out / f"{s['id']}.json").write_text(json.dumps(s, ensure_ascii=False))
        n += 1
    print(f"Wrote {n} sessions to {out}")


if __name__ == "__main__":
    main()
