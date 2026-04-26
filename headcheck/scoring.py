"""
Risk scoring and signal-extraction helpers.

Pure functions: no I/O, no globals. Given a profile dict, decide its score
and risk bucket. Given a snippet of text and a language, count mutual
connections. Given a name string, decide if its shape is suspicious.

The scoring rules are documented in the package README and in `_score()`'s
docstring; this module is the single source of truth for them.
"""
import re

from .constants import (
    MAX_SCORE,
    MUTUAL_PATTERNS,
    PHOTO_LOADED, PHOTO_NOT_LOADED, PHOTO_ABSENT,
)


# ─────────────────────────────────────────────────────────────────────────────
# Risk thresholds
# ─────────────────────────────────────────────────────────────────────────────
#
# These are the score boundaries between the three risk buckets. Centralising
# them here lets every report (PDF, HTML, XLSX) display the same thresholds
# without each report hard-coding its own copy. Adjust scoring by editing
# these — the README's "Risk scoring" section is generated from these values
# in the report headers.

RISK_GREEN_MIN  = 7   # >= 7 → green
RISK_YELLOW_MIN = 4   # 4–6 → yellow; <4 → red


# Score cutoff and threshold for the suspicious-name and CJK heuristics.
# Names matching this character class are considered "name-like" alphabetic
# content, so a token consisting only of such characters is not flagged
# (covers Latin, Cyrillic, Chinese, hiragana/katakana, hangul).
_NAME_LETTER_RE = re.compile(
    r"[A-Za-zÀ-ÿ\u0400-\u04FF\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]"
)

# Match any character in CJK / hiragana / katakana / hangul ranges. Used to
# avoid flagging short CJK names (like 李明) as "single very short token".
_CJK_OR_KANA_RE = re.compile(
    r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]"
)


# Count any run of digits followed by a language-agnostic "mutual" keyword.
# We match the digit and let the per-language pattern confirm the context.
_DIGIT_PATTERN = re.compile(r"\b(\d+)\b")

# Conjunctions used before the "mutual" keyword to indicate 2+ shared contacts
# ("Bill and 2 others are mutual connections", "Ana y 3 más en común", …).
_MULTI_CONJUNCTIONS = re.compile(r"\b(and|y|et|und|e)\b", re.I)


def count_mutual(text: str, lang: str = "en") -> int:
    """
    Returns 0 (none), 1 (one mention), or 2 (multiple / explicit count >= 2).
    Checks the requested language pattern plus English as fallback.
    """
    if not text:
        return 0

    # Pick the language-specific pattern (+ English fallback) and locate the
    # position where the "mutual" keyword starts, if any.
    patterns = [p for p in (MUTUAL_PATTERNS.get(lang), MUTUAL_PATTERNS["en"]) if p]
    match = next((m for m in (p.search(text) for p in patterns) if m), None)
    if not match:
        return 0

    # Explicit numeric count: "3 mutual connections", "3 conexiones en común"…
    # We only look for digits that appear *before* the keyword to avoid
    # picking up unrelated numbers later in the string.
    prefix = text[: match.start()]
    digit_match = _DIGIT_PATTERN.search(prefix)
    if digit_match and int(digit_match.group(1)) >= 2:
        return 2

    # Conjunction fallback: "Bill and Sarah are mutual connections" →
    # two or more names joined before the keyword.
    if _MULTI_CONJUNCTIONS.search(prefix):
        return 2

    return 1


def is_suspicious_name(name: str) -> tuple[bool, str]:
    """
    Returns (is_suspicious, reason).
    Flags obvious anomalies without penalising non-English names.
    """
    if not name:
        return True, "empty name"

    # All uppercase with no spaces (e.g. "JOHNSMITHACCOUNT")
    if name == name.upper() and " " not in name and len(name) > 4:
        return True, "all-caps no spaces"

    # Contains digits (e.g. "John Smith123", "user_4892")
    if re.search(r"\d", name):
        return True, "contains digits"

    # Contains @ or common ID characters
    if re.search(r"[@_]", name):
        return True, "contains @ or _"

    # Only initials: "A. B." or "J.K." or single letter words only
    tokens = name.split()
    if tokens and all(re.match(r"^[A-Za-z]\.?$", t) for t in tokens):
        return True, "initials only"

    # Single token shorter than 3 chars (no surname).
    # Exception: CJK names are commonly 2 characters (e.g. 李明) and each
    # character carries meaning, so we don't flag them here.
    if len(tokens) == 1 and len(tokens[0]) < 3:
        if not _CJK_OR_KANA_RE.search(tokens[0]):
            return True, "single very short token"

    # No letters at all — covers Latin, Cyrillic, and common CJK ranges
    # (Chinese, hiragana/katakana, hangul) so non-Latin names aren't flagged.
    if not _NAME_LETTER_RE.search(name):
        return True, "no alphabetic characters"

    return False, ""


def _score(p: dict) -> int:
    """
    Compute a 0–10 completeness score based on observable profile signals.

    Photo is the dominant signal: its absence (genuine, not "lazy-loading not
    finished") is still the single strongest risk indicator. But we no longer
    penalise profiles whose photo simply wasn't in the viewport at export
    time (see photo_state == PHOTO_NOT_LOADED), because that's a data-quality
    issue of the export, not a property of the profile itself.

    Similarly, zero mutual connections used to subtract a point. It no longer
    does: mutuals are a function of the exporter's network, not the profile's
    legitimacy. Missing evidence is not evidence against.
    """
    state = p.get("photo_state", PHOTO_LOADED if p.get("has_photo") else PHOTO_ABSENT)

    # Genuine absence: the profile really has no photo set. Still forces red.
    if state == PHOTO_ABSENT:
        base = 0
        if not p["slug_is_generic"]: base += 1
        if p["has_headline"]:        base += 1
        if p["mutual_level"] > 0:    base += 1
        return min(base, 3)

    # Photo loaded: full confidence in the signal.
    if state == PHOTO_LOADED:
        s = 2
    else:
        # Photo not loaded (ghost-person): unknown state. Give a single point
        # so the profile isn't punished for an export-side issue, but don't
        # grant the full photo bonus since we can't actually see it.
        s = 1

    if not p["slug_is_generic"]:  s += 2
    if p["has_headline"]:         s += 1
    if p["has_employer_ref"]:     s += 1

    # Mutual connections reinforce the signal when present. Their absence is
    # NOT a negative signal — it tells us about the exporter's network, not
    # about the profile being analysed.
    if p["mutual_level"] == 1:    s += 2
    elif p["mutual_level"] >= 2:  s += 3

    if p["suspicious_name"]:      s -= 2

    return max(0, min(s, MAX_SCORE))


def _risk(p: dict) -> str:
    """Map (photo_state, score) → 'red' | 'yellow' | 'green'."""
    # Only a genuinely absent photo forces red.
    state = p.get("photo_state", PHOTO_LOADED if p.get("has_photo") else PHOTO_ABSENT)
    if state == PHOTO_ABSENT:
        return "red"
    # Defensive: fall back to 0 if score wasn't computed yet (library users
    # can call _risk() on a partially-built profile).
    score = p.get("score", 0)
    if score >= RISK_GREEN_MIN:  return "green"
    if score >= RISK_YELLOW_MIN: return "yellow"
    return "red"
