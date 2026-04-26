"""
LinkedIn People-page DOM parsing.

`extract_profiles()` is the entry point. Given a saved HTML snapshot of a
company's People tab, it returns the list of unique profiles plus a
diagnostics dict that callers can use to surface export-quality warnings.

The module uses cascading selectors for each field (name, headline, mutual
caption) so a small CSS-class rename in LinkedIn's UI doesn't immediately
zero out our extraction. When LinkedIn does a larger refresh, the diagnostics
dict (anchor count, skip reasons) is the lever for diagnosing what changed.
"""
import re

from bs4 import BeautifulSoup

from .constants import (
    LINKEDIN_GHOST_B64,
    PHOTO_LOADED, PHOTO_NOT_LOADED, PHOTO_ABSENT,
)
from .scoring import count_mutual, is_suspicious_name, _score, _risk


# ─────────────────────────────────────────────────────────────────────────────
# URL & photo helpers
# ─────────────────────────────────────────────────────────────────────────────

def _clean_url(raw: str) -> str:
    url = raw.split("?")[0]
    # Strip any HTML entity artefacts that LinkedIn injects
    url = re.sub(r'["\'>]', "", url)
    url = url.replace("&amp;", "&").strip()
    return url


def _classify_photo(img_tag) -> tuple[str, str]:
    """
    Inspect an <img> tag and return (photo_state, avatar_url).

    `photo_state` is one of PHOTO_LOADED / PHOTO_NOT_LOADED / PHOTO_ABSENT.
    `avatar_url`  is the cleaned CDN URL when loaded, otherwise "".
    """
    if img_tag is None:
        return PHOTO_ABSENT, ""

    # The strongest signal LinkedIn gives us: the CSS class `ghost-person` is
    # applied to the <img> specifically when the picture hasn't hydrated yet.
    # This is a viewport/lazy-loading state, NOT "this person has no photo".
    classes = img_tag.get("class") or []
    if isinstance(classes, str):
        classes = classes.split()
    if any("ghost-person" in c for c in classes):
        return PHOTO_NOT_LOADED, ""

    raw = img_tag.get("src", "") or ""
    if not raw:
        return PHOTO_ABSENT, ""

    # Secondary heuristic: the 1x1 GIF data URL is the lazy placeholder source.
    # If we see it WITHOUT a ghost-person class, we still treat it as not-loaded
    # because that's what the byte-pattern means.
    if raw.startswith(LINKEDIN_GHOST_B64):
        return PHOTO_NOT_LOADED, ""

    # Strip HTML entity artefacts LinkedIn injects in CDN URLs.
    url = re.sub(r'["\'>]+', "", raw)
    url = url.replace("&amp;", "&").strip()
    if not url.startswith(("http://", "https://")):
        return PHOTO_ABSENT, ""

    return PHOTO_LOADED, url


# ─────────────────────────────────────────────────────────────────────────────
# Field extractors with selector cascades
# ─────────────────────────────────────────────────────────────────────────────
#
# Each `_find_*` function tries a sequence of selector strategies, ordered
# from most specific to most forgiving. If LinkedIn renames a CSS class in
# a UI refresh, a weaker strategy should still find the text so we don't
# silently return empty profiles.

def _find_name(card) -> str:
    for selector_fn in (
        # 1. The current (Jan 2026) class used by LinkedIn on People cards.
        lambda c: c.find("div", class_=re.compile(r"t-black")),
        # 2. Common ancestor class for profile cards — the title inside it.
        lambda c: c.find(class_=re.compile(r"artdeco-entity-lockup__title")),
        # 3. Any element that looks like a name anchor.
        lambda c: c.find("a", class_=re.compile(r"app-aware-link")),
    ):
        el = selector_fn(card)
        if el:
            txt = el.get_text(strip=True)
            if txt:
                return txt
    return ""


def _find_headline(card) -> str:
    for selector_fn in (
        lambda c: c.find("div", class_=re.compile(r"artdeco-entity-lockup__subtitle")),
        lambda c: c.find(class_=re.compile(r"entity-result__primary-subtitle")),
        lambda c: c.find(class_=re.compile(r"subtitle")),
    ):
        el = selector_fn(card)
        if el:
            txt = el.get_text(strip=True)
            if txt:
                return txt
    return ""


def _find_mutual_caption(card) -> str:
    for selector_fn in (
        lambda c: c.find("span", class_=re.compile(r"lt-line-clamp--multi-line t-12")),
        lambda c: c.find("span", class_=re.compile(r"entity-result__simple-insight-text")),
        lambda c: c.find(class_=re.compile(r"insight-text")),
    ):
        el = selector_fn(card)
        if el:
            txt = el.get_text(strip=True)
            if txt:
                return txt
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

# Words that, when found in a profile headline, indicate the person is
# describing where they work. Multilingual: covers English, Spanish, French,
# German, Italian, Portuguese, Polish, Dutch. We match conservatively (whole
# words only) to avoid false positives in unrelated text.
_EMPLOYER_REF_RE = re.compile(
    r"\bat\b|"          # English: "Engineer at Acme"
    r"\ben\b|"          # Spanish/French: "Ingeniero en Acme"
    r"\bna\b|\bno\b|"   # Portuguese: "Engenheiro na Empresa"
    r"\bpresso\b|"      # Italian: "Ingegnere presso Acme"
    r"\bpri\b|"         # Polish: "Inżynier pri Acme"
    r"\bbei\b|"         # German: "Ingenieur bei Acme"
    r"\bbij\b|"         # Dutch: "Ingenieur bij Acme"
    r"\bchez\b",        # French alt: "Ingénieur chez Acme"
    re.I,
)


def extract_profiles(html_path: str, lang: str = "en",
                     debug: bool = False) -> tuple[list[dict], dict]:
    """
    Parse a LinkedIn People-page HTML snapshot.

    Returns (profiles, diagnostics) where diagnostics is a dict with counters
    the caller can use to warn the user about likely export quality issues
    (e.g. many un-loaded photos, suspiciously empty extractions).
    """
    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f, "html.parser")

    anchors = soup.find_all(
        "a", id=re.compile(r"org-people-profile-card__profile-image-\d+")
    )

    people: list[dict] = []
    seen: set[str] = set()
    diag = {
        "anchors_found": len(anchors),
        "cards_skipped_no_parent": 0,
        "cards_skipped_no_name": 0,
        "cards_skipped_duplicate": 0,
        "photo_loaded": 0,
        "photo_not_loaded": 0,
        "photo_absent": 0,
    }

    for anchor in anchors:
        card = anchor.find_parent("div", class_="org-people-profile-card__profile-info")
        if not card:
            # Try a looser fallback for the card container before giving up.
            card = anchor.find_parent("div", class_=re.compile(r"profile-card|profile-info"))
            if not card:
                diag["cards_skipped_no_parent"] += 1
                continue

        name = _find_name(card)
        if not name:
            diag["cards_skipped_no_name"] += 1
            continue

        profile_url = _clean_url(anchor.get("href", ""))
        if not profile_url:
            continue
        if profile_url in seen:
            diag["cards_skipped_duplicate"] += 1
            continue
        seen.add(profile_url)

        photo_state, avatar_url = _classify_photo(anchor.find("img"))
        diag[f"photo_{photo_state}"] += 1

        headline = _find_headline(card)
        extra_note = _find_mutual_caption(card)

        slug = profile_url.replace("https://www.linkedin.com/in/", "").strip("/")
        slug_is_generic = bool(re.match(r"^ACo[A-Za-z0-9_\-]{10,}$", slug))
        mutual_level   = count_mutual(extra_note, lang)
        has_headline   = bool(headline)
        has_employer_ref = bool(headline and _EMPLOYER_REF_RE.search(headline))
        susp_name, susp_reason = is_suspicious_name(name)

        profile = dict(
            name=name,
            profile_url=profile_url,
            avatar_url=avatar_url,
            photo_state=photo_state,                  # tri-state field
            has_photo=(photo_state == PHOTO_LOADED),  # kept for backward-compat
            headline=headline,
            extra_note=extra_note,
            slug=slug,
            slug_is_generic=slug_is_generic,
            mutual_level=mutual_level,
            has_headline=has_headline,
            has_employer_ref=has_employer_ref,
            suspicious_name=susp_name,
            suspicious_reason=susp_reason,
        )
        profile["score"] = _score(profile)
        profile["risk"]  = _risk(profile)
        people.append(profile)

    diag["profiles_extracted"] = len(people)
    # No printing from here — the diagnostics dict is returned so the caller
    # (CLI, TUI, tests…) decides whether and how to surface it. The `debug`
    # parameter is kept for backward compatibility.
    return people, diag
