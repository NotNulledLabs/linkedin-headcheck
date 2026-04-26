# Changelog

All notable changes to LinkedIn HeadCheck are documented here.

## [2.0.1] — 2026-04-26

Code review pass over the 2.0.0 codebase. **No behaviour change for end
users running the CLI, but library users get safer error handling and
correct type hints.** Recommended upgrade for everyone.

### Fixed
- **PDF report distinguishes the three photo states.** A profile with
  `photo_state="not_loaded"` (lazy-load placeholder) was being rendered
  as "NO PHOTO" in the PDF, contradicting the scoring engine's tri-state
  logic. The PDF now shows "photo not loaded at export" instead, matching
  what the HTML / XLSX reports already did.
- **Library functions no longer call `sys.exit()`.** `payroll.load_payroll_detailed()`
  and `snapshot._load_snapshot()` now raise `ValueError` on bad input. The
  CLI catches these and translates to a friendly error + exit code 2; library
  users (notebook, GUI, automation) can catch and recover instead of having
  their process killed.
- **`_risk()` is defensive against missing `score`.** Falls back to 0 if
  `_score()` hasn't been called yet, so library users can call `_risk()`
  on a partially-built profile dict without a `KeyError`.
- **Employer-reference detection now covers 8 languages.** The old regex
  recognised `at`/`en`/`pri`/`bei`/`chez` (English/Spanish-French-Dutch
  collision/Polish/German/French alt). Italian (`presso`), Portuguese
  (`na`/`no`), and Dutch (`bij`) were missing — Italian and Portuguese
  profiles were silently scoring lower than English equivalents. The
  consolidated `_EMPLOYER_REF_RE` constant now documents each token.
- **Argparse epilog mentioned `./reports`** as an example output directory;
  the actual default is `./output/`. Fixed.

### Changed
- **Risk thresholds are now named constants.** `RISK_GREEN_MIN = 7` and
  `RISK_YELLOW_MIN = 4` live in `headcheck.scoring`. The PDF report now
  imports them and renders "Low risk (score >= 7)" etc. from these
  values instead of hard-coded strings, so adjusting the thresholds in
  one place updates the report text everywhere.
- **`slugify()` extracted to `headcheck.constants`.** Was duplicated in
  `pipeline.py` (for filenames) and `reports/html.py` (for localStorage
  keys). They could have silently diverged on a future edit; now they
  can't.
- **Type hints corrected.** `progress: callable = None` was Python-incorrect
  (`callable` is the runtime built-in, not a typing form). Replaced with
  `Optional[Callable[[str, dict], None]]` exposed as the `ProgressCallback`
  type alias.
- **Magic numbers now have names.** `_FUZZY_MATCH_CUTOFF = 85` for payroll
  fuzzy matching, `_LAZY_PHOTO_WARN_THRESHOLD = 0.10` and
  `_LOW_MUTUAL_WARN_THRESHOLD = 0.20` for export-quality warnings. Each
  has a docstring explaining why that value was chosen.
- **Warning text decoupled from CLI presentation.** Pipeline warnings used
  to embed CLI-specific indentation (`"\n           Fix: ..."`) inside the
  message strings. Now warnings are flat sentences; the CLI uses
  `textwrap.fill` at print time to wrap and indent them. Library users
  consuming `result["warnings"]` no longer have to strip CLI artefacts.
- **`_DIFF_CHANGE_BUCKETS` constant** in `cli.py` replaces three identical
  inline tuples that listed the same five diff bucket names.
- **Variables renamed** in `snapshot.diff_snapshots` for clarity:
  `op`/`np` → `old_p`/`new_p` (the latter could be confused with
  numpy's conventional alias).
- **`xlsx.generate_xlsx` defensive against None names.** The sort key was
  `p["name"].lower()`; would crash on profiles where extraction failed.
  Now `(p.get("name") or "").lower()`.
- **`is_suspicious_name` regex precompiled.** The CJK/Cyrillic/Latin
  character class was inline twice; extracted to module-level
  `_NAME_LETTER_RE` and `_CJK_OR_KANA_RE` constants.

### Internal
- `console and console.print()` → `if console is not None: console.print()`.
  Pythonic and explicit.
- Duplicate "install questionary..." hint in the plain-fallback wizard
  removed; the message is shown once, in `_run_interactive`, before
  dropping into the plain wizard.

---

## [2.0.0] — 2026-04-25

Major release: the codebase has been split from a single 2,600-line file into
a proper Python package. **Functionally equivalent to 1.6.0** — same scoring,
same outputs, same CLI behaviour, same test results (129/129 still passing).
The reason for a 2.x bump is the public surface change: anyone who was
importing internal helpers from `headcheck.py` by their old paths needs to
adjust. Library users who only used the documented public API
(`run_headcheck`, `diff_snapshots`, …) are unaffected.

### Added
- **`install.sh`** — one-shot setup for Linux and macOS. Verifies Python
  3.10+, creates a `.venv`, installs runtime dependencies, optionally
  installs dev dependencies and runs the test suite as a sanity check.
  Idempotent. Windows users still follow the manual steps in the README.
- **Default output directory is now `./output/`** (was the current
  directory). Reports no longer clutter the repo root. The directory is
  created automatically if it doesn't exist, and is in `.gitignore` by
  default. Override with `--out path/` as before. Library users calling
  `run_headcheck()` without `out_dir=` get the same default.

### Changed
- **Package structure.** `headcheck.py` is now `headcheck/` with one module
  per dataset/responsibility:
  - `headcheck/constants.py` — version, brand, photo states, stage names
  - `headcheck/scoring.py` — `count_mutual`, `is_suspicious_name`, `_score`, `_risk`
  - `headcheck/parsing.py` — `extract_profiles` + cascading DOM selectors
  - `headcheck/payroll.py` — `load_payroll`, column auto-detect, cross-reference
  - `headcheck/pipeline.py` — `run_headcheck` + export-quality warnings
  - `headcheck/cli.py` — argparse main + `diff` subcommand + CLI progress printer
  - `headcheck/tui.py` — interactive wizard (questionary + rich, with fallback)
  - `headcheck/reports/` — `html`, `pdf`, `xlsx`, `suspects`, `snapshot`
- **Backward-compatible launcher.** `python headcheck.py …` still works
  exactly as before — the file is now a 3-line shim that calls into the
  package. No script changes needed for existing users.
- **`python -m headcheck` is now supported** as an alternative invocation
  (uses `headcheck/__main__.py`).
- **Public API unchanged.** `from headcheck import run_headcheck,
  diff_snapshots, generate_xlsx, …` keeps working. The package's
  `__init__.py` re-exports every previously-public symbol.

---

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
- **Export-quality warnings** when many photos didn't load (≥10 %) or
  mutual coverage is low (<20 %).
- **`--debug` flag** for extraction diagnostics.
- **Regression test suite.** 129 tests covering scoring, parsing, payroll,
  multilingual mutual detection, warnings, interactive mode, Excel output
  and snapshot diffing. Runs in ~3.5 seconds.

### Changed
- **Photo detection is now tri-state**: `loaded` / `not_loaded` / `absent`.
  Only genuinely absent photos force red. Lazy-load placeholders no longer
  produce false-positive reds.
- **Zero mutual connections no longer subtracts from the score.**
- **Payroll column detection** split into strong/weak keywords (fixes
  "Employee ID beats Full Name" bug).
- **Cascading selectors** for name, headline, mutual caption.
- **JSON embedded in `<script>` tags** escapes `<`, `>`, `&`, U+2028/U+2029.
- **HTML notes persist in `localStorage`**, scoped per company slug.
- **CJK / hangul / kana names** no longer flagged suspicious.
- **Multilingual mutual-count detection** (es/fr/de/pt/it).
- **Payroll cross-reference now O(n)** via thefuzz `process.extractOne`.

### Fixed
- "Employee ID" column bug in payroll auto-detection.
- Lazy-loaded photos producing false-positive reds (≤ 1.2.0). On a real
  96-profile snapshot the false-positive count dropped from 10 to 0.
- Suspicious-name heuristic for non-Latin scripts.

---

## [1.2.0] — prior release

- Multi-language mutual-connection detection (initial version).
- Exact-match optimisation for payroll cross-reference.
- XSS hardening (partial — completed in 1.6.0).
- Column disambiguation (partial — completed in 1.6.0).

## [1.1.0] — prior release

- LinkedIn ghost avatar (1×1 GIF) recognised as "no photo" for scoring.
  Refined in 1.6.0 to distinguish lazy-load from genuinely absent.

## [1.0.0] — initial release

- HTML + PDF + suspects CSV outputs, optional payroll cross-reference.
