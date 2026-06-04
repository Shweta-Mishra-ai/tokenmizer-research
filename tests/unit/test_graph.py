"""Tests for tokenmizer.graph_memory.graph"""
import pytest
from tokenmizer.graph_memory.graph import (
    GraphMemory,
    GraphNode,
    NodeType,
    NodeStatus,
    STATUS_ORDER,
)


class TestGraphNode:
    def test_make_id_deterministic(self):
        id1 = GraphNode.make_id(NodeType.TASK, "auth service")
        id2 = GraphNode.make_id(NodeType.TASK, "auth service")
        assert id1 == id2

    def test_make_id_case_insensitive(self):
        id1 = GraphNode.make_id(NodeType.TASK, "Auth Service")
        id2 = GraphNode.make_id(NodeType.TASK, "auth service")
        assert id1 == id2

    def test_different_types_different_ids(self):
        id1 = GraphNode.make_id(NodeType.TASK, "auth")
        id2 = GraphNode.make_id(NodeType.DECISION, "auth")
        assert id1 != id2


class TestStatusOrder:
    def test_completed_beats_pending(self):
        assert STATUS_ORDER[NodeStatus.COMPLETED] > STATUS_ORDER[NodeStatus.PENDING]

    def test_in_progress_beats_pending(self):
        assert STATUS_ORDER[NodeStatus.IN_PROGRESS] > STATUS_ORDER[NodeStatus.PENDING]

    def test_modified_beats_completed(self):
        assert STATUS_ORDER[NodeStatus.MODIFIED] > STATUS_ORDER[NodeStatus.COMPLETED]


class TestGraphMemory:
    def test_create_and_extract(self, tmp_storage, sample_messages):
        g = GraphMemory(session_id="test-session", storage_dir=tmp_storage)
        g.extract_from_messages(sample_messages)
        assert g.node_count > 0

    def test_resume_block_within_budget(self, tmp_storage, sample_messages):
        g = GraphMemory(session_id="test-session", storage_dir=tmp_storage)
        g.extract_from_messages(sample_messages)
        block = g.to_resume_block(budget=300)
        assert "CHECKPOINT" in block
        assert len(block) < 1200  # 300 tokens * ~4 chars

    def test_persistence(self, tmp_storage, sample_messages):
        # Create and populate
        g1 = GraphMemory(session_id="persist-test", storage_dir=tmp_storage)
        g1.extract_from_messages(sample_messages)
        count1 = g1.node_count

        # Reload from same DB
        g2 = GraphMemory(session_id="persist-test", storage_dir=tmp_storage)
        assert g2.node_count == count1

    def test_empty_graph_resume(self, tmp_storage):
        g = GraphMemory(session_id="empty", storage_dir=tmp_storage)
        block = g.to_resume_block()
        assert "CHECKPOINT" in block
