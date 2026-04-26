"""
Constants shared across the package.

Anything that can be imported from any other module without creating cycles
lives here: brand strings, scoring caps, language patterns, photo state
identifiers, pipeline progress stages, and shared helpers like `slugify()`.
"""
import re

# ─────────────────────────────────────────────────────────────────────────────
# Branding & version
# ─────────────────────────────────────────────────────────────────────────────

VERSION = "2.0.1"

BRAND_NAME = "Not Nulled Labs"
BRAND_URL  = "https://notnulled.com/"
REPO_URL   = "https://github.com/NotNulledLabs"

MAX_SCORE = 10


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(s: str, default: str = "company") -> str:
    """
    Convert an arbitrary string to a filesystem- and URL-safe slug.

    Used to derive output filenames and localStorage keys from the company
    name. Centralised here so the pipeline and the HTML report can never
    produce divergent slugs for the same input.
    """
    return _SLUG_NON_ALNUM.sub("_", s.lower()).strip("_") or default


# ─────────────────────────────────────────────────────────────────────────────
# Multilingual mutual-connection detection
# ─────────────────────────────────────────────────────────────────────────────
#
# Each entry is a regex that matches the language-specific phrase LinkedIn
# uses for "mutual connection(s)". Used by `count_mutual` together with
# digit/conjunction heuristics.

MUTUAL_PATTERNS = {
    "en": re.compile(r"mutual connection", re.I),
    "es": re.compile(r"conexi[oó]n en com[uú]n|conexiones en com[uú]n", re.I),
    "fr": re.compile(r"relation commune|relations communes", re.I),
    "de": re.compile(r"gemeinsame.{0,6}kontakt", re.I),
    "pt": re.compile(r"conex[aã]o em comum|conex[oõ]es em comum", re.I),
    "it": re.compile(r"collegamento in comune|collegamenti in comune", re.I),
}


# ─────────────────────────────────────────────────────────────────────────────
# Photo presence states
# ─────────────────────────────────────────────────────────────────────────────
#
# Tri-state classification for profile photos. Only PHOTO_ABSENT forces red.
# PHOTO_NOT_LOADED is an export-quality issue (lazy-load placeholder),
# not a property of the profile itself.

PHOTO_LOADED      = "loaded"
PHOTO_NOT_LOADED  = "not_loaded"
PHOTO_ABSENT      = "absent"

# LinkedIn's lazy-load placeholder is a 1×1 transparent GIF served as a
# data: URL. Recognising this byte-prefix is the secondary heuristic when
# the `ghost-person` CSS class is missing.
LINKEDIN_GHOST_B64 = "data:image/gif;base64,R0lGODlhAQABAIA"


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline progress stages
# ─────────────────────────────────────────────────────────────────────────────
#
# `run_headcheck()` invokes the caller's progress callback with one of these
# stage strings as the first argument, plus a dict with stage-specific data.
# CLI and TUI front-ends use these to render their own progress UI.

STAGE_EXTRACT   = "extract"
STAGE_PAYROLL   = "payroll"
STAGE_REPORTS   = "reports"
STAGE_XLSX      = "xlsx"
STAGE_SUSPECTS  = "suspects"
STAGE_SNAPSHOT  = "snapshot"
STAGE_DONE      = "done"
