#!/usr/bin/env python3
"""
Backward-compatible launcher.

`python headcheck.py …` keeps working exactly as it did in 1.x. The actual
implementation lives in the `headcheck/` package; this file just dispatches
to it. Library users should `from headcheck import run_headcheck, …` and
ignore this file.
"""
from headcheck.cli import main

if __name__ == "__main__":
    main()
