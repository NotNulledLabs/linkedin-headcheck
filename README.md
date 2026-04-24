# LinkedIn HeadCheck

**Security and workforce verification tool for HR and security teams.**  
Built by [Not Nulled Labs](https://notnulled.com/) · [GitHub](https://github.com/NotNulledLabs)

---

<img width="1895" height="939" alt="image" src="https://github.com/user-attachments/assets/2f9404f0-f839-469c-a636-b10ff167724c" />

## Why This Tool Exists

### The Security Risk Nobody Talks About

LinkedIn is the world's leading professional network. Most companies maintain a page where employees list their current workplace — and that list is public. Anyone can see who works at your company, what their role is, what their name looks like, and how long they have been there.

Attackers use this information. Fake LinkedIn profiles impersonating employees are one of the most effective and underreported social engineering vectors in use today. The attacks are varied and convincing:

- **Employee impersonation** — A fake profile claims to work at your company, builds credibility over time, then contacts your clients, suppliers or colleagues requesting access, credentials, payments or sensitive information. Because the profile looks like a real employee, the target has no reason to be suspicious.
- **Malicious file and repository sharing** — Attackers posing as developers or IT staff share links to repositories, documents or tools. The recipient trusts the sender because they appear to work at the same company.
- **Spear phishing using internal data** — Names, job titles, org structure and tenure are all publicly visible on LinkedIn. This data is used to craft highly personalised phishing emails that are far more convincing than generic attacks.
- **Social engineering against clients and suppliers** — A fake profile posing as an employee reaches out to your contacts, requests changes to payment details, account access, or confidential documents.
- **Credential harvesting via fake job offers** — Profiles posing as HR or recruiters at your company approach candidates or employees with offers that lead to phishing pages.

None of these attacks require hacking your systems. They exploit the gap between who LinkedIn says works at your company and who actually does.

### The Problem With LinkedIn's People Section

LinkedIn's "People" tab on any company page shows everyone who has listed that company as their current employer. This list is entirely self-reported. Anyone can add any company to their profile — and LinkedIn does not verify employment.

This means a company with 100 employees may show 200 or more profiles associated with them. Some belong to former employees who never updated their profile after leaving. Others belong to freelancers or contractors who listed the company incorrectly. And some may be deliberate fake profiles created to exploit the company's identity and reputation.

LinkedIn provides no official tool to export, audit or manage this list. Page admins can report individual profiles to LinkedIn, but they cannot remove them directly, and there is no dashboard showing all associated members.

### Why You Can't Just Check Manually

For a company with 150 profiles listed, reviewing each one manually — opening the profile, noting the name, checking connections, verifying against internal records — takes hours of repetitive work. LinkedIn also throttles page loading and does not support bulk navigation, making this approach impractical at any scale.

### Why Automated Scraping Is Not the Answer

Automating LinkedIn access is prohibited by their Terms of Service and actively blocked by their infrastructure. Risks include account suspension, legal action, and unreliable results due to bot detection. No responsible tool should put your account or organisation at legal risk.

### What LinkedIn HeadCheck Does Instead

**You do the browsing. The tool does the analysis.**

You open the LinkedIn People page in your own browser, scroll through it normally, and export what is already rendered on your screen with a single browser command. No automation, no scraping, no API calls — you are saving what LinkedIn has already shown you.

The tool analyses that snapshot, scores each profile based on publicly visible signals, and produces structured reports that security and HR teams can act on in minutes instead of hours. It also saves a machine-readable snapshot so you can compare audits over time.

---

## How It Works

1. You save the LinkedIn People page HTML manually (one command or one bookmark click).
2. Run HeadCheck — either an interactive wizard (`python headcheck.py`) or with flags for scripting.
3. The script analyses every profile and assigns a risk score from 0 to 10.
4. Five output files are generated automatically (HTML, PDF, XLSX, suspects CSV, JSON snapshot).
5. Optionally, provide a payroll file to cross-reference names against your internal employee list.
6. Re-run monthly. Use the `diff` subcommand to compare snapshots and see what changed.

---

## Risk Scoring (0 – 10)

| Indicator | Points | Why it matters |
|---|---|---|
| Profile photo is loaded | +2 | Active employees almost always have a photo |
| Profile photo present but not loaded at export time | +1 | Unknown state — not a risk signal, but no full credit |
| Genuinely no profile photo | — | **Forces Red regardless of other signals** |
| Has a custom URL slug | +2 | Auto-generated IDs (`ACoAAA…`) mean the account was never configured |
| Has a headline / job title | +1 | Active profiles almost always have a title |
| Headline references an employer ("at …") | +1 | Shows the person actively maintains their work information |
| Multiple mutual connections | +3 | Strong signal — real employees share connections with colleagues |
| One mutual connection | +2 | Positive signal of a real professional relationship |
| No mutual connections | 0 | Neutral — depends on the exporter's network, not the profile itself |
| Suspicious name pattern | −2 | Name contains digits, initials only, or other anomalies |

**Score thresholds:**

| Score | Risk | Meaning |
|---|---|---|
| 7 – 10 | 🟢 Low risk | Complete, active profile |
| 4 – 6 | 🟡 Needs review | Partial profile — manual HR check recommended |
| 0 – 3 | 🔴 High risk | Minimal or photoless profile — HR priority |

### Photo States — The Critical Distinction

LinkedIn uses a 1×1 transparent GIF as a placeholder for any image that has not yet loaded. HeadCheck distinguishes three states:

- **Loaded** — the profile photo's real URL is captured. Full signal.
- **Not loaded** — the image is still in lazy-load state (either the `ghost-person` CSS class or the placeholder GIF is present). **This is treated as unknown, not as a red flag**, because it reflects the export process — not the profile. If many profiles show this state, HeadCheck shows an export-quality warning and asks you to re-export scrolling more slowly.
- **Absent** — there is genuinely no image tag, or its source is empty. Only this state forces Red.

**Prior versions (≤ 1.2.0) incorrectly treated lazy-loaded photos as absent, producing false-positive reds.** Version 1.3.0 fixed this. If you see very different numbers after upgrading, that's why.

### Understanding "Needs Review" — It Doesn't Mean Suspicious

A profile can appear as 🟡 **Needs review** for someone who genuinely works at the company. The most common reason is **no visible mutual connections** plus a weak headline (no "at [Company]" reference).

Mutual connections are detected from the perspective of the LinkedIn account used to export the page. If the exporter is not connected (directly or indirectly) to a given employee, LinkedIn shows no mutual connections — regardless of whether the employee is legitimate.

**Best practice:** Have the export done by someone with broad internal connections — an HR manager or a senior employee connected to many colleagues. This maximises the mutual connection signal and reduces false yellows. If the exporter's network coverage is too low, HeadCheck shows an export-quality warning after extraction.

---

## Export-Quality Warnings

In addition to scoring individual profiles, HeadCheck evaluates the export itself and warns when something looks off. These warnings appear after extraction and are about the HTML snapshot, not about specific profiles.

| Warning | Trigger | Fix |
|---|---|---|
| Many photos not loaded | ≥ 10 % of profiles have ghost-person placeholders | Re-open the People page and scroll slowly to the bottom so every photo has time to load, then re-export |
| Low mutual coverage | < 20 % of profiles show any mutual connections | Have a non-admin employee with broad internal connections do the export from their own LinkedIn session |

Warnings are informational. The report is still generated; scores that depend on these signals are simply less reliable.

---

## Output Files

Each run produces five files:

| File | Purpose |
|---|---|
| `headcheck_company_date.html` | Interactive report — filter, search, add HR notes (persisted in browser localStorage), export notes as CSV |
| `headcheck_company_date.pdf` | Executive PDF — grouped by risk, with clickable URLs, for management |
| `headcheck_company_date.xlsx` | Excel workbook for HR — colour-coded risk cells, score data bars, hyperlinks, autofilter, frozen header, empty Notes column |
| `headcheck_company_date_suspects.csv` | Red + Yellow only, sorted worst-first — bring to HR meetings |
| `headcheck_company_date.json` | Machine-readable snapshot for comparing audits over time (see Diff section below) |

---

<img width="695" height="349" alt="image" src="https://github.com/user-attachments/assets/30dfc29e-1561-40c1-b748-5a6bba959d32" />

## Dependencies

**Runtime (required):**

| Package | Version | Purpose |
|---|---|---|
| `beautifulsoup4` | ≥ 4.12 | Parses the LinkedIn HTML snapshot |
| `reportlab` | ≥ 4.0 | Generates the PDF report |
| `thefuzz` | ≥ 0.22 | Fuzzy name matching for payroll cross-reference |
| `python-levenshtein` | ≥ 0.25 | Speeds up fuzzy matching |
| `openpyxl` | ≥ 3.1 | Reads Excel payroll files and writes the XLSX report |

Install with:

```bash
pip install -r requirements.txt
```

**Optional (interactive wizard + test suite):**

| Package | Version | Purpose |
|---|---|---|
| `questionary` | ≥ 2.0 | Friendly prompts when running with no arguments |
| `rich` | ≥ 13.0 | Colour-coded progress, tables and diff output |
| `pytest` | ≥ 7.0 | Running the regression test suite |

These are listed in `requirements-dev.txt`. Install separately if you want the wizard or to run tests:

```bash
pip install -r requirements-dev.txt
```

**Python 3.10 or higher required.** No browser drivers, no Selenium, no Playwright, no external APIs.

---

## Installation and Running the Script

### Option 1 — Run Locally (Recommended)

Running locally means installing Python on your own computer and running the script from the terminal. This keeps all data on your machine — nothing is uploaded anywhere.

**Step 1 — Install Python**

Download Python from [python.org](https://www.python.org/downloads/). Choose version 3.10 or higher.

- **Windows:** Run the installer. Make sure to check **"Add Python to PATH"** during installation.
- **macOS:** Python comes pre-installed on modern Macs. To check: open Terminal and run `python3 --version`. If it shows 3.10 or higher, you are ready.
- **Linux:** Use your package manager: `sudo apt install python3 python3-pip`

**Step 2 — Download HeadCheck**

```bash
git clone https://github.com/NotNulledLabs/linkedin-headcheck.git
cd linkedin-headcheck
```

Or download the ZIP from GitHub and extract it.

**Step 3 — Install dependencies**

```bash
pip install -r requirements.txt
```

On some systems you may need to use `pip3` instead of `pip`.

**Step 4 — Run the script**

Two ways to run it:

**Interactive wizard (easiest):**

```bash
python headcheck.py
```

With no arguments the script asks you for the HTML path, company name, optional payroll, language and output directory. Best for IT staff who prefer a guided flow.

**With flags (for scripting):**

```bash
python headcheck.py --html people.html --company "Acme Corp"
```

<img width="1225" height="652" alt="image" src="https://github.com/user-attachments/assets/28cfcd7e-92bd-4b24-892a-4ea0ce00a70f" />

The output files will appear in the same folder (or in `--out` if specified).

---

### Option 2 — Run on Google Colab (No Installation)

Google Colab is a free online environment that runs Python in the cloud. No installation required — you only need a Google account.

**Step 1 — Open a new Colab notebook**

Go to [colab.research.google.com](https://colab.research.google.com) and create a new notebook.

**Step 2 — Install dependencies**

In the first cell, paste and run:

```python
!pip install beautifulsoup4 reportlab thefuzz python-levenshtein openpyxl -q
```

**Step 3 — Upload the script and your HTML file**

Click the folder icon on the left sidebar → upload `headcheck.py` and your `people.html`.

**Step 4 — Run**

```python
!python headcheck.py --html people.html --company "Acme Corp"
```

**Step 5 — Download the output files**

The generated files will appear in the file browser on the left. Right-click each one and select "Download".

---

### Option 3 — Run on a Remote Server (Advanced)

If you want to run HeadCheck on a cloud server (e.g. AWS, DigitalOcean, any Linux VPS):

```bash
# SSH into your server
ssh user@your-server

# Install Python if needed
sudo apt update && sudo apt install python3 python3-pip git -y

# Clone the repo
git clone https://github.com/NotNulledLabs/linkedin-headcheck.git
cd linkedin-headcheck

# Install dependencies
pip3 install -r requirements.txt

# Upload your people.html via scp from your local machine:
# scp people.html user@your-server:~/linkedin-headcheck/

# Run
python3 headcheck.py --html people.html --company "Acme Corp" --out ./reports

# Download the results:
# scp user@your-server:~/linkedin-headcheck/reports/* ./local-folder/
```

---

## Step-by-Step: Exporting the LinkedIn People Page

### Why this manual step is necessary

LinkedIn does not provide a public API for this data. Automated scraping violates their Terms of Service. The only compliant approach is to export what you can already see in your own browser session using a standard browser capability.

### Option A — Browser Console

1. Log in to LinkedIn.
2. Go to the target company's LinkedIn page and click **"People"**.
3. **Scroll all the way to the bottom, slowly** — LinkedIn loads profiles and their photos progressively. Scrolling too fast leaves placeholders in place.
4. Open the browser console:
   - **Chrome / Edge / Brave:** `F12` → Console tab
   - **Firefox:** `F12` → Console tab
   - **Safari:** Preferences → Advanced → Enable Developer Tools → `Cmd+Option+C`
5. Click in the console, paste the following, and press **Enter**:
   ```javascript
   copy(document.documentElement.outerHTML)
   ```
<br>
<img width="1772" height="929" alt="image" src="https://github.com/user-attachments/assets/76f5a985-a9e6-4806-908f-bb1d6955f2f4" />
<br>

6. Open any text editor, paste (`Ctrl+V` / `Cmd+V`), save as `people.html`.

### Option B — Bookmarklet (no console needed)

A bookmarklet runs JavaScript with a single click — same result as Option A.

**One-time setup:**
1. Right-click your bookmarks bar → "Add bookmark".
2. Name: `HeadCheck Export`
3. URL (paste the entire line):
   ```
   javascript:void(function(){var a=document.createElement('a');a.href='data:text/html;charset=utf-8,'+encodeURIComponent(document.documentElement.outerHTML);a.download='people.html';document.body.appendChild(a);a.click();document.body.removeChild(a);})();
   ```
4. Save.

**Usage:** Go to the People page, scroll slowly to the bottom, click the bookmark. `people.html` downloads automatically.

---

## Payroll File Format

Accepted formats: `.csv`, `.xlsx`, `.xls`

Column detection is automatic and uses a two-tier strategy:

1. **Strong keywords** — headers like `full name`, `name`, `nombre`, `apellido`, `nom` win immediately.
2. **Weak keywords** — headers like `employee`, `staff`, `worker` are accepted only if their column contents actually look like human names. This prevents columns like `Employee ID` from being mistaken for the names column.
3. **Content-based fallback** — if no header keyword is found, the column whose cells best match a human-name pattern is chosen.

**No reformatting required.** A sample file is included: `sample_payroll.csv`.

---

## Tracking Changes Over Time — the Diff Subcommand

A security audit isn't a one-off exercise. Running HeadCheck monthly gives you a running record; the `diff` subcommand tells you what changed between two runs.

Each HeadCheck run produces a `.json` snapshot next to the HTML / PDF / XLSX outputs. Compare two of them:

```bash
python headcheck.py diff reports/headcheck_acme_2026-03.json reports/headcheck_acme_2026-04.json
```

The diff classifies every profile into five buckets:

| Bucket | Meaning | Why it matters |
|---|---|---|
| ✚ **Appeared** | Profiles in the new snapshot that weren't in the old | New hires, contractors, or **newly-created fake profiles** |
| ✖ **Disappeared** | Profiles in the old snapshot that aren't in the new | Former employees who updated their profile, or **profiles LinkedIn removed** after a report |
| ⬆ **Risk worsened** | green → yellow, yellow → red, green → red | A profile that was fine is now flagged — photo removed, headline gone, etc. |
| ⬇ **Risk improved** | The opposite — something got fixed | Often means HR reached out and the employee updated their profile |
| ~ **Score drift** | Score changed but risk bucket stayed the same | Minor changes — worth noting, not urgent |

Identity between snapshots is established by the LinkedIn URL slug. If a user changes their custom slug, they'll show up as both *appeared* and *disappeared* — a limitation of using public data without LinkedIn's internal IDs.

Additional options:

```bash
# Export the diff as a CSV for HR spreadsheets
python headcheck.py diff old.json new.json --csv changes.csv

# Plain text output (no colour) for terminals that don't support it or for logs
python headcheck.py diff old.json new.json --plain
```

The subcommand's exit code is non-zero when any change is detected, so you can run it in cron or CI and alert on changes:

```bash
python headcheck.py diff last.json this.json && echo "No changes" || echo "Review needed"
```

---

## All Command-Line Options

```bash
# Interactive wizard (no arguments)
python headcheck.py

# Main audit
python headcheck.py --html people.html --company "Acme Corp"
python headcheck.py --html people.html --company "Acme Corp" --payroll staff.xlsx
python headcheck.py --html people.html --company "Acme Corp" --lang es --out ./reports

# Diff two snapshots
python headcheck.py diff old.json new.json
python headcheck.py diff old.json new.json --csv changes.csv --plain
```

**Main audit flags:**

| Argument | Required | Default | Description |
|---|---|---|---|
| `--html` | Yes | — | Path to saved LinkedIn People HTML file |
| `--company` | No | `"Company"` | Company name for report headers |
| `--payroll` | No | — | Payroll file (`.csv`, `.xlsx`, `.xls`) |
| `--lang` | No | `en` | LinkedIn interface language: `en` `es` `fr` `de` `pt` `it` |
| `--out` | No | `.` | Output directory for the report files |
| `--debug` | No | off | Print extraction diagnostics (how many anchors found, photo states, skip reasons) |

**Diff flags:**

| Argument | Required | Default | Description |
|---|---|---|---|
| `old` | Yes | — | Older snapshot `.json` |
| `new` | Yes | — | Newer snapshot `.json` |
| `--csv` | No | — | Write a CSV export of the diff to this path |
| `--plain` | No | off | Plain text output (no colour, no `rich`) |

---

## Using HeadCheck as a Library

The pipeline is exposed as a pure function so you can embed HeadCheck in your own tools without going through the command line:

```python
from headcheck import run_headcheck

result = run_headcheck(
    html_path="people.html",
    company="Acme Corp",
    payroll_path="staff.xlsx",   # optional
    lang="en",
    out_dir="./reports",
)

print(result["stats"])        # {'total': 96, 'red': 0, 'yellow': 33, 'green': 63, 'suspects_exported': 33}
print(result["warnings"])     # list of export-quality messages
print(result["outputs"])      # {'html': ..., 'pdf': ..., 'xlsx': ..., 'suspects_csv': ..., 'snapshot': ...}
for profile in result["profiles"]:
    ...
```

Optionally pass a `progress=callback` to receive stage-by-stage updates:

```python
def my_progress(stage, info):
    print(f"→ {stage}: {info}")

run_headcheck(html_path="people.html", company="Acme Corp", progress=my_progress)
```

For snapshot comparison:

```python
from headcheck import diff_snapshots, export_diff_csv

diff = diff_snapshots("march.json", "april.json")
print(f"New: {len(diff['appeared'])}, Gone: {len(diff['disappeared'])}")
print(f"Risk worsened: {len(diff['risk_up'])}")

export_diff_csv(diff, "changes.csv")
```

The library functions do not print anything — the CLI wraps them with a progress callback for its own output. This keeps the library usable from GUIs, notebooks, or other automation.

---

## Running the Tests

The project includes a pytest suite (129 tests as of 1.6.0) that covers scoring, HTML parsing, payroll matching, multilingual mutual-connection detection, export-quality warnings, Excel output, interactive mode and snapshot diffing. It also includes regression tests for past bugs so they cannot silently come back.

```bash
pip install -r requirements-dev.txt
python -m pytest tests/
```

The suite runs in under four seconds. Integration tests that require a real LinkedIn HTML snapshot are automatically skipped if the file is not present, so the suite is green on a fresh clone.

---

## Limitations

- Only profiles loaded on screen at export time are captured — scroll fully before exporting.
- LinkedIn limits the People section to approximately 1,000 visible profiles.
- The report is a snapshot. LinkedIn profiles change constantly.
- LinkedIn's identity verification badge is not captured in the People page HTML.
- Profiles whose photos did not load by export time are marked as "photo not loaded" and get a reduced photo signal. They are not flagged red, but the weaker signal may push borderline legitimate profiles into yellow. Scroll more slowly and re-export if HeadCheck warns about this.
- The diff subcommand uses the LinkedIn URL slug as the identity key. A profile that changes its custom slug will appear as both "disappeared" and "appeared".

### ⚠️ Known Limitation for LinkedIn Page Admins

If you are an admin of the company's LinkedIn page, LinkedIn will redirect you to the admin dashboard when you navigate to the People section. The `?viewAsMember=true` parameter lets you view the page, but **that view does not include your personal network** — mutual connections will not appear for any profile.

This means all profiles will score lower (no mutual connection signal), and legitimate employees will appear as 🟡 Needs review instead of 🟢 Low risk. HeadCheck will show a "low mutual coverage" warning in this scenario.

**This is a LinkedIn limitation, not a tool limitation.**

To get accurate mutual connection data, the export must be done by someone who:
- Is **not** a page admin, and
- Navigates to `linkedin.com/company/[company-slug]/people` from their **normal LinkedIn session**

Any non-admin employee with connections to several colleagues will produce significantly better results. The more internal connections that person has, the more profiles will correctly appear as green.

---

## What to Do After the Audit

Once HR has reviewed the report and identified suspicious profiles, these are the available actions:

### Former employees who never updated their profile

This is the most common case. The person genuinely worked at the company but left and forgot to update LinkedIn.

**Best approach:** Contact them directly and ask them to edit the Experience section on their LinkedIn profile and remove or update the position. LinkedIn will automatically disassociate their profile from the company page. Changes can take up to 30 days to reflect.

### Profiles that appear fake or malicious

For profiles where there is no known relationship with the company and the association appears intentional or fraudulent:

**Step 1 — Report via LinkedIn's form**
LinkedIn does not allow page admins to remove associated members directly — members self-associate by editing their own profiles. To request removal, you must contact LinkedIn and provide:
- The full name of the person
- A screenshot of the company People page showing that person
- A link to their public profile
- An explanation of why the association is incorrect

Submit the request through LinkedIn's official support: [linkedin.com/help/linkedin/ask/cp-master](https://www.linkedin.com/help/linkedin/ask/cp-master)

> Note: you must have a confirmed company email address registered to your LinkedIn account to submit this request.

**Step 2 — Report the individual profile**
On the person's LinkedIn profile, click the **More** button (···) → **Report / Block** → select the appropriate reason (fake profile, incorrect information, etc.). LinkedIn will review and may remove the profile or the company association.

**Step 3 — Be patient**
LinkedIn support response times for these requests vary. If the association is clearly malicious, escalating via [@LinkedInHelp](https://twitter.com/LinkedInHelp) on Twitter/X can sometimes speed up the process.

### What admins cannot do

- **Cannot directly remove** a member from the company page — only the member can edit their own profile
- **Cannot see a list** of all associated members in the admin dashboard — this is why HeadCheck exists
- **Cannot prevent** someone from associating themselves with the company — LinkedIn's system relies on self-reported data

---

## Privacy and Legal

- Processes only publicly visible LinkedIn data from your own authenticated session.
- Reports contain personal data — treat as confidential HR documents.
- Do not share outside the organisation or use for purposes other than workforce verification.
- Ensure compliance with GDPR, CCPA, LGPD, or other applicable regulations.
- `.gitignore` prevents accidentally committing reports, payroll files, HTML snapshots, or JSON snapshots.

---

## Version History

See [CHANGELOG.md](CHANGELOG.md) for the full list of changes per release.

Current version: **1.6.0** — interactive wizard, Excel output, snapshot diff, library API, 129 tests. Recommended upgrade for all users.

---

## Contributing

Pull requests welcome. Useful areas:

- Additional `--lang` values for mutual connection detection
- Additional scoring signals (e.g. LinkedIn identity verification badge, if captureable from the DOM)
- A lightweight GUI for non-technical users
- Browser extension for more robust capture via LinkedIn's internal API (would eliminate the lazy-load photo issue entirely)
- Transliteration support so `李明` and `Li Ming` can be matched across scripts in payroll cross-reference

Please include or update tests under `tests/` for any behaviour change.

---

## License

MIT License — free to use, modify, and distribute.

---

*LinkedIn HeadCheck is an independent open-source project, not affiliated with or endorsed by LinkedIn Corporation.*

Built by [Not Nulled Labs](https://notnulled.com/) · [github.com/NotNulledLabs](https://github.com/NotNulledLabs)
