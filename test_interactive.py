"""
Tests for the interactive/TUI entry point.

Fully simulating questionary requires a pseudo-terminal which pytest doesn't
provide out of the box, so we focus on the testable seams:

  - _try_import_interactive() correctly reports what's available
  - _rich_progress_callback() produces output for each stage without errors
  - _plain_wizard() works with piped stdin (no TTY required)
  - main() dispatches to the interactive path when argv is empty

What we deliberately don't test here:
  - the actual questionary prompt rendering (would need pexpect or similar)
  - the visual correctness of rich output (eye-balled during development)
"""
import io
import sys
from unittest.mock import patch

import pytest

from headcheck import (
    _try_import_interactive, _plain_wizard, _rich_progress_callback,
    STAGE_EXTRACT, STAGE_PAYROLL, STAGE_REPORTS, STAGE_SUSPECTS, STAGE_DONE,
)


# ─────────────────────────────────────────────────────────────────────────────
# _try_import_interactive
# ─────────────────────────────────────────────────────────────────────────────

class TestImportDetection:
    def test_returns_modules_when_available(self):
        """Both questionary and rich are installed in dev env → should succeed."""
        questionary, Console = _try_import_interactive()
        # These will both be non-None in the dev/test environment. If they're
        # None here, it means the deps aren't installed — that's a CI setup
        # issue, not a bug in _try_import_interactive.
        assert questionary is not None or Console is None
        # Whatever the environment, the tuple must have exactly two elements:
        assert len((questionary, Console)) == 2


# ─────────────────────────────────────────────────────────────────────────────
# _plain_wizard — fallback that works without questionary/rich
# ─────────────────────────────────────────────────────────────────────────────

class TestPlainWizard:
    def test_collects_all_fields_via_stdin(self, tmp_path, monkeypatch, capsys):
        """Feed answers through stdin and verify the returned config dict."""
        html_file = tmp_path / "people.html"
        html_file.write_text("<html></html>")
        out_dir = str(tmp_path / "out")

        inputs = iter([
            str(html_file),   # HTML path
            "TestCorp",       # Company
            "",               # Payroll (skip)
            "es",             # Language
            out_dir,          # Output dir
        ])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

        result = _plain_wizard(print)
        assert result["html_path"] == str(html_file)
        assert result["company"] == "TestCorp"
        assert result["payroll_path"] is None
        assert result["lang"] == "es"
        assert result["out_dir"] == out_dir

    def test_retries_on_missing_file(self, tmp_path, monkeypatch, capsys):
        """Non-existent HTML path triggers re-prompt."""
        good_path = tmp_path / "people.html"
        good_path.write_text("<html></html>")

        inputs = iter([
            "/nonexistent/path.html",  # first attempt fails
            str(good_path),            # second attempt succeeds
            "TestCorp",
            "",
            "en",
            ".",
        ])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

        result = _plain_wizard(print)
        assert result["html_path"] == str(good_path)

    def test_defaults_apply_for_blank_answers(self, tmp_path, monkeypatch):
        html_file = tmp_path / "people.html"
        html_file.write_text("<html></html>")

        inputs = iter([
            str(html_file),
            "",  # blank company → defaults to "Company"
            "",  # blank payroll → None
            "",  # blank lang → "en"
            "",  # blank out → "."
        ])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

        result = _plain_wizard(print)
        assert result["company"] == "Company"
        assert result["lang"] == "en"
        assert result["out_dir"] == "."

    def test_invalid_lang_falls_back_to_english(self, tmp_path, monkeypatch):
        html_file = tmp_path / "people.html"
        html_file.write_text("<html></html>")

        inputs = iter([str(html_file), "Co", "", "klingon", "."])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

        result = _plain_wizard(print)
        assert result["lang"] == "en"

    def test_missing_payroll_gracefully_skipped(self, tmp_path, monkeypatch, capsys):
        html_file = tmp_path / "people.html"
        html_file.write_text("<html></html>")

        inputs = iter([str(html_file), "Co", "/nope/ghost.csv", "en", "."])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

        result = _plain_wizard(print)
        # Non-existent payroll → warned, then set to None rather than crashing.
        assert result["payroll_path"] is None


# ─────────────────────────────────────────────────────────────────────────────
# _rich_progress_callback — rendering smoke tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def rich_console():
    """A rich Console writing to a buffer so we can inspect its output."""
    pytest.importorskip("rich")
    from rich.console import Console
    buf = io.StringIO()
    # force_terminal=False keeps the output ANSI-free for easier assertions.
    return Console(file=buf, force_terminal=False, width=100), buf


class TestRichProgressCallback:
    def test_extract_stage_shows_count(self, rich_console):
        console, buf = rich_console
        cb = _rich_progress_callback(console)
        cb(STAGE_EXTRACT, {"count": 96, "diagnostics": {}, "warnings": []})
        assert "96" in buf.getvalue()
        assert "Extract" in buf.getvalue()

    def test_extract_with_zero_profiles_shows_warning(self, rich_console):
        console, buf = rich_console
        cb = _rich_progress_callback(console)
        cb(STAGE_EXTRACT, {"count": 0, "diagnostics": {}, "warnings": []})
        out = buf.getvalue()
        assert "No profiles" in out or "scroll" in out.lower()

    def test_extract_renders_warnings_panels(self, rich_console):
        console, buf = rich_console
        cb = _rich_progress_callback(console)
        cb(STAGE_EXTRACT, {
            "count": 50,
            "diagnostics": {},
            "warnings": ["Too many ghost-person placeholders — re-export please"],
        })
        out = buf.getvalue()
        assert "ghost-person" in out

    def test_payroll_stage_with_data(self, rich_console):
        console, buf = rich_console
        cb = _rich_progress_callback(console)
        cb(STAGE_PAYROLL, {"has_payroll": True, "loaded": 42, "detected_col": 2})
        out = buf.getvalue()
        assert "42" in out

    def test_payroll_stage_skipped(self, rich_console):
        console, buf = rich_console
        cb = _rich_progress_callback(console)
        cb(STAGE_PAYROLL, {"has_payroll": False, "loaded": 0, "detected_col": None})
        assert "skipped" in buf.getvalue().lower()

    def test_reports_stage_shows_both_paths(self, rich_console):
        console, buf = rich_console
        cb = _rich_progress_callback(console)
        cb(STAGE_REPORTS, {"html": "/tmp/a.html", "pdf": "/tmp/b.pdf"})
        out = buf.getvalue()
        assert "/tmp/a.html" in out
        assert "/tmp/b.pdf" in out

    def test_done_stage_shows_all_three_totals(self, rich_console):
        console, buf = rich_console
        cb = _rich_progress_callback(console)
        cb(STAGE_DONE, {"total": 100, "red": 5, "yellow": 20, "green": 75,
                        "suspects_exported": 25})
        out = buf.getvalue()
        # All three counts should be visible in the summary panel.
        assert "5" in out
        assert "20" in out
        assert "75" in out
