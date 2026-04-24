# Changelog

All notable changes to LinkedIn HeadCheck are documented here.

## [1.6.0] — 2026-04-24

A substantial release covering scoring correctness, resilience, testing,
user experience, and new outputs. Recommended upgrade for all users.

### Added
- **Interactive wizard mode.** Running `python headcheck.py` with no arguments
  launches a guided wizard powered by `questionary` + `rich`: path pickers,
  colour-coded progress, results panel. Falls back to plain `input()` prompts
  if those libraries aren't installed.
- **Excel workbook (`.xlsx`).** Fourth output file tuned for HR workflows:
  colour-coded risk cells, score data bars, hyperlinked profile URLs, frozen
  header, autofilter, empty Notes column for inline annotation.
- **Snapshot JSON.** Fifth output file — a machine-readable record of the
  audit, written next to the human reports. Used by the diff subcommand.
- **Snapshot diff subcommand.** `python headcheck.py diff old.json new.json`
  compares two audits and classifies profiles into five buckets: appeared,
  disappeared, risk worsened, risk improved, score drift. Exit code signals
  whether any change was detected so it can run in cron/CI. Optional
  `--csv` flag exports the diff for HR spreadsheets.
- **`run_headcheck()` public function.** The pipeline is now callable as a
  library, returning a structured dict with profiles, stats, warnings and
  output paths. Optional `progress=callback` for custom UIs.
- **Export-quality warnings.** New `_evaluate_export_quality()` surfaces
  actionable messages when many photos didn't load (≥10 %) or mutual
  coverage is suspiciously low (<20 %).
- **`--debug` flag.** Prints extraction diagnostics (anchor count, skip
  reasons, photo-state breakdown) to help pinpoint parser issues when
  LinkedIn changes its DOM.
- **Regression test suite.** 129 tests covering scoring, parsing, payroll,
  multilingual mutual detection, warnings, interactive mode, Excel output
  and snapshot diffing. Runs in ~3.5 seconds.

### Changed
- **Photo detection is now tri-state**: `loaded` / `not_loaded` / `absent`.
  Only genuinely absent photos force red. Lazy-load placeholders
  (LinkedIn's `ghost-person` class or the 1×1 GIF) are treated as unknown
  and no longer falsely flag legitimate employees as high-risk.
- **Zero mutual connections no longer subtracts from the score.** The
  signal depends on the exporter's network, not the analysed profile. A
  missing signal is not a negative signal.
- **Payroll column detection split into strong/weak keywords.** Prevents
  columns like `Employee ID` from beating `Full Name` in auto-detection.
- **Cascading selectors** for name, headline and mutual caption. If LinkedIn
  renames a CSS class in a UI refresh, a secondary selector takes over
  before the extractor silently returns empty.
- **JSON embedded in `<script>` tags now escapes `<`, `>`, `&`** and the
  JavaScript line terminators `U+2028` / `U+2029`. A profile name
  containing `</script>` could previously break out of the script wrapper.
- **HTML notes persist in `localStorage`**, scoped per company slug.
  Survives page reload.
- **`_classify_photo()` rejects non-`http(s)` URLs** (defensive against
  any future `javascript:` or `data:` scheme surprises).
- **`_best_name_col()` scans all columns**, not just those appearing in
  the first row, so ragged CSVs don't trip the detector.
- **CJK / hangul / kana names no longer flagged suspicious.** `李明`,
  `田中太郎`, `김민수` and similar are recognised as legitimate names.
- **Multilingual mutual-count detection.** `5 conexiones en común`,
  `3 relations communes`, `2 gemeinsame Kontakte`, `4 conexões em comum`,
  `3 collegamenti in comune` now correctly resolve to `mutual_level = 2`.
  Previous versions only parsed English digit counts.
- **Payroll cross-reference is now O(n)** via exact-match dict + `thefuzz.
  process.extractOne` with a score cutoff. Meaningful speedup on large
  payrolls.
- **Pipeline now emits 6 stages** (1/6 through 6/6) with clear labels.

### Fixed
- The "Employee ID" column bug — auto-detection used to return the first
  column matching *any* name-keyword, so HR exports with `Employee ID` as
  the first column and `Full Name` as the third silently used IDs.
- Prior versions (≤ 1.2.0) treated lazy-loaded photos as absent, producing
  false-positive reds on real exports. On a 96-profile real-world snapshot
  the false-positive red count dropped from 10 to 0.
- Suspicious-name heuristic no longer mis-flags single-character-short CJK
  names or names containing hangul / kana / mixed scripts.
- `_best_name_col()` no longer picks the wrong column when the first row
  has fewer cells than later rows.

### Removed
- Unused `unicodedata` import.

### Internal
- `load_payroll()` split into `load_payroll()` (silent) and
  `load_payroll_detailed()` (returns detected column index too), so UIs
  can display the detection result.
- `extract_profiles()` now returns `(profiles, diagnostics)` so callers
  can decide how to report parser health.
- All report generators (`generate_html`, `generate_pdf`, `generate_xlsx`,
  `export_suspects_csv`, `export_snapshot_json`, `export_diff_csv`) are
  silent — they return counts/paths instead of printing. The CLI's
  progress output is now emitted by `_cli_progress_printer()`, a
  callback built on top of `run_headcheck()`'s progress protocol.

---

## [1.2.0] — prior release

- Multi-language mutual-connection detection (initial version).
- Exact-match optimisation for payroll cross-reference.
- XSS hardening in the HTML report (partial).
- `Employee ID` vs `Full Name` column disambiguation (partial — completed
  in 1.6.0).

---

## [1.1.0] — prior release

- LinkedIn ghost avatar (1×1 GIF) recognised as "no photo" for scoring.
  Later refined in 1.6.0 to distinguish lazy-load from genuinely absent.

---

## [1.0.0] — initial release

- First public version.
- HTML + PDF + suspects CSV outputs.
- Optional payroll cross-reference with fuzzy matching.
