"""
Checkpoint Manager
==================
Three-tier serialization system with graph diffs.
Tiers: critical (100 tok), standard (300 tok), full (600 tok).
"""
from __future__ import annotations
import json, time, uuid
from dataclasses import dataclass
from pathlib import Path


TIER_BUDGETS = {"critical": 100, "standard": 300, "full": 600}


@dataclass
class Checkpoint:
    id: str
    session_id: str
    tier: str
    resume_block: str
    resume_tokens: int
    graph_diff: dict
    created_at: float


class CheckpointManager:
    def __init__(self, storage_dir: str = ".tokenmizer"):
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def create(self, session_id: str, graph,
               tier: str = "standard") -> Checkpoint:
        from ..core.tokenizer import count_tokens
        budget = TIER_BUDGETS.get(tier, 300)
        block = graph.to_resume_block(budget=budget)
        ckpt = Checkpoint(
            id=f"ckpt_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            tier=tier,
            resume_block=block,
            resume_tokens=count_tokens(block),
            graph_diff={},
            created_at=time.time(),
        )
        self._persist(ckpt)
        return ckpt

    def load_latest(self, session_id: str) -> Checkpoint | None:
        path = self._dir / f"{session_id}_latest.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return Checkpoint(**data)

    def _persist(self, ckpt: Checkpoint) -> None:
        import dataclasses
        path = self._dir / f"{ckpt.session_id}_latest.json"
        path.write_text(json.dumps(dataclasses.asdict(ckpt), indent=2))
