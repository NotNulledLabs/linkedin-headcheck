"""
Command-line interface.

Three modes, all routed through `main()`:
  - `headcheck`                       → interactive wizard (see tui.py)
  - `headcheck --html ... --company`  → classic flag-based CLI
  - `headcheck diff old.json new.json` → snapshot diff subcommand
"""
import argparse
import json
import sys

from .constants import (
    VERSION, BRAND_NAME, BRAND_URL, REPO_URL, MUTUAL_PATTERNS,
    STAGE_EXTRACT, STAGE_PAYROLL, STAGE_REPORTS, STAGE_XLSX,
    STAGE_SUSPECTS, STAGE_SNAPSHOT,
)
from .pipeline import run_headcheck
from .reports.snapshot import diff_snapshots, export_diff_csv


# Diff buckets that indicate a change occurred. The "unchanged" bucket is
# excluded — those profiles are noise in a diff report, and counting only
# these five tells the caller "anything happened?".
_DIFF_CHANGE_BUCKETS = ("appeared", "disappeared", "risk_up", "risk_down", "score_changed")


def _cli_progress_printer(debug: bool = False):
    """
    Build a progress callback that reproduces the classic CLI output style.
    Kept as a module-level factory so the TUI can construct its own callback
    independently without any CLI-specific strings leaking.
    """
    def printer(stage: str, info: dict):
        if stage == STAGE_EXTRACT:
            count = info["count"]
            print("[ 1/6 ] Extracting profiles…")
            print(f"        {count} unique profiles found")
            if count == 0:
                print(
                    "        ⚠  No profiles were extracted. The HTML snapshot may be\n"
                    "           incomplete (did you scroll to the bottom before copying?)\n"
                    "           or LinkedIn may have changed its DOM structure.\n"
                )
            if debug:
                print("   [debug] extraction diagnostics:", info["diagnostics"])
            if info["warnings"]:
                import textwrap
                print("        ⚠  Export-quality warnings:")
                for w in info["warnings"]:
                    wrapped = textwrap.fill(
                        w, width=78,
                        initial_indent="           • ",
                        subsequent_indent="             ",
                    )
                    print(wrapped + "\n")

        elif stage == STAGE_PAYROLL:
            if info["has_payroll"]:
                print("[ 2/6 ] Loading payroll…")
                print(f"   Auto-detected name column index: {info['detected_col']}")
                print(f"        {info['loaded']} employees loaded")
            elif info["loaded"] == 0 and info["detected_col"] is None:
                print("[ 2/6 ] No payroll file — skipping cross-reference")
            else:
                # payroll path given but no names found
                print("[ 2/6 ] Loading payroll…")
                print("        ⚠  Payroll file parsed but no names were detected — skipping cross-reference")

        elif stage == STAGE_REPORTS:
            print("[ 3/6 ] Generating reports…")
            print(f"  ✔ HTML report  →  {info['html']}")
            print(f"  ✔ PDF report   →  {info['pdf']}")

        elif stage == STAGE_XLSX:
            print("[ 4/6 ] Generating Excel workbook for HR…")
            print(f"  ✔ Excel        →  {info['path']}  ({info['rows']} profiles)")

        elif stage == STAGE_SUSPECTS:
            print("[ 5/6 ] Exporting suspects list…")
            print(f"  ✔ Suspects CSV →  {info['path']}  ({info['count']} profiles)")

        elif stage == STAGE_SNAPSHOT:
            print("[ 6/6 ] Saving snapshot for future diffs…")
            print(f"  ✔ JSON         →  {info['path']}  ({info['count']} profiles)")

    return printer



# ─────────────────────────────────────────────────────────────────────────────
# DIFF SUBCOMMAND
# ─────────────────────────────────────────────────────────────────────────────

def _format_diff_plain(diff: dict) -> str:
    """Render a snapshot diff as plain text — no colour, works anywhere."""
    meta = diff["meta"]
    lines = []
    lines.append("")
    lines.append("  HeadCheck — Snapshot Diff")
    lines.append("  " + "─" * 46)
    lines.append(f"  Old: {meta['old_path']}  ({meta.get('old_generated_at') or 'unknown date'})")
    lines.append(f"  New: {meta['new_path']}  ({meta.get('new_generated_at') or 'unknown date'})")
    lines.append("")

    def _section(title: str, items: list, formatter):
        if not items:
            return
        lines.append(f"  {title}  ({len(items)})")
        lines.append("  " + "─" * 46)
        for p in items:
            lines.append("    " + formatter(p))
        lines.append("")

    _section("✚ Appeared (new since last audit)",
             diff["appeared"],
             lambda p: f"{p.get('name',''):30s}  risk={p.get('risk','?'):6s}  {p.get('profile_url','')}")
    _section("✖ Disappeared (no longer in company)",
             diff["disappeared"],
             lambda p: f"{p.get('name',''):30s}  risk={p.get('risk','?'):6s}  {p.get('profile_url','')}")
    _section("⬆ Risk worsened",
             diff["risk_up"],
             lambda p: f"{p['name']:30s}  {p['old_risk']} → {p['new_risk']}   score {p['old_score']} → {p['new_score']}")
    _section("⬇ Risk improved",
             diff["risk_down"],
             lambda p: f"{p['name']:30s}  {p['old_risk']} → {p['new_risk']}   score {p['old_score']} → {p['new_score']}")
    _section("~ Score drift (same risk)",
             diff["score_changed"],
             lambda p: f"{p['name']:30s}  score {p['old_score']} → {p['new_score']}  ({p['new_risk']})")

    total_changes = sum(len(diff[k]) for k in
                        _DIFF_CHANGE_BUCKETS)
    if total_changes == 0:
        lines.append("  Nothing changed between the two snapshots.")
        lines.append("")
    else:
        lines.append(f"  Summary: {total_changes} changes · "
                     f"{len(diff['unchanged'])} profiles unchanged")
        lines.append("")
    return "\n".join(lines)


def _format_diff_rich(diff: dict):
    """Render a diff using rich — colour, panels, nicer typography."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    console = Console()
    meta = diff["meta"]

    console.print()
    console.print("[bold cyan]HeadCheck — Snapshot Diff[/bold cyan]")
    console.print(f"[dim]{'─' * 46}[/dim]")
    console.print(f"[dim]Old:[/dim] {meta['old_path']}  [dim]({meta.get('old_generated_at') or '—'})[/dim]")
    console.print(f"[dim]New:[/dim] {meta['new_path']}  [dim]({meta.get('new_generated_at') or '—'})[/dim]")
    console.print()

    def _section(title: str, items: list, cols: list, extractor, style: str):
        if not items:
            return
        t = Table(title=f"{title}  ({len(items)})", title_style=style, title_justify="left",
                  show_header=True, header_style="bold", box=None, padding=(0, 1))
        for col in cols:
            t.add_column(col)
        for p in items:
            t.add_row(*extractor(p))
        console.print(t)
        console.print()

    _section(
        "✚ Appeared (new since last audit)",
        diff["appeared"],
        ["Name", "Risk", "URL"],
        lambda p: (p.get("name", ""), p.get("risk", "?"), p.get("profile_url", "")),
        "bold green",
    )
    _section(
        "✖ Disappeared (no longer listed)",
        diff["disappeared"],
        ["Name", "Was", "URL"],
        lambda p: (p.get("name", ""), p.get("risk", "?"), p.get("profile_url", "")),
        "bold magenta",
    )
    _section(
        "⬆ Risk worsened",
        diff["risk_up"],
        ["Name", "Risk", "Score"],
        lambda p: (p["name"], f"{p['old_risk']} → {p['new_risk']}",
                   f"{p['old_score']} → {p['new_score']}"),
        "bold red",
    )
    _section(
        "⬇ Risk improved",
        diff["risk_down"],
        ["Name", "Risk", "Score"],
        lambda p: (p["name"], f"{p['old_risk']} → {p['new_risk']}",
                   f"{p['old_score']} → {p['new_score']}"),
        "bold green",
    )
    _section(
        "~ Score drift (same risk)",
        diff["score_changed"],
        ["Name", "Score", "Risk"],
        lambda p: (p["name"], f"{p['old_score']} → {p['new_score']}", p["new_risk"]),
        "bold yellow",
    )

    total_changes = sum(len(diff[k]) for k in
                        _DIFF_CHANGE_BUCKETS)
    unchanged = len(diff["unchanged"])
    if total_changes == 0:
        console.print(Panel("Nothing changed between the two snapshots.",
                            border_style="dim"))
    else:
        console.print(Panel(f"[bold]{total_changes}[/bold] changes · "
                            f"[dim]{unchanged} profiles unchanged[/dim]",
                            title="Summary", title_align="left", border_style="cyan"))


def _run_diff(argv: list[str]) -> int:
    """
    Entry point for `headcheck diff old.json new.json [--csv path]`.
    Returns a shell-friendly exit code:
        0 — snapshots compared, no changes
        1 — snapshots compared, at least one change detected
        2 — bad usage or I/O error
    """
    parser = argparse.ArgumentParser(
        prog="headcheck diff",
        description="Compare two HeadCheck JSON snapshots and report what changed.",
    )
    parser.add_argument("old", help="Path to the older snapshot (.json)")
    parser.add_argument("new", help="Path to the newer snapshot (.json)")
    parser.add_argument("--csv", help="Optional path to also write a CSV export of the diff")
    parser.add_argument("--plain", action="store_true",
                        help="Plain text output (no colour, no rich)")
    args = parser.parse_args(argv)

    try:
        diff = diff_snapshots(args.old, args.new)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in snapshot file — {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    # Try rich unless the user asked for plain output or rich is missing.
    used_rich = False
    if not args.plain:
        try:
            _format_diff_rich(diff)
            used_rich = True
        except ImportError:
            pass
    if not used_rich:
        print(_format_diff_plain(diff))

    if args.csv:
        n = export_diff_csv(diff, args.csv)
        print(f"\n  ✔ Diff CSV  →  {args.csv}  ({n} rows)")

    has_changes = any(diff[k] for k in
                      _DIFF_CHANGE_BUCKETS)
    return 1 if has_changes else 0



# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # Subcommand dispatch: `headcheck diff ...` runs the snapshot comparator.
    # The usual flag-based CLI and the interactive wizard are the default paths.
    if len(sys.argv) >= 2 and sys.argv[1] == "diff":
        sys.exit(_run_diff(sys.argv[2:]))

    # When the user invokes `headcheck` with no arguments, drop into the
    # interactive wizard. The CLI with flags stays untouched for scripting
    # and for users who prefer it.
    if len(sys.argv) == 1:
        # Lazy import — keeps `headcheck diff` and the flag-based CLI working
        # even if questionary/rich aren't installed.
        from .tui import _run_interactive
        sys.exit(_run_interactive())

    parser = argparse.ArgumentParser(
        prog="headcheck",
        description="LinkedIn HeadCheck — Workforce Verification Tool by Not Nulled Labs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Run with no arguments for an interactive wizard, or use flags below for
scripting:

  python headcheck.py                                              (interactive)
  python headcheck.py --html people.html --company "Acme Corp"
  python headcheck.py --html people.html --company "Acme Corp" --payroll staff.xlsx
  python headcheck.py --html people.html --company "Acme Corp" --payroll nomina.csv --lang es
  python headcheck.py --html people.html --company "Acme Corp" --out ./output

Compare two audits with the diff subcommand:

  python headcheck.py diff old.json new.json
  python headcheck.py diff old.json new.json --csv changes.csv

Supported payroll formats: .csv  .xlsx  .xls
Supported languages (--lang): en  es  fr  de  pt  it

{BRAND_NAME}  ·  {BRAND_URL}
{REPO_URL}
        """
    )
    parser.add_argument("--html",    required=True,   help="Path to saved LinkedIn People page HTML")
    parser.add_argument("--company", default="Company", help="Company name for report headers")
    parser.add_argument("--payroll", default=None,    help="Optional payroll file (.csv, .xlsx, .xls)")
    parser.add_argument("--lang",    default="en",    choices=list(MUTUAL_PATTERNS.keys()),
                        help="Language of the LinkedIn interface used during export (default: en)")
    parser.add_argument("--out",     default="./output",     help="Output directory (default: ./output)")
    parser.add_argument("--debug",   action="store_true",
                        help="Print extraction diagnostics to help pinpoint parser issues")
    args = parser.parse_args()

    # Header block — keeps the current look of the CLI intact.
    print(f"\n  LinkedIn HeadCheck  v{VERSION}  ·  {BRAND_NAME}")
    print(f"  {'─'*46}")
    print(f"  Company  : {args.company}")
    print(f"  HTML     : {args.html}")
    print(f"  Language : {args.lang}")
    if args.payroll:
        print(f"  Payroll  : {args.payroll}")
    print(f"  Output   : {args.out}\n")

    try:
        result = run_headcheck(
            html_path=args.html,
            company=args.company,
            payroll_path=args.payroll,
            lang=args.lang,
            out_dir=args.out,
            progress=_cli_progress_printer(debug=args.debug),
        )
    except (ValueError, FileNotFoundError) as e:
        # Library-style errors propagate from payroll loading or report
        # writing. Translate to a friendly CLI exit instead of a traceback.
        print(f"\n  Error: {e}", file=sys.stderr)
        sys.exit(2)

    s = result["stats"]
    print(f"\n  Done.  🔴 {s['red']} high-risk  ·  🟡 {s['yellow']} review  ·  🟢 {s['green']} low-risk")
    print(f"  Reports saved to: {args.out}\n")


if __name__ == "__main__":
    main()
