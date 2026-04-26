"""
End-to-end audit pipeline.

`run_headcheck()` is the single programmatic entry point. CLI, TUI and
library callers all go through it. It does not print — instead it accepts
an optional `progress` callback that gets invoked at each stage boundary,
which keeps the pipeline UI-agnostic.
"""
import os
import re
from datetime import datetime
from typing import Callable, Optional

from .constants import (
    PHOTO_NOT_LOADED,
    STAGE_EXTRACT, STAGE_PAYROLL, STAGE_REPORTS, STAGE_XLSX,
    STAGE_SUSPECTS, STAGE_SNAPSHOT, STAGE_DONE,
    slugify,
)
from .parsing import extract_profiles
from .payroll import load_payroll_detailed, cross_reference
from .reports import (
    generate_html, generate_pdf, generate_xlsx,
    export_suspects_csv, export_snapshot_json,
)


# Type alias for the progress callback. Receives the stage identifier (one
# of the STAGE_* constants) and a dict of stage-specific information.
ProgressCallback = Callable[[str, dict], None]


# Export-quality thresholds. If the exporter scrolled too fast (lazy-load
# placeholders never resolved) or has too few colleagues connected to the
# observed profiles (typical of page-admin sessions), the warning kicks in.
_LAZY_PHOTO_WARN_THRESHOLD = 0.10   # ≥10% un-loaded photos triggers warning
_LOW_MUTUAL_WARN_THRESHOLD = 0.20   # <20% with any mutual triggers warning


def _evaluate_export_quality(profiles: list[dict], diag: dict) -> list[str]:
    """
    Build a list of human-readable warnings about likely export problems.
    These are shown to the user AFTER extraction, so they can decide whether
    to re-export or trust the results.
    """
    warnings: list[str] = []
    total = len(profiles)
    if not total:
        return warnings

    # Lazy-loaded photos: the user scrolled fast (or not at all).
    not_loaded = sum(1 for p in profiles if p.get("photo_state") == PHOTO_NOT_LOADED)
    if not_loaded / total >= _LAZY_PHOTO_WARN_THRESHOLD:
        pct = round(100 * not_loaded / total)
        warnings.append(
            f"{not_loaded} of {total} profiles ({pct}%) have photos that were not "
            "loaded at export time. These are NOT flagged as suspicious, but "
            "the signal is weaker than it could be. "
            "Fix: re-open the People page, scroll slowly to the bottom "
            "so every photo gets a chance to load, then re-export."
        )

    # Mutual-connection coverage: tells us about the exporter, not the profiles.
    with_mutual = sum(1 for p in profiles if p.get("mutual_level", 0) > 0)
    if with_mutual / total < _LOW_MUTUAL_WARN_THRESHOLD:
        pct = round(100 * with_mutual / total)
        warnings.append(
            f"Only {with_mutual} of {total} profiles ({pct}%) show mutual "
            "connections. This almost always means the export was done from a "
            "page-admin account (which hides your network) or an account "
            "with limited internal connections. Scores may be systematically "
            "lower than reality. "
            "Fix: have a non-admin employee with broad internal connections "
            "export the page from their own LinkedIn session."
        )

    # No profiles of a given base: might indicate LinkedIn changed its DOM.
    if diag.get("anchors_found", 0) > 0 and total == 0:
        warnings.append(
            "Profile card anchors were found, but no profiles could be parsed. "
            "LinkedIn may have changed its HTML structure. Run with --debug "
            "to see the extraction diagnostics."
        )

    return warnings


def run_headcheck(
    html_path: str,
    company: str = "Company",
    payroll_path: Optional[str] = None,
    lang: str = "en",
    out_dir: str = "./output",
    progress: Optional[ProgressCallback] = None,
) -> dict:
    """
    Run the full HeadCheck pipeline and return a structured result.

    This function is the programmatic entry point for both the CLI and the
    TUI. It does NOT print anything — callers get all information via the
    returned dict, and may optionally pass a `progress` callback that will
    be invoked at each stage boundary with (stage_name, details_dict).

    Parameters
    ----------
    html_path : str
        Path to the LinkedIn People page HTML snapshot.
    company : str
        Company name used in report headers and output filenames.
    payroll_path : str | None
        Optional path to a .csv/.xlsx/.xls payroll file for cross-reference.
    lang : str
        Language code of the LinkedIn interface used during export.
    out_dir : str
        Directory where output files are written. Created if missing.
    progress : callable | None
        Optional callback(stage: str, info: dict) invoked between stages.
        See STAGE_* constants in headcheck.constants.

    Returns
    -------
    dict with keys: config, profiles, diagnostics, warnings, payroll,
    outputs, stats. See module README for full schema.
    """
    def _emit(stage: str, **info):
        if progress is not None:
            progress(stage, info)

    os.makedirs(out_dir, exist_ok=True)
    date_slug = datetime.now().strftime("%Y-%m-%d")
    co_slug   = re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_") or "company"
    base      = f"headcheck_{co_slug}_{date_slug}"

    # ── Stage 1: extract ──
    profiles, diag = extract_profiles(html_path, lang)
    warnings_list = _evaluate_export_quality(profiles, diag)
    _emit(STAGE_EXTRACT, count=len(profiles), diagnostics=diag, warnings=warnings_list)

    # ── Stage 2: payroll (optional) ──
    payroll_info = {"loaded": 0, "detected_col": None, "has_payroll": False}
    if payroll_path:
        names, col_idx = load_payroll_detailed(payroll_path)
        payroll_info["loaded"] = len(names)
        payroll_info["detected_col"] = col_idx
        if names:
            profiles = cross_reference(profiles, names)
            payroll_info["has_payroll"] = True
    _emit(STAGE_PAYROLL, **payroll_info)

    has_payroll = payroll_info["has_payroll"]

    # ── Stage 3: reports ──
    html_out = os.path.join(out_dir, f"{base}.html")
    pdf_out  = os.path.join(out_dir, f"{base}.pdf")
    generate_html(profiles, company, has_payroll, html_out)
    generate_pdf(profiles, company, has_payroll, pdf_out)
    _emit(STAGE_REPORTS, html=html_out, pdf=pdf_out)

    # ── Stage 4: Excel workbook for HR ──
    xlsx_out = os.path.join(out_dir, f"{base}.xlsx")
    xlsx_rows = generate_xlsx(profiles, company, has_payroll, xlsx_out)
    _emit(STAGE_XLSX, path=xlsx_out, rows=xlsx_rows)

    # ── Stage 5: suspects CSV ──
    csv_out = os.path.join(out_dir, f"{base}_suspects.csv")
    suspects_count = export_suspects_csv(profiles, has_payroll, csv_out)
    _emit(STAGE_SUSPECTS, path=csv_out, count=suspects_count)

    # ── Stats (needed by the snapshot) ──
    stats = {
        "total":  len(profiles),
        "red":    sum(1 for p in profiles if p["risk"] == "red"),
        "yellow": sum(1 for p in profiles if p["risk"] == "yellow"),
        "green":  sum(1 for p in profiles if p["risk"] == "green"),
        "suspects_exported": suspects_count,
    }

    # ── Stage 6: snapshot JSON for later diffing ──
    snap_out = os.path.join(out_dir, f"{base}.json")
    export_snapshot_json(profiles, company, has_payroll, stats, snap_out)
    _emit(STAGE_SNAPSHOT, path=snap_out, count=len(profiles))

    result = {
        "config": {
            "html_path": html_path,
            "company": company,
            "payroll_path": payroll_path,
            "lang": lang,
            "out_dir": out_dir,
        },
        "profiles": profiles,
        "diagnostics": diag,
        "warnings": warnings_list,
        "payroll": payroll_info,
        "outputs": {"html": html_out, "pdf": pdf_out,
                    "xlsx": xlsx_out, "suspects_csv": csv_out,
                    "snapshot": snap_out},
        "stats": stats,
    }
    _emit(STAGE_DONE, **stats)
    return result
