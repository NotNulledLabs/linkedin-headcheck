"""
Snapshot persistence and diffing.

Every run writes a JSON file alongside the human reports — a durable,
machine-readable record of what was observed. Two snapshots can be compared
with `diff_snapshots()` to produce a structured changelog suitable for
showing to HR ("who's new since last audit?") or alerting via cron/CI.

Library-friendly: bad input raises `ValueError` instead of calling sys.exit,
so callers can catch and decide what to do.
"""
import csv
import json
from datetime import datetime

from ..constants import VERSION


def export_snapshot_json(profiles: list[dict], company: str,
                          has_payroll: bool, stats: dict, out: str) -> int:
    """
    Write a structured JSON snapshot of the audit for later diffing.

    Unlike the HTML / PDF / XLSX reports — which are meant for humans —
    this file is the durable machine-readable record of what was observed
    on this date. Two snapshots can be compared with `diff_snapshots()` to
    answer questions like "who is new since last audit?".

    Returns the number of profile entries serialised.
    """
    payload = {
        "headcheck_version": VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "company": company,
        "has_payroll": has_payroll,
        "stats": stats,
        "profiles": profiles,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    return len(profiles)


def _load_snapshot(path: str) -> dict:
    """Load and lightly validate a HeadCheck JSON snapshot."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "profiles" not in data:
        raise ValueError(
            f"{path!r} does not look like a HeadCheck snapshot "
            "(missing 'profiles' key)."
        )
    return data


def diff_snapshots(old_path: str, new_path: str) -> dict:
    """
    Compare two HeadCheck snapshots and classify profiles by what changed.

    Identity is established by `profile_url`: if LinkedIn re-uses the same
    URL slug, it's the same person. A profile whose slug changed will show
    up as both "appeared" and "disappeared" — an inherent limitation of
    using public data without LinkedIn's internal IDs.

    Returns a dict with these keys, each mapping to a list of profiles:
        appeared:       profiles in new but not in old
        disappeared:    profiles in old but not in new
        risk_up:        risk got worse (green→yellow, yellow→red, green→red)
        risk_down:      risk got better
        score_changed:  score changed but risk stayed the same (minor drift)
        unchanged:      same in every relevant way
    """
    old = _load_snapshot(old_path)
    new = _load_snapshot(new_path)

    old_by_url = {p["profile_url"]: p for p in old["profiles"] if p.get("profile_url")}
    new_by_url = {p["profile_url"]: p for p in new["profiles"] if p.get("profile_url")}

    old_urls = set(old_by_url)
    new_urls = set(new_by_url)

    result = {
        "appeared":      [new_by_url[u] for u in sorted(new_urls - old_urls)],
        "disappeared":   [old_by_url[u] for u in sorted(old_urls - new_urls)],
        "risk_up":       [],
        "risk_down":     [],
        "score_changed": [],
        "unchanged":     [],
        "meta": {
            "old_path": old_path,
            "new_path": new_path,
            "old_generated_at": old.get("generated_at"),
            "new_generated_at": new.get("generated_at"),
            "old_company": old.get("company"),
            "new_company": new.get("company"),
        },
    }

    # Order risk states from safest to most concerning so we can compare.
    risk_rank = {"green": 0, "yellow": 1, "red": 2}

    for url in sorted(old_urls & new_urls):
        old_p, new_p = old_by_url[url], new_by_url[url]
        # Default rank to "yellow" for unknown values — neutral, won't push
        # a missing-risk profile into either improvement or worsening bucket.
        old_rank = risk_rank.get(old_p.get("risk"), 1)
        new_rank = risk_rank.get(new_p.get("risk"), 1)
        entry = {
            "name":        new_p.get("name") or old_p.get("name"),
            "profile_url": url,
            "old_risk":    old_p.get("risk"),
            "new_risk":    new_p.get("risk"),
            "old_score":   old_p.get("score"),
            "new_score":   new_p.get("score"),
        }
        if new_rank > old_rank:
            result["risk_up"].append(entry)
        elif new_rank < old_rank:
            result["risk_down"].append(entry)
        elif old_p.get("score") != new_p.get("score"):
            result["score_changed"].append(entry)
        else:
            result["unchanged"].append(entry)

    return result


def export_diff_csv(diff: dict, out: str) -> int:
    """
    Flatten the diff result into a single CSV for HR spreadsheets.
    Returns the number of rows written (excluding 'unchanged' profiles,
    which would be noise in a diff report).
    """
    rows = []
    for p in diff["appeared"]:
        rows.append({
            "change": "appeared",
            "name": p.get("name", ""),
            "profile_url": p.get("profile_url", ""),
            "old_risk": "",
            "new_risk": p.get("risk", ""),
            "old_score": "",
            "new_score": p.get("score", ""),
        })
    for p in diff["disappeared"]:
        rows.append({
            "change": "disappeared",
            "name": p.get("name", ""),
            "profile_url": p.get("profile_url", ""),
            "old_risk": p.get("risk", ""),
            "new_risk": "",
            "old_score": p.get("score", ""),
            "new_score": "",
        })
    for category in ("risk_up", "risk_down", "score_changed"):
        for p in diff[category]:
            rows.append({
                "change": category,
                "name": p["name"],
                "profile_url": p["profile_url"],
                "old_risk": p["old_risk"],
                "new_risk": p["new_risk"],
                "old_score": p["old_score"],
                "new_score": p["new_score"],
            })

    fieldnames = ["change", "name", "profile_url",
                  "old_risk", "new_risk", "old_score", "new_score"]
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)
