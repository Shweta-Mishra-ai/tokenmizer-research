"""Tests for tokenmizer.graph_memory.validator"""
import pytest
from tokenmizer.graph_memory.validator import GraphValidator
from tokenmizer.graph_memory.graph import GraphNode, NodeType, NodeStatus


class TestGraphValidator:
    @pytest.fixture
    def validator(self):
        return GraphValidator(min_confidence=0.50)

    def test_file_path_boosts_score(self, validator):
        node = GraphNode(
            id="test", type=NodeType.FILE,
            label="api/auth.py", status=None
        )
        score = validator.score(node)
        assert score >= 0.70  # base 0.5 + file bonus 0.2

    def test_long_label_boosts_score(self, validator):
        node = GraphNode(
            id="test", type=NodeType.TASK,
            label="Implemented user authentication with JWT tokens",
            status=NodeStatus.COMPLETED
        )
        score = validator.score(node)
        assert score >= 0.60  # base 0.5 + length bonus 0.1

    def test_short_label_penalized(self, validator):
        node = GraphNode(
            id="test", type=NodeType.TASK,
            label="fix", status=NodeStatus.PENDING
        )
        score = validator.score(node)
        assert score < 0.50  # should be rejected

    def test_verb_only_heavily_penalized(self, validator):
        node = GraphNode(
            id="test", type=NodeType.TASK,
            label="run", status=None
        )
        score = validator.score(node)
        assert score < 0.20

    def test_version_number_boosts(self, validator):
        node = GraphNode(
            id="test", type=NodeType.DECISION,
            label="Python 3.12", status=None
        )
        score = validator.score(node)
        assert score >= 0.60
