"""
Shared pytest configuration.

Adds the project root to sys.path so `import headcheck` works regardless of
where pytest is invoked from, and exposes fixture paths as module-level
constants.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SYNTHETIC_HTML = FIXTURES_DIR / "synthetic_people.html"
FALLBACK_HTML = FIXTURES_DIR / "fallback_selectors.html"
PAYROLL_WITH_ID = FIXTURES_DIR / "payroll_with_id_col.csv"
PAYROLL_NO_HEADER = FIXTURES_DIR / "payroll_no_header.csv"

# Optional: a real-world LinkedIn snapshot for integration tests. Tests that need it should skip if missing,
# so the suite stays green on a fresh clone without the private file.
REAL_SNAPSHOT_HTML = PROJECT_ROOT / "people.html"
