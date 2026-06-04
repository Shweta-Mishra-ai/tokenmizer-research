"""Tests for tokenmizer.compression.engine"""
import pytest
from tokenmizer.compression.engine import CompressionEngine


class TestCompressionEngine:
    @pytest.fixture
    def engine(self):
        return CompressionEngine(min_tokens=10)  # low threshold for testing

    def test_filler_removal(self, engine):
        text = "Certainly! I'd be happy to help. Here is the code. " * 20
        result = engine.compress(text)
        assert len(result) < len(text)
        assert "certainly" not in result.lower() or "happy to help" not in result.lower()

    def test_dedup_lines(self, engine):
        text = "line one\n" * 30 + "line two\n"
        result = engine.compress(text)
        assert result.count("line one") == 1

    def test_whitespace_normalization(self, engine):
        text = ("word   word\n\n\n\nword\t\tword " * 20)
        result = engine.compress(text)
        assert "   " not in result
        assert "\t" not in result
        assert "\n\n\n" not in result

    def test_short_text_bypass(self):
        engine = CompressionEngine(min_tokens=300)
        short = "Hello world"
        assert engine.compress(short) == short

    def test_preserves_content_meaning(self, engine):
        text = ("Implemented user authentication with JWT tokens. "
                "The auth module handles login and registration. " * 10)
        result = engine.compress(text)
        # Should still contain the meaningful content
        assert "auth" in result.lower() or "jwt" in result.lower()
