"""Tests for tokenmizer.graph_memory.extractor_v2"""
import pytest
from tokenmizer.graph_memory.extractor_v2 import (
    heuristic_extract_v2,
    normalize_label,
    split_compound,
    fuzzy_match,
)


class TestNormalizeLabel:
    def test_lowercase(self):
        assert normalize_label("FastAPI Auth") == "fastapi auth"

    def test_strips_whitespace(self):
        assert normalize_label("  hello  world  ") == "hello world"

    def test_strips_verbose_prefix(self):
        assert normalize_label("Fixed the login bug") == "the login bug"
        assert normalize_label("Completed user model") == "user model"
        assert normalize_label("Added rate limiting") == "rate limiting"

    def test_truncates_at_60_chars(self):
        long_label = "a" * 100
        assert len(normalize_label(long_label)) == 60

    def test_removes_special_chars(self):
        # normalize_label preserves dots and slashes (for file paths/versions)
        assert normalize_label("v1.0 (beta)") == "v1.0 beta"


class TestSplitCompound:
    def test_splits_on_sentence_boundary(self):
        result = split_compound("Created auth module. Implemented login flow")
        assert len(result) == 2

    def test_no_split_single_sentence(self):
        result = split_compound("simple task")
        assert len(result) == 1

    def test_filters_short_fragments(self):
        result = split_compound("OK. Good. Implemented login")
        assert all(len(p) > 3 for p in result)


class TestFuzzyMatch:
    def test_substring_containment(self):
        assert fuzzy_match("auth endpoints", "implemented auth endpoints for login")

    def test_reverse_containment(self):
        assert fuzzy_match("implemented auth endpoints for login", "auth endpoints")

    def test_token_overlap(self):
        assert fuzzy_match("bcrypt password hashing", "using bcrypt for hashing")

    def test_no_match(self):
        assert not fuzzy_match("redis cache", "postgresql database")

    def test_empty_strings(self):
        # Empty string is a substring of any string in Python, so fuzzy_match returns True
        # This is acceptable behavior — callers should filter empty inputs
        assert fuzzy_match("", "something")  # '' in 'something' == True

    def test_case_insensitive(self):
        assert fuzzy_match("FastAPI", "fastapi service")


class TestHeuristicExtractV2:
    def test_extracts_completed_tasks(self, sample_messages):
        result = heuristic_extract_v2(sample_messages)
        tasks = result["tasks"]
        completed = [t for t in tasks if t["status"] == "completed"]
        assert len(completed) >= 2  # scaffold + user model

    def test_extracts_decisions(self, sample_messages):
        result = heuristic_extract_v2(sample_messages)
        decisions = result["decisions"]
        labels = [d["label"] for d in decisions]
        assert any("python" in l or "3.12" in l for l in labels)

    def test_extracts_files(self, sample_messages):
        result = heuristic_extract_v2(sample_messages)
        files = result["files"]
        assert "api/models.py" in files

    def test_extracts_pending_tasks(self, sample_messages):
        result = heuristic_extract_v2(sample_messages)
        tasks = result["tasks"]
        pending = [t for t in tasks if t["status"] == "pending"]
        assert len(pending) >= 1

    def test_extracts_in_progress(self, sample_messages):
        result = heuristic_extract_v2(sample_messages)
        tasks = result["tasks"]
        in_progress = [t for t in tasks if t["status"] == "in_progress"]
        assert len(in_progress) >= 1

    def test_ignores_user_messages(self):
        messages = [
            {"role": "user", "content": "Completed: something important"},
            {"role": "assistant", "content": "Working on your request."},
        ]
        result = heuristic_extract_v2(messages)
        tasks = result["tasks"]
        # Should not extract from user messages
        completed = [t for t in tasks if t["status"] == "completed"]
        assert len(completed) == 0

    def test_empty_messages(self):
        result = heuristic_extract_v2([])
        assert result["tasks"] == []
        assert result["decisions"] == []
        assert result["files"] == []
