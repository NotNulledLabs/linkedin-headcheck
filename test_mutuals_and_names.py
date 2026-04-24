"""
Tests for mutual-connection detection and suspicious-name heuristics.

These are the pieces where the refactor fixed a chain of small bugs
(multilingual digit counting, CJK names flagged as suspicious, etc.),
so the tests are regression-focused.
"""
import pytest

from headcheck import count_mutual, is_suspicious_name


# ─────────────────────────────────────────────────────────────────────────────
# count_mutual
# ─────────────────────────────────────────────────────────────────────────────

class TestCountMutualEnglish:
    def test_empty_text_returns_zero(self):
        assert count_mutual("", "en") == 0

    def test_no_keyword_returns_zero(self):
        assert count_mutual("Loves dogs and travel", "en") == 0

    def test_single_mutual_returns_one(self):
        assert count_mutual("1 mutual connection", "en") == 1

    def test_explicit_count_over_one_returns_two(self):
        assert count_mutual("3 mutual connections", "en") == 2

    def test_two_names_with_and_returns_two(self):
        assert count_mutual("Bill and Sarah are mutual connections", "en") == 2


class TestCountMutualMultilingual:
    """
    Regression tests. Before the refactor, the digit-counting regex was
    English-only (r'\\d+\\s+mutual'), so a Spanish '5 conexiones en común'
    was incorrectly classified as 1 mutual.
    """
    def test_spanish_explicit_count(self):
        assert count_mutual("5 conexiones en común", "es") == 2

    def test_spanish_conjunction(self):
        assert count_mutual("Ana y Luis son conexiones en común", "es") == 2

    def test_spanish_single(self):
        assert count_mutual("1 conexión en común", "es") == 1

    def test_french_explicit_count(self):
        assert count_mutual("3 relations communes", "fr") == 2

    def test_german_explicit_count(self):
        assert count_mutual("2 gemeinsame Kontakte", "de") == 2

    def test_portuguese_explicit_count(self):
        assert count_mutual("4 conexões em comum", "pt") == 2

    def test_italian_explicit_count(self):
        assert count_mutual("3 collegamenti in comune", "it") == 2


class TestCountMutualEnglishFallback:
    """
    When the user picks a non-English lang but the mutual caption happens
    to be in English (e.g. admin account with language override), the
    extractor still needs to detect it.
    """
    def test_english_caption_with_es_lang(self):
        assert count_mutual("3 mutual connections", "es") == 2

    def test_english_caption_with_unknown_lang(self):
        """Unknown langs should still fall back to English matching."""
        assert count_mutual("3 mutual connections", "xx") == 2


# ─────────────────────────────────────────────────────────────────────────────
# is_suspicious_name
# ─────────────────────────────────────────────────────────────────────────────

class TestSuspiciousName:
    @pytest.mark.parametrize("name", [
        "John Smith",
        "María García",
        "Владимир Путин",       # Cyrillic
        "李明",                  # CJK 2-char (regression fix)
        "田中太郎",               # Japanese kanji
        "김민수",                # Korean hangul
        "Ana-María O'Brien",    # hyphen + apostrophe
    ])
    def test_legitimate_names_not_flagged(self, name):
        is_susp, reason = is_suspicious_name(name)
        assert is_susp is False, f"{name!r} flagged as {reason!r}"

    @pytest.mark.parametrize("name,expected_reason_fragment", [
        ("",                    "empty"),
        ("J. K.",               "initials"),
        ("JOHNSMITHACCOUNT",    "all-caps"),
        ("user_4892",           "digits"),
        ("John123",             "digits"),
        ("test@user",           "@"),
        ("Jo",                  "short"),
    ])
    def test_suspicious_names_flagged(self, name, expected_reason_fragment):
        is_susp, reason = is_suspicious_name(name)
        assert is_susp is True
        assert expected_reason_fragment in reason, (
            f"Expected {expected_reason_fragment!r} in reason, got {reason!r}"
        )
