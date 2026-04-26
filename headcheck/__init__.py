"""
LinkedIn HeadCheck — workforce verification tool.

Package layout:
    constants     — version, brand strings, photo states, stage names
    scoring       — count_mutual, is_suspicious_name, _score, _risk
    parsing       — extract_profiles + DOM helpers (cascading selectors)
    payroll       — load_payroll[_detailed], cross_reference, column auto-detect
    reports/      — html, pdf, xlsx, suspects, snapshot generators
    pipeline      — run_headcheck (the public entry point) + warnings
    cli           — argparse main + diff subcommand
    tui           — interactive wizard (questionary + rich)

Public API for library users:
    from headcheck import run_headcheck, diff_snapshots, ...

Run as a script:
    python -m headcheck                                  # interactive wizard
    python -m headcheck --html people.html --company X   # classic CLI
    python -m headcheck diff old.json new.json           # snapshot diff
"""
from .constants import (
    VERSION, BRAND_NAME, BRAND_URL, REPO_URL, MAX_SCORE,
    MUTUAL_PATTERNS,
    PHOTO_LOADED, PHOTO_NOT_LOADED, PHOTO_ABSENT,
    STAGE_EXTRACT, STAGE_PAYROLL, STAGE_REPORTS, STAGE_XLSX,
    STAGE_SUSPECTS, STAGE_SNAPSHOT, STAGE_DONE,
)
from .scoring import (
    count_mutual, is_suspicious_name, _score, _risk,
    RISK_GREEN_MIN, RISK_YELLOW_MIN,
)
from .parsing import extract_profiles, _classify_photo
from .payroll import (
    load_payroll, load_payroll_detailed, cross_reference,
    _best_name_col, _NAME_HEADER_STRONG, _NAME_HEADER_WEAK, _NAME_HEADER_RE,
)
from .reports import (
    generate_html, generate_pdf, generate_xlsx,
    export_suspects_csv, export_snapshot_json,
    diff_snapshots, export_diff_csv,
)
# Some private helpers are referenced by the test suite. Re-exporting them
# here keeps the existing tests working without forcing them to know the
# internal package layout.
from .reports.snapshot import _load_snapshot
from .pipeline import run_headcheck, _evaluate_export_quality
from .cli import _cli_progress_printer, main
from .tui import _try_import_interactive, _plain_wizard, _rich_progress_callback


__all__ = [
    # Library API
    "run_headcheck",
    "diff_snapshots",
    "extract_profiles",
    "load_payroll",
    "load_payroll_detailed",
    "cross_reference",
    "count_mutual",
    "is_suspicious_name",
    "generate_html",
    "generate_pdf",
    "generate_xlsx",
    "export_suspects_csv",
    "export_snapshot_json",
    "export_diff_csv",
    # Constants
    "VERSION", "BRAND_NAME", "BRAND_URL", "REPO_URL", "MAX_SCORE",
    "MUTUAL_PATTERNS",
    "PHOTO_LOADED", "PHOTO_NOT_LOADED", "PHOTO_ABSENT",
    "STAGE_EXTRACT", "STAGE_PAYROLL", "STAGE_REPORTS", "STAGE_XLSX",
    "STAGE_SUSPECTS", "STAGE_SNAPSHOT", "STAGE_DONE",
    "RISK_GREEN_MIN", "RISK_YELLOW_MIN",
    # CLI entry point
    "main",
]
