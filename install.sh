#!/usr/bin/env bash
# install.sh — One-shot setup for LinkedIn HeadCheck on Linux and macOS.
#
# What it does:
#   1. Verifies Python 3.10+ is available.
#   2. Creates a virtual environment in .venv/
#   3. Installs runtime dependencies.
#   4. Optionally installs dev dependencies (interactive wizard + tests).
#   5. Prints next-step instructions.
#
# Idempotent: safe to re-run. If .venv/ already exists it'll be reused.
# Windows users: see README.md for the manual setup steps.

set -euo pipefail

# ─── Pretty output helpers ───────────────────────────────────────────────────
if [ -t 1 ]; then
    BOLD=$(tput bold); DIM=$(tput dim); RESET=$(tput sgr0)
    GREEN=$(tput setaf 2); RED=$(tput setaf 1); YELLOW=$(tput setaf 3)
else
    BOLD=""; DIM=""; RESET=""; GREEN=""; RED=""; YELLOW=""
fi

step()    { echo "${BOLD}▸${RESET} $*"; }
ok()      { echo "  ${GREEN}✓${RESET} $*"; }
warn()    { echo "  ${YELLOW}⚠${RESET} $*"; }
fail()    { echo "  ${RED}✗${RESET} $*" >&2; exit 1; }

# ─── Locate a usable Python 3.10+ ────────────────────────────────────────────
step "Looking for Python 3.10+"

PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        version=$("$candidate" -c \
            'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' \
            2>/dev/null || true)
        if [ -n "$version" ]; then
            major=${version%%.*}
            minor=${version##*.}
            if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
                PYTHON_BIN="$candidate"
                ok "Found $candidate (Python $version)"
                break
            fi
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    fail "Python 3.10 or higher not found. Install from https://python.org"
fi

# ─── Create / reuse virtualenv ───────────────────────────────────────────────
if [ -d ".venv" ]; then
    step "Reusing existing virtual environment in .venv/"
else
    step "Creating virtual environment in .venv/"
    "$PYTHON_BIN" -m venv .venv
    ok "Created"
fi

# Activate inside the script (only valid for the duration of this run)
# shellcheck source=/dev/null
source .venv/bin/activate

# ─── Install runtime deps ────────────────────────────────────────────────────
step "Installing runtime dependencies"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
ok "Runtime dependencies installed"

# ─── Optionally install dev deps ─────────────────────────────────────────────
echo
echo "${BOLD}Dev dependencies${RESET} include:"
echo "  - questionary + rich  (for the interactive wizard and colour output)"
echo "  - pytest              (to run the test suite)"
echo
read -r -p "Install them too? [Y/n] " yn
yn=${yn:-Y}
if [[ "$yn" =~ ^[Yy]$ ]]; then
    step "Installing dev dependencies"
    pip install --quiet -r requirements-dev.txt
    ok "Dev dependencies installed"

    # Quick test smoke-check, since pytest is now available
    step "Running test suite as a sanity check"
    if python -m pytest tests/ -q --no-header 2>&1 | tail -3; then
        ok "Tests passed"
    else
        warn "Some tests failed — install completed but please review the output above"
    fi
else
    warn "Skipped. The classic CLI (with --html / --company flags) works without these."
fi

# ─── Closing instructions ────────────────────────────────────────────────────
echo
echo "${BOLD}${GREEN}✓ Installation complete.${RESET}"
echo
echo "To use HeadCheck, activate the virtual environment first:"
echo
echo "    ${BOLD}source .venv/bin/activate${RESET}"
echo
echo "Then run it interactively:"
echo
echo "    ${BOLD}python headcheck.py${RESET}"
echo
echo "Or with flags for scripting:"
echo
echo "    ${BOLD}python headcheck.py --html people.html --company \"Acme Corp\"${RESET}"
echo
echo "Output files will go to ${BOLD}./output/${RESET} by default. ${DIM}Override with --out path/${RESET}"
echo
