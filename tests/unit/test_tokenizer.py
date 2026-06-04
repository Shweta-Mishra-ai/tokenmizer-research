"""Tests for tokenmizer.core.tokenizer"""
import pytest
from tokenmizer.core.tokenizer import count_tokens


class TestCountTokens:
    def test_non_empty_string(self):
        result = count_tokens("hello world")
        assert result > 0

    def test_empty_string(self):
        result = count_tokens("")
        assert result == 0

    def test_longer_text_more_tokens(self):
        short = count_tokens("hello")
        long = count_tokens("hello world this is a longer sentence with more words")
        assert long > short

    def test_returns_int(self):
        result = count_tokens("test")
        assert isinstance(result, int)
