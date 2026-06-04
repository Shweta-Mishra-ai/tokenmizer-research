"""
TokenMizer Graph Memory
=======================
Persistent typed knowledge graph for LLM session state.
Schema: 14 node types, 7 edge types.
Storage: SQLite via three tables (nodes, edges, checkpoints).
"""
from __future__ import annotations
import hashlib, json, sqlite3, time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


class NodeType(str, Enum):
    # Action nodes (carry status lifecycle)
    TASK        = "task"
    FILE        = "file"
    ERROR       = "error"
    TEST        = "test"
    SCHEMA      = "schema"
    METRIC      = "metric"
    # Decision nodes
    DECISION    = "decision"
    DEPENDENCY  = "dependency"
    API         = "api"
    # Context nodes (status-free)
    GOAL        = "goal"
    ENVIRONMENT = "environment"
    PROJECT     = "project"
    CONCEPT     = "concept"
    AGENT       = "agent"


class NodeStatus(str, Enum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    FAILED      = "failed"
    MODIFIED    = "modified"


class EdgeType(str, Enum):
    DEPENDS_ON  = "depends_on"
    RELATED_TO  = "related_to"
    IMPLEMENTS  = "implements"
    FIXES       = "fixes"
    BLOCKS      = "blocks"
    PART_OF     = "part_of"
    SUPERSEDES  = "supersedes"


# Status transition ordering (monotonic — downgrades rejected)
STATUS_ORDER = {
    NodeStatus.PENDING: 0, NodeStatus.IN_PROGRESS: 1,
    NodeStatus.COMPLETED: 2, NodeStatus.FAILED: 2, NodeStatus.MODIFIED: 3,
}

# Node types always retained during pruning
PINNED_TYPES = {NodeType.DECISION, NodeType.ENVIRONMENT,
                NodeType.GOAL, NodeType.SCHEMA}


@dataclass
class GraphNode:
    id: str
    type: NodeType
    label: str
    status: Optional[NodeStatus] = None
    summary: str = ""
    importance: float = 0.5
    confidence: float = 0.5
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @staticmethod
    def make_id(node_type: NodeType, label: str) -> str:
        norm = f"{node_type}:{label.lower().strip()}"
        return hashlib.sha1(norm.encode()).hexdigest()[:12]


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    type: EdgeType
    weight: float = 1.0


class GraphMemory:
    """
    Persistent session knowledge graph backed by SQLite.

    Usage:
        g = GraphMemory(session_id="my-project")
        g.extract_from_messages(messages)
        checkpoint = g.to_resume_block(budget=300)
    """

    def __init__(self, session_id: str, storage_dir: str = ".tokenmizer"):
        self.session_id = session_id
        self._db_path = Path(storage_dir) / f"{session_id}.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._init_db()
        self._load()

    # ── Public API ──────────────────────────────────────────────────────────

    def extract_from_messages(self, messages: list[dict],
                               incremental: bool = True) -> None:
        """Extract graph nodes from conversation messages."""
        from .extractor_v2 import heuristic_extract_v2
        from .validator import GraphValidator
        validator = GraphValidator()
        extracted = heuristic_extract_v2(messages)
        for task in extracted.get("tasks", []):
            node = GraphNode(
                id=GraphNode.make_id(NodeType.TASK, task["label"]),
                type=NodeType.TASK,
                label=task["label"][:120],
                status=NodeStatus(task.get("status", "pending")),
            )
            self._upsert_node(node, validator)
        for dec in extracted.get("decisions", []):
            node = GraphNode(
                id=GraphNode.make_id(NodeType.DECISION, dec["label"]),
                type=NodeType.DECISION,
                label=dec["label"][:120],
                summary=dec.get("rationale", ""),
            )
            self._upsert_node(node, validator)
        for fp in extracted.get("files", []):
            node = GraphNode(
                id=GraphNode.make_id(NodeType.FILE, fp),
                type=NodeType.FILE,
                label=fp[:120],
            )
            self._upsert_node(node, validator)
        self._save()

    def to_resume_block(self, budget: int = 300) -> str:
        """Serialize graph to a compact resume block within token budget."""
        from ..core.tokenizer import count_tokens
        lines = [f"[CHECKPOINT: {self.session_id}]"]
        token_budget = budget - count_tokens(lines[0])

        def add(line: str) -> bool:
            nonlocal token_budget
            cost = count_tokens(line)
            if cost > token_budget:
                return False
            lines.append(line)
            token_budget -= cost
            return True

        sorted_nodes = sorted(self._nodes.values(),
                              key=lambda n: n.importance, reverse=True)
        completed = [n for n in sorted_nodes
                     if n.type == NodeType.TASK
                     and n.status == NodeStatus.COMPLETED]
        pending   = [n for n in sorted_nodes
                     if n.type == NodeType.TASK
                     and n.status in (NodeStatus.PENDING, NodeStatus.IN_PROGRESS)]
        decisions = [n for n in sorted_nodes if n.type == NodeType.DECISION]
        files_    = [n for n in sorted_nodes if n.type == NodeType.FILE]
        envs      = [n for n in sorted_nodes if n.type == NodeType.ENVIRONMENT]

        if completed:
            add("DONE: " + ", ".join(n.label for n in completed[:8]))
        if pending:
            add("PENDING: " + ", ".join(n.label for n in pending[:5]))
        if decisions:
            add("DECIDED: " + ", ".join(n.label for n in decisions[:8]))
        if files_:
            add("FILES: " + ", ".join(n.label for n in files_[:6]))
        if envs:
            add("ENV: " + ", ".join(n.label for n in envs[:4]))

        return "\n".join(lines)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    # ── Private helpers ─────────────────────────────────────────────────────

    def _upsert_node(self, node: GraphNode, validator) -> None:
        node.confidence = validator.score(node)
        if node.confidence < validator.min_confidence:
            return
        if node.id in self._nodes:
            existing = self._nodes[node.id]
            existing.importance = min(1.0, existing.importance + 0.1)
            existing.updated_at = time.time()
            if node.status and existing.status:
                if STATUS_ORDER.get(node.status, 0) > STATUS_ORDER.get(existing.status, 0):
                    existing.status = node.status
        else:
            self._nodes[node.id] = node
        if len(self._nodes) > 500:
            self._prune()

    def _prune(self) -> None:
        evictable = [n for n in self._nodes.values()
                     if n.type not in PINNED_TYPES and n.importance < 0.1]
        for n in sorted(evictable, key=lambda x: x.importance)[:50]:
            del self._nodes[n.id]

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY, type TEXT, label TEXT,
                status TEXT, summary TEXT, importance REAL,
                confidence REAL, created_at REAL, updated_at REAL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS edges (
                source_id TEXT, target_id TEXT, type TEXT, weight REAL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS checkpoints (
                id TEXT PRIMARY KEY, session_id TEXT,
                resume_block TEXT, graph_diff TEXT, created_at REAL)""")

    def _load(self) -> None:
        with sqlite3.connect(self._db_path) as con:
            for row in con.execute("SELECT * FROM nodes"):
                n = GraphNode(id=row[0], type=NodeType(row[1]), label=row[2],
                              status=NodeStatus(row[3]) if row[3] else None,
                              summary=row[4] or "", importance=row[5],
                              confidence=row[6], created_at=row[7],
                              updated_at=row[8])
                self._nodes[n.id] = n
            for row in con.execute("SELECT * FROM edges"):
                e = GraphEdge(source_id=row[0], target_id=row[1],
                              type=EdgeType(row[2]), weight=row[3])
                self._edges.append(e)

    def _save(self) -> None:
        with sqlite3.connect(self._db_path) as con:
            for n in self._nodes.values():
                con.execute("""INSERT OR REPLACE INTO nodes
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (n.id, n.type.value, n.label,
                     n.status.value if n.status else None,
                     n.summary, n.importance, n.confidence,
                     n.created_at, n.updated_at))
            for e in self._edges:
                con.execute("""INSERT OR REPLACE INTO edges
                    VALUES (?,?,?,?)""",
                    (e.source_id, e.target_id, e.type.value, e.weight))
