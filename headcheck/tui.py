"""
Interactive terminal UI.

Activated when `headcheck` is invoked with no arguments. Powered by
`questionary` (prompts) and `rich` (progress + results panel) when those
optional libraries are installed; falls back to a plain stdin/stdout
wizard with no third-party deps if either is missing.
"""
import os

from .constants import (
    VERSION, BRAND_NAME, MUTUAL_PATTERNS,
    STAGE_EXTRACT, STAGE_PAYROLL, STAGE_REPORTS, STAGE_XLSX,
    STAGE_SUSPECTS, STAGE_SNAPSHOT, STAGE_DONE,
)
from .pipeline import run_headcheck
from .cli import _cli_progress_printer


def _try_import_interactive():
    """
    Attempt to import questionary and rich. Returns (questionary, rich_console
    Console class) on success, (None, None) if either is missing.
    """
    try:
        import questionary
        from rich.console import Console
        return questionary, Console
    except ImportError:
        return None, None


def _plain_wizard(console_print) -> dict:
    """
    Zero-dependency fallback wizard. Used when questionary / rich aren't
    installed. Same questions, much uglier input loop.
    """
    console_print("\n  LinkedIn HeadCheck — interactive mode (plain fallback)\n")

    while True:
        html = input("  HTML snapshot path: ").strip()
        if html and os.path.isfile(html):
            break
        print("  ✗ File not found. Try again.")

    company = input("  Company name [Company]: ").strip() or "Company"

    payroll = input("  Payroll file (optional, blank to skip): ").strip() or None
    if payroll and not os.path.isfile(payroll):
        print(f"  ⚠  {payroll!r} not found — continuing without payroll.")
        payroll = None

    langs = list(MUTUAL_PATTERNS.keys())
    lang = input(f"  LinkedIn language {langs} [en]: ").strip() or "en"
    if lang not in langs:
        lang = "en"

    out = input("  Output directory [./output]: ").strip() or "./output"

    return dict(html_path=html, company=company, payroll_path=payroll,
                lang=lang, out_dir=out)


def _questionary_wizard(questionary) -> dict | None:
    """
    Friendly wizard powered by questionary. Returns None if the user aborts
    (Ctrl+C or ESC on any prompt), else the configuration dict.
    """
    def _file_exists(v: str) -> bool | str:
        if not v:
            return "This field is required"
        if not os.path.isfile(v):
            return f"File not found: {v}"
        return True

    def _file_or_empty(v: str) -> bool | str:
        if not v:
            return True
        if not os.path.isfile(v):
            return f"File not found: {v}"
        return True

    answers = questionary.form(
        html_path=questionary.path(
            "HTML snapshot path:",
            validate=_file_exists,
        ),
        company=questionary.text(
            "Company name:",
            default="Company",
            instruction="(used in report headers and filenames)",
        ),
        payroll_path=questionary.path(
            "Payroll file (optional, leave blank to skip):",
            default="",
            validate=_file_or_empty,
        ),
        lang=questionary.select(
            "LinkedIn interface language used during export:",
            choices=list(MUTUAL_PATTERNS.keys()),
            default="en",
        ),
        out_dir=questionary.path(
            "Output directory:",
            default="./output",
        ),
    ).ask()

    if answers is None:                          # user hit Ctrl+C / ESC
        return None
    # questionary.path() returns "" for skipped optional fields — normalise.
    answers["payroll_path"] = answers["payroll_path"] or None
    return answers


def _rich_progress_callback(console):
    """
    Build a progress callback that renders each stage as a rich status line.
    Closed over `console` so both header and per-stage output share the same
    terminal handler (important for colour / width detection).
    """
    from rich.panel import Panel
    from rich.table import Table

    def cb(stage: str, info: dict):
        if stage == STAGE_EXTRACT:
            console.print(f"[bold cyan]⬢ Extracting profiles[/bold cyan] "
                          f"· {info['count']} unique")
            if info["count"] == 0:
                console.print(
                    "  [yellow]⚠  No profiles were extracted. The HTML snapshot may "
                    "be incomplete (scroll to the bottom before exporting) or "
                    "LinkedIn may have changed its DOM structure.[/yellow]"
                )
            for w in info["warnings"]:
                console.print(Panel(w, title="Export quality warning",
                                    title_align="left", border_style="yellow"))

        elif stage == STAGE_PAYROLL:
            if info["has_payroll"]:
                console.print(f"[bold cyan]⬢ Payroll[/bold cyan] · "
                              f"{info['loaded']} employees "
                              f"(name column #{info['detected_col']})")
            elif info["loaded"] == 0 and info["detected_col"] is None:
                console.print("[dim]⬢ Payroll skipped (no file provided)[/dim]")
            else:
                console.print("[yellow]⬢ Payroll file had no detectable names — "
                              "cross-reference skipped[/yellow]")

        elif stage == STAGE_REPORTS:
            console.print(f"[bold cyan]⬢ Reports[/bold cyan]")
            console.print(f"  [green]✔[/green] HTML  → {info['html']}")
            console.print(f"  [green]✔[/green] PDF   → {info['pdf']}")

        elif stage == STAGE_XLSX:
            console.print(f"[bold cyan]⬢ Excel workbook for HR[/bold cyan] · "
                          f"{info['rows']} profiles")
            console.print(f"  [green]✔[/green] XLSX  → {info['path']}")

        elif stage == STAGE_SUSPECTS:
            console.print(f"[bold cyan]⬢ Suspects list[/bold cyan] · "
                          f"{info['count']} profiles")
            console.print(f"  [green]✔[/green] CSV   → {info['path']}")

        elif stage == STAGE_SNAPSHOT:
            console.print(f"[bold cyan]⬢ Snapshot[/bold cyan] · "
                          f"saved for future diffs")
            console.print(f"  [green]✔[/green] JSON  → {info['path']}")

        elif stage == STAGE_DONE:
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_row("[bold red]🔴 High risk[/bold red]",    str(info["red"]))
            table.add_row("[bold yellow]🟡 Needs review[/bold yellow]", str(info["yellow"]))
            table.add_row("[bold green]🟢 Low risk[/bold green]",  str(info["green"]))
            console.print()
            console.print(Panel(table, title="Results",
                                title_align="left", border_style="cyan"))

    return cb


def _run_interactive() -> int:
    """
    Interactive entry point. Returns an exit code.
    """
    questionary, Console = _try_import_interactive()

    if Console is not None:
        console = Console()
        _print = console.print
        # Banner
        console.print()
        console.print(f"[bold cyan]LinkedIn HeadCheck[/bold cyan] "
                      f"[dim]v{VERSION}[/dim] · {BRAND_NAME}")
        console.print(f"[dim]{'─' * 46}[/dim]\n")
    else:
        console = None
        _print = print
        _print(f"\n  LinkedIn HeadCheck  v{VERSION}  ·  {BRAND_NAME}")
        _print(f"  {'─' * 46}\n")

    # Collect answers
    if questionary is not None:
        answers = _questionary_wizard(questionary)
        if answers is None:
            _print("\n[dim]Cancelled.[/dim]" if console else "\n  Cancelled.")
            return 1
    else:
        # One-time hint: the plain wizard works but is uglier.
        _print("  (Install `questionary` and `rich` for a better experience:")
        _print("   pip install questionary rich)\n")
        answers = _plain_wizard(_print)

    # Run the pipeline with the right progress renderer
    if console is not None:
        progress = _rich_progress_callback(console)
    else:
        progress = _cli_progress_printer()

    if console is not None:
        console.print()
    try:
        run_headcheck(progress=progress, **answers)
    except Exception as e:                       # noqa: BLE001 — user-facing
        if console is not None:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
        else:
            print(f"\n  Error: {e}")
        return 2
    return 0

