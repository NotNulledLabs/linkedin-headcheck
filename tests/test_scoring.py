"""
Scoring tests.

These lock in the current semantics of _score() and _risk() as of v1.3.0:
  - PHOTO_ABSENT is the ONLY photo state that forces red.
  - PHOTO_NOT_LOADED (ghost-person placeholder) gets +1, not +2, and does
    NOT force red — it's an export-quality issue, not a profile property.
  - mutual_level == 0 does NOT subtract from the score. Missing mutual
    connections tell us about the exporter's network, not the profile.

If these rules ever change intentionally, update the matrix below.
"""
import pytest

from headcheck import (
    _score, _risk,
    PHOTO_LOADED, PHOTO_NOT_LOADED, PHOTO_ABSENT,
    MAX_SCORE,
)


def profile(**overrides):
    """
    Build a profile dict with 'perfect' defaults. Each test overrides only
    the signals it cares about, so the test reads as a statement about
    that signal's effect.
    """
    base = dict(
        photo_state=PHOTO_LOADED,
        has_photo=True,
        slug_is_generic=False,
        has_headline=True,
        has_employer_ref=True,
        mutual_level=2,
        suspicious_name=False,
    )
    base.update(overrides)
    return base


# ─────────────────────────────────────────────────────────────────────────────
# Photo state matrix
# ─────────────────────────────────────────────────────────────────────────────

class TestPhotoState:
    def test_loaded_photo_gives_full_credit(self):
        p = profile(photo_state=PHOTO_LOADED)
        assert _score(p) == 9   # 2 + 2 + 1 + 1 + 3
        assert _risk({**p, "score": _score(p)}) == "green"

    def test_not_loaded_photo_gives_partial_credit_not_red(self):
        """The ghost-person fix: a lazy-load placeholder should NOT force red."""
        p = profile(photo_state=PHOTO_NOT_LOADED)
        assert _score(p) == 8   # 1 + 2 + 1 + 1 + 3
        assert _risk({**p, "score": _score(p)}) == "green"

    def test_absent_photo_forces_red_regardless_of_other_signals(self):
        """Genuine absence is still the strongest risk indicator."""
        p = profile(photo_state=PHOTO_ABSENT, has_photo=False)
        assert _risk({**p, "score": _score(p)}) == "red"
        assert _score(p) <= 3

    def test_absent_photo_score_capped_at_3(self):
        p = profile(photo_state=PHOTO_ABSENT, has_photo=False,
                    mutual_level=2, has_headline=True, slug_is_generic=False)
        assert _score(p) == 3  # cap

    def test_absent_photo_with_no_other_signals_scores_zero(self):
        p = profile(photo_state=PHOTO_ABSENT, has_photo=False,
                    mutual_level=0, has_headline=False, slug_is_generic=True)
        assert _score(p) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Mutual connections
# ─────────────────────────────────────────────────────────────────────────────

class TestMutualLevel:
    def test_zero_mutuals_no_longer_penalised(self):
        """
        Regression test for the exporter-bias fix. Zero mutuals used to cost
        -1 point; it no longer does, because the signal depends on who
        exported the page, not on the profile itself.
        """
        p = profile(mutual_level=0)
        # Expected: 2 (photo) + 2 (slug) + 1 (hl) + 1 (empl_ref) + 0 = 6
        assert _score(p) == 6
        assert _risk({**p, "score": _score(p)}) == "yellow"

    def test_one_mutual_adds_two(self):
        p = profile(mutual_level=1)
        assert _score(p) == 8   # 2 + 2 + 1 + 1 + 2

    def test_multiple_mutuals_add_three(self):
        p = profile(mutual_level=2)
        assert _score(p) == 9   # 2 + 2 + 1 + 1 + 3


# ─────────────────────────────────────────────────────────────────────────────
# Component signals
# ─────────────────────────────────────────────────────────────────────────────

class TestScoringSignals:
    def test_suspicious_name_subtracts_two(self):
        clean = profile()
        dirty = profile(suspicious_name=True)
        assert _score(clean) - _score(dirty) == 2

    def test_generic_slug_loses_two_points(self):
        """ACoAAA… auto-generated IDs are a weak-signal marker."""
        normal = profile(slug_is_generic=False)
        generic = profile(slug_is_generic=True)
        assert _score(normal) - _score(generic) == 2

    def test_missing_headline_loses_one(self):
        with_hl = profile(has_headline=True)
        no_hl = profile(has_headline=False)
        assert _score(with_hl) - _score(no_hl) == 1

    def test_missing_employer_ref_loses_one(self):
        with_ref = profile(has_employer_ref=True)
        no_ref = profile(has_employer_ref=False)
        assert _score(with_ref) - _score(no_ref) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Score bounds
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreBounds:
    def test_score_never_exceeds_max(self):
        # Even with every possible positive signal the cap is MAX_SCORE.
        p = profile()
        assert _score(p) <= MAX_SCORE

    def test_score_never_negative(self):
        # Worst plausible legit case: suspicious name eats into the base.
        p = profile(
            photo_state=PHOTO_NOT_LOADED,
            slug_is_generic=True,
            has_headline=False,
            has_employer_ref=False,
            mutual_level=0,
            suspicious_name=True,
        )
        assert _score(p) >= 0


# ─────────────────────────────────────────────────────────────────────────────
# Risk thresholds
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("score,expected_risk", [
    (0, "red"),
    (3, "red"),
    (4, "yellow"),
    (6, "yellow"),
    (7, "green"),
    (10, "green"),
])
def test_risk_thresholds(score, expected_risk):
    """The score→risk boundaries are part of the public contract."""
    p = profile()
    p["score"] = score
    assert _risk(p) == expected_risk
