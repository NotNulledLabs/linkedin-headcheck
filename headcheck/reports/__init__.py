"""
Report generators.

Each module in this subpackage produces one of the output files:
  - html      : interactive standalone HTML
  - pdf       : executive PDF
  - xlsx      : Excel workbook for HR
  - suspects  : red+yellow CSV
  - snapshot  : machine-readable JSON + diff helpers
"""
from .html import generate_html
from .pdf import generate_pdf
from .xlsx import generate_xlsx
from .suspects import export_suspects_csv
from .snapshot import export_snapshot_json, diff_snapshots, export_diff_csv

__all__ = [
    "generate_html",
    "generate_pdf",
    "generate_xlsx",
    "export_suspects_csv",
    "export_snapshot_json",
    "diff_snapshots",
    "export_diff_csv",
]
