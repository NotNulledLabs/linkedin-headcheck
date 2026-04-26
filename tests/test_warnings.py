"""
Tests for _evaluate_export_quality().

These verify that the user-facing warnings fire when they should and stay
silent when they shouldn't. They are deliberately black-box — they inspect
the presence of specific keywords in the warning text, not its exact
wording, so editing the messages doesn't break the tests.
"""
from headcheck import (
    _evaluate_export_quality,
    PHOTO_LOADED, PHOTO_NOT_LOADED, PHOTO_ABSENT,
)


def _mk_profile(photo_state=PHOTO_LOADED, mutual_level=2):
    return {"photo_state": photo_state, "mutual_level": mutual_level}


class TestExportQualityWarnings:
    def test_no_warnings_on_healthy_export(self):
        profiles = [_mk_profile() for _ in range(50)]
        diag = {"anchors_found": 50}
        assert _evaluate_export_quality(profiles, diag) == []

    def test_many_unloaded_photos_warns(self):
        # 20% not-loaded is above the 10% threshold.
        profiles = (
            [_mk_profile(photo_state=PHOTO_NOT_LOADED) for _ in range(20)]
            + [_mk_profile() for _ in range(80)]
        )
        warnings = _evaluate_export_quality(profiles, {"anchors_found": 100})
        assert len(warnings) == 1
        assert "not loaded" in warnings[0].lower()
        assert "re-export" in warnings[0].lower() or "scroll" in warnings[0].lower()

    def test_low_mutual_coverage_warns(self):
        # 10% mutual coverage is below the 20% threshold.
        profiles = (
            [_mk_profile(mutual_level=1) for _ in range(10)]
            + [_mk_profile(mutual_level=0) for _ in range(90)]
        )
        warnings = _evaluate_export_quality(profiles, {"anchors_found": 100})
        assert len(warnings) == 1
        assert "mutual" in warnings[0].lower()

    def test_both_warnings_stack(self):
        profiles = (
            [_mk_profile(photo_state=PHOTO_NOT_LOADED, mutual_level=0) for _ in range(30)]
            + [_mk_profile(mutual_level=0) for _ in range(70)]
        )
        warnings = _evaluate_export_quality(profiles, {"anchors_found": 100})
        assert len(warnings) == 2

    def test_empty_profiles_returns_no_warnings(self):
        """Zero-profile case is handled by the 'No profiles extracted' message
        elsewhere; this function should just return cleanly."""
        assert _evaluate_export_quality([], {"anchors_found": 0}) == []

    def test_threshold_edge_ten_percent_fires(self):
        """10% is the inclusive threshold for the not-loaded warning."""
        profiles = (
            [_mk_profile(photo_state=PHOTO_NOT_LOADED) for _ in range(10)]
            + [_mk_profile() for _ in range(90)]
        )
        warnings = _evaluate_export_quality(profiles, {"anchors_found": 100})
        assert any("not loaded" in w.lower() for w in warnings)
