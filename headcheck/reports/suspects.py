"""
Suspects CSV export — red + yellow profiles, sorted worst-first.

This is the file HR brings to a meeting. It deliberately filters out
the green profiles to keep the focus on what needs review.
"""
import csv


def export_suspects_csv(profiles: list[dict], has_payroll: bool, out: str) -> int:
    """
    Write the red+yellow subset to `out` as CSV. Returns the number of
    suspect profiles written.
    """
    suspects = [p for p in profiles if p["risk"] in ("red", "yellow")]
    suspects.sort(key=lambda p: p["score"])  # lowest score first

    fieldnames = ["risk", "score", "name", "headline", "profile_url",
                  "has_photo", "mutual_level", "slug_is_generic",
                  "suspicious_name", "suspicious_reason"]
    if has_payroll:
        fieldnames += ["payroll_status", "payroll_match"]

    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(suspects)

    return len(suspects)
