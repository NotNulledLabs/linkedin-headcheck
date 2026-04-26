"""
Tests for snapshot JSON export and snapshot diffing.

We exercise the full loop: write a synthetic snapshot, tweak it, write a
second one, diff them, assert the expected classifications. Also cover the
edge cases that would silently break things in production — empty diff,
missing keys, malformed JSON, identity by profile_url.
"""
import json
import pytest

from headcheck import (
    export_snapshot_json, export_diff_csv,
    diff_snapshots, _load_snapshot,
)


def _mkprofile(slug, **kw):
    """Minimal profile dict keyed by slug. URL is derived from slug."""
    base = dict(
        name=slug.replace("-", " ").title(),
        profile_url=f"https://www.linkedin.com/in/{slug}",
        risk="green",
        score=8,
        headline="Engineer at Acme",
        photo_state="loaded",
        mutual_level=2,
        slug_is_generic=False,
        suspicious_name=False,
        has_photo=True,
    )
    base.update(kw)
    return base


@pytest.fixture
def old_snapshot_path(tmp_path):
    """Snapshot with 3 profiles: Alice (green), Bob (yellow), Carol (red)."""
    profiles = [
        _mkprofile("alice-johnson", risk="green", score=8),
        _mkprofile("bob-smith", risk="yellow", score=5, mutual_level=0),
        _mkprofile("carol-white", risk="red", score=2,
                   photo_state="absent", has_photo=False),
    ]
    path = tmp_path / "old.json"
    export_snapshot_json(profiles, "Acme", True,
                         {"total": 3, "red": 1, "yellow": 1, "green": 1,
                          "suspects_exported": 2},
                         str(path))
    return path


class TestSnapshotExport:
    def test_snapshot_is_valid_json(self, old_snapshot_path):
        data = json.loads(old_snapshot_path.read_text())
        assert isinstance(data, dict)

    def test_snapshot_has_required_keys(self, old_snapshot_path):
        data = json.loads(old_snapshot_path.read_text())
        for k in ("headcheck_version", "generated_at", "company",
                  "has_payroll", "stats", "profiles"):
            assert k in data, f"Missing key {k!r}"

    def test_snapshot_preserves_profile_count(self, old_snapshot_path):
        data = json.loads(old_snapshot_path.read_text())
        assert len(data["profiles"]) == 3

    def test_loading_non_snapshot_fails(self, tmp_path):
        bad = tmp_path / "not_a_snapshot.json"
        bad.write_text(json.dumps({"foo": "bar"}))
        with pytest.raises(ValueError, match="HeadCheck snapshot"):
            _load_snapshot(str(bad))


class TestDiffSnapshots:
    def _write(self, tmp_path, profiles, name="s.json"):
        path = tmp_path / name
        export_snapshot_json(profiles, "Acme", False,
                             {"total": len(profiles), "red": 0, "yellow": 0,
                              "green": 0, "suspects_exported": 0},
                             str(path))
        return path

    def test_identical_snapshots_produce_no_changes(self, tmp_path):
        """Regression: comparing a snapshot with itself must find no changes."""
        profiles = [_mkprofile("alice"), _mkprofile("bob")]
        p = self._write(tmp_path, profiles)
        diff = diff_snapshots(str(p), str(p))
        assert diff["appeared"]      == []
        assert diff["disappeared"]   == []
        assert diff["risk_up"]       == []
        assert diff["risk_down"]     == []
        assert diff["score_changed"] == []
        assert len(diff["unchanged"]) == 2

    def test_appeared_profiles_detected(self, tmp_path):
        old = self._write(tmp_path, [_mkprofile("alice")], "old.json")
        new = self._write(tmp_path,
                          [_mkprofile("alice"), _mkprofile("bob")],
                          "new.json")
        diff = diff_snapshots(str(old), str(new))
        assert len(diff["appeared"]) == 1
        assert diff["appeared"][0]["profile_url"].endswith("/bob")

    def test_disappeared_profiles_detected(self, tmp_path):
        old = self._write(tmp_path,
                          [_mkprofile("alice"), _mkprofile("bob")],
                          "old.json")
        new = self._write(tmp_path, [_mkprofile("alice")], "new.json")
        diff = diff_snapshots(str(old), str(new))
        assert len(diff["disappeared"]) == 1
        assert diff["disappeared"][0]["profile_url"].endswith("/bob")

    def test_risk_up_detected(self, tmp_path):
        """green→red should land in risk_up, not score_changed."""
        old = self._write(tmp_path,
                          [_mkprofile("alice", risk="green", score=9)],
                          "old.json")
        new = self._write(tmp_path,
                          [_mkprofile("alice", risk="red", score=2,
                                      photo_state="absent", has_photo=False)],
                          "new.json")
        diff = diff_snapshots(str(old), str(new))
        assert len(diff["risk_up"]) == 1
        entry = diff["risk_up"][0]
        assert entry["old_risk"] == "green" and entry["new_risk"] == "red"
        assert diff["risk_down"]     == []
        assert diff["score_changed"] == []

    def test_risk_down_detected(self, tmp_path):
        old = self._write(tmp_path,
                          [_mkprofile("alice", risk="red", score=2,
                                      photo_state="absent", has_photo=False)],
                          "old.json")
        new = self._write(tmp_path,
                          [_mkprofile("alice", risk="green", score=9)],
                          "new.json")
        diff = diff_snapshots(str(old), str(new))
        assert len(diff["risk_down"]) == 1

    def test_score_drift_with_same_risk(self, tmp_path):
        """Score changes but risk bucket stays the same."""
        old = self._write(tmp_path,
                          [_mkprofile("alice", risk="green", score=9)],
                          "old.json")
        new = self._write(tmp_path,
                          [_mkprofile("alice", risk="green", score=7)],
                          "new.json")
        diff = diff_snapshots(str(old), str(new))
        assert len(diff["score_changed"]) == 1
        assert diff["risk_up"]   == []
        assert diff["risk_down"] == []

    def test_profile_identity_uses_url_not_name(self, tmp_path):
        """
        If someone changes their display name on LinkedIn but the URL slug
        stays the same, it's still the same profile — not an appeared+
        disappeared pair.
        """
        old = self._write(tmp_path,
                          [_mkprofile("alice", name="Alice Old Name")],
                          "old.json")
        new = self._write(tmp_path,
                          [_mkprofile("alice", name="Alice New Name")],
                          "new.json")
        diff = diff_snapshots(str(old), str(new))
        assert diff["appeared"] == []
        assert diff["disappeared"] == []
        # The name change alone doesn't trigger any bucket — risk and score
        # are unchanged.
        assert len(diff["unchanged"]) == 1


class TestDiffCsvExport:
    def _build_diff(self, tmp_path):
        """Produce a diff with one item in each non-unchanged bucket."""
        old_profiles = [
            _mkprofile("alice", risk="green", score=9),    # will stay
            _mkprofile("bob",   risk="green", score=8),    # will get worse
            _mkprofile("carol", risk="yellow", score=5),   # will disappear
            _mkprofile("dave",  risk="green", score=9),    # score drift
        ]
        new_profiles = [
            _mkprofile("alice", risk="green", score=9),           # unchanged
            _mkprofile("bob",   risk="red",   score=2,
                       photo_state="absent", has_photo=False),   # risk_up
            _mkprofile("dave",  risk="green", score=7),           # score drift
            _mkprofile("new-hire", risk="green", score=8),        # appeared
        ]
        old = tmp_path / "old.json"
        new = tmp_path / "new.json"
        for p, items in ((old, old_profiles), (new, new_profiles)):
            export_snapshot_json(items, "Acme", False,
                                 {"total": len(items), "red": 0, "yellow": 0,
                                  "green": 0, "suspects_exported": 0},
                                 str(p))
        return diff_snapshots(str(old), str(new))

    def test_csv_contains_one_row_per_change(self, tmp_path):
        diff = self._build_diff(tmp_path)
        out = tmp_path / "diff.csv"
        n = export_diff_csv(diff, str(out))
        # 1 appeared + 1 disappeared + 1 risk_up + 1 score_changed = 4.
        assert n == 4

    def test_csv_headers(self, tmp_path):
        diff = self._build_diff(tmp_path)
        out = tmp_path / "diff.csv"
        export_diff_csv(diff, str(out))

        # Read back the first line to check headers.
        with open(out, encoding="utf-8-sig") as f:
            first = f.readline().strip()
        for expected_col in ("change", "name", "profile_url",
                             "old_risk", "new_risk", "old_score", "new_score"):
            assert expected_col in first


class TestDiffMetaBlock:
    def test_meta_preserves_paths_and_timestamps(self, tmp_path):
        old = tmp_path / "old.json"
        new = tmp_path / "new.json"
        for p in (old, new):
            export_snapshot_json([_mkprofile("alice")], "Acme", False,
                                 {"total": 1, "red": 0, "yellow": 0,
                                  "green": 1, "suspects_exported": 0},
                                 str(p))
        diff = diff_snapshots(str(old), str(new))
        meta = diff["meta"]
        assert meta["old_path"] == str(old)
        assert meta["new_path"] == str(new)
        assert meta["old_company"] == "Acme"
        assert meta["new_company"] == "Acme"
