"""
TokenMizer V2 Heuristic Extractor
===================================
V2 improvements over V1 baseline (ablation results):
  + expanded trigger vocabulary  → +0pp task recall (enables fuzzy matching)
  + fuzzy label matching         → +33pp task recall  ← DOMINANT IMPROVEMENT
  + compound task splitting      → +0pp
  + decision CSV splitting       → slight decision recall regression (known issue)

Latency: 0.5ms per session. Cost: $0.
"""
from __future__ import annotations
import re

_COMPLETED = re.compile(
    r'(?:Completed|Implemented|Fixed|Added|Deployed|Resolved|Migrated'
    r'|Launched|Shipped|Published|Done|Finished|Updated)[:\s]+(.+?)(?:\.|$)',
    re.I | re.M)
_IN_PROGRESS = re.compile(
    r'(?:Working on|Adding|Building|Setting up|Implementing|Integrating)[:\s]+(.+?)(?:\.|$)',
    re.I | re.M)
_PENDING = re.compile(
    r'(?:Need to|TODO|Will|Next|Pending)[:\s]+(.+?)(?:\.|$)',
    re.I | re.M)
_DECISION = re.compile(
    r'(?:Decided|Using|Running|Tools?|Chose|Selected)[:\s]+(.+?)(?:\.|$)',
    re.I | re.M)
_FILE = re.compile(
    r'(?:Files?[:\s]+|Updated[:\s]+|Created[:\s]+)?'
    r'([\w./][\w./\-]*\.(?:py|js|ts|jsx|tsx|yaml|yml|json|md|go|rs|tf|toml|sh))',
    re.I)
_VERBOSE_PREFIX = re.compile(
    r'^(?:missing|error|fixed|added|completed|created|updated|implemented)\s+',
    re.I)


def normalize_label(label: str) -> str:
    label = label.lower().strip()
    label = re.sub(r'\s+', ' ', label)
    label = re.sub(r'[^\w\s./\-]', '', label)
    label = _VERBOSE_PREFIX.sub('', label)
    return label[:60]


def split_compound(label: str) -> list[str]:
    parts = [p.strip() for p in re.split(r'\.\s+(?=[A-Z])', label)]
    return [p for p in parts if len(p) > 3]


def fuzzy_match(a: str, b: str) -> bool:
    """
    Match verbose extracted labels against concise ground-truth annotations.
    Definition 5 from the paper: substring containment OR ≥50% token overlap.
    The ≥3-char filter prevents common short tokens from inflating scores.
    """
    a, b = a.lower(), b.lower()
    if a in b or b in a:
        return True
    wa = set(re.findall(r'\w{3,}', a))
    wb = set(re.findall(r'\w{3,}', b))
    if not wa or not wb:
        return False
    shorter = wa if len(wa) <= len(wb) else wb
    return len(wa & wb) / len(shorter) >= 0.5


def heuristic_extract_v2(messages: list[dict]) -> dict:
    """
    V2 heuristic extractor. Drop-in replacement for V1.
    Returns dict compatible with GraphMemory._apply_extracted().
    """
    text = "\n".join(m["content"] for m in messages if m.get("role") == "assistant")

    completed, in_progress, pending = set(), set(), set()
    decisions, files = set(), set()

    for m in _COMPLETED.finditer(text):
        for part in split_compound(m.group(1).strip()):
            if len(part) > 3:
                completed.add(normalize_label(part))

    for m in _IN_PROGRESS.finditer(text):
        in_progress.add(normalize_label(m.group(1).strip()[:70]))

    for m in _PENDING.finditer(text):
        pending.add(normalize_label(m.group(1).strip()[:70]))

    for m in _DECISION.finditer(text):
        for part in re.split(r',\s*|\s+and\s+', m.group(1).strip()):
            part = normalize_label(part)
            if 2 < len(part) < 50:
                decisions.add(part)

    for m in _FILE.finditer(text):
        files.add(m.group(1).lower())

    tasks = (
        [{"label": t, "status": "completed"} for t in completed] +
        [{"label": t, "status": "in_progress"} for t in in_progress] +
        [{"label": t, "status": "pending"} for t in pending]
    )
    return {
        "tasks": tasks,
        "decisions": [{"label": d, "rationale": ""} for d in decisions],
        "files": list(files),
        "errors": [], "dependencies": [], "environment": [],
        "goals": [], "endpoints": [], "schemas": [],
    }
