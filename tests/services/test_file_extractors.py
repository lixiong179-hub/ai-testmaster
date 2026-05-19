import pytest
from app.services.file_extractor.extractors import clean_text


class TestCleanText:
    def test_empty_string(self):
        assert clean_text("") == ""

    def test_none_like(self):
        assert clean_text(None) == ""

    def test_normalizes_line_endings(self):
        result = clean_text("line1\r\nline2\rline3\nline4")
        assert "\r" not in result
        assert result.count("\n") == 3

    def test_collapses_spaces(self):
        result = clean_text("hello    world   test")
        assert "    " not in result

    def test_collapses_tabs(self):
        result = clean_text("hello\t\tworld")
        assert "\t" not in result

    def test_collapses_multiple_newlines(self):
        result = clean_text("line1\n\n\n\nline2")
        assert "\n\n\n" not in result

    def test_truncates_long_text(self):
        long_text = "a" * 60000
        result = clean_text(long_text, max_length=50000)
        assert len(result) < 60000
        assert "截断" in result

    def test_custom_max_length(self):
        text = "a" * 200
        result = clean_text(text, max_length=100)
        assert len(result) < 200

    def test_strips_whitespace(self):
        result = clean_text("  hello  ")
        assert result == "hello"

    def test_preserves_single_newlines(self):
        result = clean_text("line1\nline2")
        assert result == "line1\nline2"

    def test_preserves_double_newlines(self):
        result = clean_text("line1\n\nline2")
        assert result == "line1\n\nline2"

    def test_short_text_unchanged(self):
        text = "hello world"
        assert clean_text(text) == text
