"""
HTML-parsing tests.

These tests cover extract_profiles() and _classify_photo() against fixture
HTML that mirrors the real LinkedIn DOM structure. They also cover the
selector-cascade behaviour: if LinkedIn renames a CSS class, the parser
should fall back to a secondary selector before silently returning empty.
"""
import pytest

from headcheck import (
    extract_profiles, _classify_photo,
    PHOTO_LOADED, PHOTO_NOT_LOADED, PHOTO_ABSENT,
)
from tests.conftest import (
    SYNTHETIC_HTML, FALLBACK_HTML, REAL_SNAPSHOT_HTML,
)


class _FakeImg:
    """Minimal stand-in for a BeautifulSoup Tag, enough for _classify_photo."""
    def __init__(self, src="", classes=None):
        self._attrs = {"src": src, "class": classes or []}

    def get(self, key, default=""):
        return self._attrs.get(key, default)


# ─────────────────────────────────────────────────────────────────────────────
# _classify_photo
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyPhoto:
    def test_real_cdn_url_is_loaded(self):
        tag = _FakeImg(src="https://media.licdn.com/dms/image/v2/ABC")
        state, url = _classify_photo(tag)
        assert state == PHOTO_LOADED
        assert url.startswith("https://media.licdn.com/")

    def test_ghost_person_class_wins_even_with_real_src(self):
        """
        If LinkedIn ever marks a hydrated image with ghost-person (they do,
        briefly, during SPA transitions), trust the class over the src.
        """
        tag = _FakeImg(
            src="https://media.licdn.com/xyz.jpg",
            classes=["evi-image", "lazy-image", "ghost-person"],
        )
        state, url = _classify_photo(tag)
        assert state == PHOTO_NOT_LOADED
        assert url == ""

    def test_lazy_load_gif_placeholder_is_not_loaded(self):
        tag = _FakeImg(src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAA")
        state, _ = _classify_photo(tag)
        assert state == PHOTO_NOT_LOADED

    def test_no_img_tag_is_absent(self):
        state, url = _classify_photo(None)
        assert state == PHOTO_ABSENT
        assert url == ""

    def test_empty_src_is_absent(self):
        tag = _FakeImg(src="")
        state, _ = _classify_photo(tag)
        assert state == PHOTO_ABSENT

    def test_non_http_src_treated_as_absent(self):
        """Protect against unexpected scheme injections."""
        tag = _FakeImg(src="javascript:alert(1)")
        state, _ = _classify_photo(tag)
        assert state == PHOTO_ABSENT


# ─────────────────────────────────────────────────────────────────────────────
# extract_profiles — against the synthetic fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def synthetic_profiles():
    profiles, diag = extract_profiles(str(SYNTHETIC_HTML), lang="en")
    return profiles, diag


def by_slug(profiles, slug):
    """Look up a profile by its slug. Tests read cleaner with this."""
    for p in profiles:
        if p["slug"] == slug:
            return p
    raise AssertionError(f"No profile with slug {slug!r} found; "
                         f"got: {[p['slug'] for p in profiles]}")


class TestExtractProfiles:
    def test_extracts_expected_number_of_unique_profiles(self, synthetic_profiles):
        profiles, _ = synthetic_profiles
        # 8 anchors in the fixture; profile-6 is a duplicate of profile-1 → 7 unique.
        # profile-3 has a valid slug and should be included despite no photo.
        assert len(profiles) == 7

    def test_duplicate_profile_is_deduplicated(self, synthetic_profiles):
        profiles, diag = synthetic_profiles
        assert diag["cards_skipped_duplicate"] == 1
        slugs = [p["slug"] for p in profiles]
        assert slugs.count("alice-johnson") == 1

    def test_loaded_photo_profile(self, synthetic_profiles):
        profiles, _ = synthetic_profiles
        alice = by_slug(profiles, "alice-johnson")
        assert alice["photo_state"] == PHOTO_LOADED
        assert alice["avatar_url"].startswith("https://media.licdn.com/")
        assert alice["risk"] == "green"

    def test_ghost_person_profile_is_not_red(self, synthetic_profiles):
        """The headline bug-fix: Bob has ghost-person but should NOT be red."""
        profiles, _ = synthetic_profiles
        bob = by_slug(profiles, "bob-smith")
        assert bob["photo_state"] == PHOTO_NOT_LOADED
        assert bob["risk"] != "red"

    def test_genuinely_photoless_profile_is_red(self, synthetic_profiles):
        profiles, _ = synthetic_profiles
        ghost = by_slug(profiles, "ACoAAABCDEF1234567")
        assert ghost["photo_state"] == PHOTO_ABSENT
        assert ghost["risk"] == "red"
        assert ghost["slug_is_generic"] is True

    def test_spanish_mutual_caption_not_detected_when_lang_is_english(self):
        """
        The extractor only applies the per-language mutual regex plus an
        English fallback. A Spanish '5 conexiones en común' caption is NOT
        detected when the caller passes lang='en'. This is intentional —
        language fallback is limited to English, not full multilingual.
        """
        profiles, _ = extract_profiles(str(SYNTHETIC_HTML), lang="en")
        maria = by_slug(profiles, "maria-garcia")
        assert maria["mutual_level"] == 0

    def test_spanish_mutual_caption_is_parsed_when_lang_is_spanish(self):
        """With lang='es' the Spanish regex activates and '5 conexiones
        en común' is correctly read as mutual_level=2."""
        profiles, _ = extract_profiles(str(SYNTHETIC_HTML), lang="es")
        maria = by_slug(profiles, "maria-garcia")
        assert maria["mutual_level"] == 2
        assert maria["risk"] == "green"

    def test_cjk_name_not_flagged_suspicious(self, synthetic_profiles):
        profiles, _ = synthetic_profiles
        liming = by_slug(profiles, "li-ming")
        assert liming["suspicious_name"] is False
        assert liming["risk"] == "green"

    def test_name_with_digits_flagged_suspicious(self, synthetic_profiles):
        profiles, _ = synthetic_profiles
        user123 = by_slug(profiles, "user123")
        assert user123["suspicious_name"] is True
        assert "digits" in user123["suspicious_reason"]

    def test_xss_payload_is_captured_as_plain_text(self, synthetic_profiles):
        """
        The extractor preserves whatever LinkedIn showed. The escaping
        happens at render time (HTML/CSV), not at extraction time.
        """
        profiles, _ = synthetic_profiles
        evil = by_slug(profiles, "evil-user")
        assert "<script>" in evil["name"]  # stored as literal text


# ─────────────────────────────────────────────────────────────────────────────
# extract_profiles — diagnostics dict
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractionDiagnostics:
    def test_diagnostics_include_expected_counters(self, synthetic_profiles):
        _, diag = synthetic_profiles
        for key in ("anchors_found", "profiles_extracted",
                    "photo_loaded", "photo_not_loaded", "photo_absent",
                    "cards_skipped_duplicate"):
            assert key in diag

    def test_photo_state_counters_sum_to_profile_count(self, synthetic_profiles):
        profiles, diag = synthetic_profiles
        total_photo = (diag["photo_loaded"] + diag["photo_not_loaded"]
                       + diag["photo_absent"])
        assert total_photo == len(profiles)

    def test_empty_html_returns_empty_profiles_and_diag(self, tmp_path):
        """
        Hard-negative: if the HTML has no relevant structure, we must return
        cleanly with zero profiles and the diagnostics tell the story.
        """
        broken = tmp_path / "broken.html"
        broken.write_text("<html><body>nothing here</body></html>")
        profiles, diag = extract_profiles(str(broken))
        assert profiles == []
        assert diag["anchors_found"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Selector-cascade resilience
# ─────────────────────────────────────────────────────────────────────────────

class TestSelectorFallback:
    """
    The point of these tests: when LinkedIn renames a CSS class we depend on,
    the secondary selectors in _find_name/_find_headline/_find_mutual_caption
    should absorb the change without the extractor returning empty.
    """
    def test_fallback_selectors_find_name_and_mutuals(self):
        profiles, diag = extract_profiles(str(FALLBACK_HTML))
        assert len(profiles) == 1
        p = profiles[0]
        # Name came from `artdeco-entity-lockup__title` (fallback #2).
        assert p["name"] == "Alice Fallback"
        # Mutual caption came from `entity-result__simple-insight-text`.
        assert p["mutual_level"] >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Integration: a real-world LinkedIn snapshot
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not REAL_SNAPSHOT_HTML.exists(),
    reason="Real LinkedIn snapshot not present — skipping integration test",
)
class TestRealSnapshotIntegration:
    """
    Runs the extractor against a real 96-profile LinkedIn export. Asserts
    coarse properties that shouldn't drift with small edits; the exact
    numbers would be too fragile to encode.
    """
    def test_real_snapshot_extracts_reasonable_number(self):
        profiles, diag = extract_profiles(str(REAL_SNAPSHOT_HTML))
        # At the time of writing the fixture had 96 profiles. Allow some drift
        # in case we tweak deduplication or parsing later, but it should stay
        # close.
        assert 80 <= len(profiles) <= 110

    def test_real_snapshot_produces_no_red_from_ghost_person_alone(self):
        """
        This is THE regression test for the v1.3.0 scoring fix. In v1.2.0 this
        snapshot produced 10 red profiles, all of them false positives due to
        ghost-person placeholders. In v1.3.0 there should be zero red from
        that cause — any remaining reds must have photo_state == PHOTO_ABSENT.
        """
        profiles, _ = extract_profiles(str(REAL_SNAPSHOT_HTML))
        reds = [p for p in profiles if p["risk"] == "red"]
        for r in reds:
            assert r["photo_state"] == PHOTO_ABSENT, (
                f"Profile {r['name']!r} is red but photo_state is "
                f"{r['photo_state']!r} — only PHOTO_ABSENT should force red."
            )
