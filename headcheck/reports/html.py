"""
Interactive HTML report.

Single-file standalone HTML the user opens in any browser. Filterable
table, search box, per-profile notes (persisted in localStorage scoped
by company), CSV export of notes, no external dependencies.

Security note: all profile-derived strings are escaped before rendering,
both at JSON-embedding time (escape <, >, &, U+2028/U+2029 to prevent
breaking out of <script> tags) and again at DOM-insertion time via
escapeHtml() in the page's JavaScript.
"""
import json
import re
from datetime import datetime

from ..constants import VERSION, BRAND_NAME, BRAND_URL, REPO_URL, MAX_SCORE, slugify


def generate_html(profiles: list[dict], company: str, has_payroll: bool, out: str):
    total  = len(profiles)
    green  = sum(1 for p in profiles if p["risk"] == "green")
    yellow = sum(1 for p in profiles if p["risk"] == "yellow")
    red    = sum(1 for p in profiles if p["risk"] == "red")
    ts     = datetime.now().strftime("%B %d, %Y — %H:%M")
    # Stable key for scoping localStorage notes per company — must match main()'s slug.
    co_slug = slugify(company)

    if has_payroll:
        exact     = sum(1 for p in profiles if p.get("payroll_status") == "exact")
        fuzzy_n   = sum(1 for p in profiles if p.get("payroll_status") == "fuzzy")
        not_found = sum(1 for p in profiles if p.get("payroll_status") == "not_found")
    else:
        exact = fuzzy_n = not_found = 0

    # Escape sequences that could break out of the surrounding <script> tag.
    # json.dumps doesn't escape < / > / & by default, so a profile name
    # containing "</script>" would terminate the script early. We replace
    # those characters with their \u-escaped forms, which remain valid JSON
    # but are inert inside an HTML document.
    data_json = (
        json.dumps(profiles, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")  # JS line terminators break JSON in <script>
        .replace("\u2029", "\\u2029")
    )

    payroll_th  = "<th>Payroll <span class='tip' data-tip='Whether this name was found in the uploaded payroll file.'>?</span></th><th>Matched name</th>" if has_payroll else ""
    payroll_sel = """<select id="fPayroll">
          <option value="">All payroll statuses</option>
          <option value="exact">In payroll</option>
          <option value="fuzzy">Similar name</option>
          <option value="not_found">Not found</option>
        </select>""" if has_payroll else ""

    payroll_kpis = f"""
      <div class="kpi"><div class="kpi-val c-green">{exact}</div><div class="kpi-lbl">In payroll</div></div>
      <div class="kpi"><div class="kpi-val c-amber">{fuzzy_n}</div><div class="kpi-lbl">Similar name</div></div>
      <div class="kpi"><div class="kpi-val c-red">{not_found}</div><div class="kpi-lbl">Not in payroll</div></div>
    """ if has_payroll else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LinkedIn HeadCheck — {company}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {{
  --bg:        #F2F4F8;
  --surface:   #FFFFFF;
  --border:    #D9DEE9;
  --text:      #111827;
  --muted:     #4B5563;
  --blue:      #1D4ED8;
  --blue-lt:   #EFF6FF;
  --blue-dk:   #1E3A8A;
  --green:     #166534;
  --green-lt:  #DCFCE7;
  --amber:     #92400E;
  --amber-lt:  #FEF3C7;
  --red:       #991B1B;
  --red-lt:    #FEE2E2;
  --radius:    8px;
  --shadow:    0 1px 3px rgba(0,0,0,.10), 0 1px 2px rgba(0,0,0,.06);
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.5; }}

/* HEADER */
.header {{ background: var(--blue-dk); color: #fff; padding: 0; }}
.header-inner {{ padding: 24px 40px 20px; }}
.brand-row {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }}
.brand {{ display: flex; align-items: center; gap: 10px; }}
.brand-icon {{ width: 34px; height: 34px; background: #fff; border-radius: 6px; display: flex; align-items: center; justify-content: center; color: var(--blue-dk); font-weight: 800; font-size: 13px; font-family: 'IBM Plex Mono', monospace; flex-shrink: 0; }}
.brand-name {{ font-size: 13px; font-weight: 600; color: rgba(255,255,255,.9); }}
.brand-sub  {{ font-size: 11px; color: rgba(255,255,255,.55); }}
.header-meta {{ font-size: 11px; color: rgba(255,255,255,.55); text-align: right; line-height: 1.7; }}
.header h1 {{ font-size: 20px; font-weight: 700; color: #fff; }}
.header h1 span {{ color: #93C5FD; }}

/* HELP PANEL */
.help-bar {{
  background: #1E40AF;
  border-bottom: 1px solid #1D4ED8;
  padding: 0 40px;
  display: flex; gap: 0; overflow: hidden;
}}
.help-tab {{
  padding: 10px 18px;
  font-size: 13px; font-weight: 500;
  color: rgba(255,255,255,.65);
  cursor: pointer; border: none; background: none;
  border-bottom: 2px solid transparent;
  transition: color .15s, border-color .15s;
}}
.help-tab.active {{ color: #fff; border-bottom-color: #93C5FD; }}
.help-panel {{
  background: #1E3A8A;
  border-bottom: 1px solid #1D4ED8;
  padding: 20px 40px;
  font-size: 14px; color: rgba(255,255,255,.85);
  line-height: 1.8;
  display: none;
}}
.help-panel.active {{ display: block; }}
.help-panel h3 {{ font-size: 13px; font-weight: 700; color: #fff; margin-bottom: 10px; text-transform: uppercase; letter-spacing: .06em; }}
.help-panel p {{ margin-bottom: 10px; }}
.help-panel code {{ background: rgba(255,255,255,.12); padding: 2px 7px; border-radius: 4px; font-family: 'IBM Plex Mono', monospace; font-size: 12px; }}
.help-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }}
.help-grid dt {{ font-weight: 600; color: #93C5FD; margin-bottom: 4px; font-size: 13px; }}
.help-grid dd {{ color: rgba(255,255,255,.8); font-size: 13px; line-height: 1.6; }}

/* KPI BAR */
.kpi-bar {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 14px 40px; display: flex; gap: 10px; flex-wrap: wrap; box-shadow: var(--shadow); }}
.kpi {{ background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); padding: 12px 18px; min-width: 96px; text-align: center; }}
.kpi-val {{ font-size: 24px; font-weight: 700; line-height: 1; font-family: 'IBM Plex Mono', monospace; }}
.kpi-lbl {{ font-size: 10px; color: var(--muted); margin-top: 3px; text-transform: uppercase; letter-spacing: .05em; }}
.c-blue  {{ color: var(--blue);  }}
.c-green {{ color: var(--green); }}
.c-amber {{ color: var(--amber); }}
.c-red   {{ color: var(--red);   }}

/* FILTERS */
.filters {{
  position: sticky; top: 0; z-index: 60;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 10px 40px;
  display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
  box-shadow: var(--shadow);
}}
.filters input, .filters select {{
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 7px 11px; font-family: 'Inter', sans-serif; font-size: 13px;
  color: var(--text); background: var(--bg); outline: none;
  transition: border-color .15s;
}}
.filters input {{ min-width: 210px; }}
.filters input:focus, .filters select:focus {{ border-color: var(--blue); }}
.filter-info {{ margin-left: auto; font-size: 11px; color: var(--muted); font-family: 'IBM Plex Mono', monospace; }}
.btn-export {{
  margin-left: 8px;
  padding: 7px 14px;
  background: var(--blue); color: #fff;
  border: none; border-radius: var(--radius);
  font-size: 12px; font-weight: 600; font-family: 'Inter', sans-serif;
  cursor: pointer; transition: background .15s;
}}
.btn-export:hover {{ background: var(--blue-dk); }}

/* TABLE */
.table-wrap {{ padding: 20px 40px 48px; overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; background: var(--surface); border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow); }}
thead th {{
  background: #F8FAFD; border-bottom: 2px solid var(--border);
  padding: 10px 13px; text-align: left;
  font-size: 11px; font-weight: 600; color: var(--muted);
  text-transform: uppercase; letter-spacing: .06em;
  white-space: nowrap;
}}
tbody tr {{ border-bottom: 1px solid var(--border); transition: background .1s; }}
tbody tr:last-child {{ border-bottom: none; }}
tbody tr:hover {{ background: #F8FAFF; }}
tbody td {{ padding: 10px 13px; vertical-align: middle; }}

/* AVATAR */
.av-cell {{ width: 44px; }}
.av {{ width: 38px; height: 38px; border-radius: 50%; object-fit: cover; border: 2px solid var(--border); display: block; }}
.av-wrap {{ display: inline-block; }}
.av-ph {{ width: 38px; height: 38px; border-radius: 50%; background: #E5E7EB; display: flex; align-items: center; justify-content: center; font-size: 16px; border: 2px dashed #D1D5DB; color: #9CA3AF; }}

/* BADGES */
.badge {{ display: inline-block; border-radius: 4px; padding: 3px 9px; font-size: 11px; font-weight: 600; white-space: nowrap; }}
.badge-green  {{ background: var(--green-lt);  color: var(--green);  }}
.badge-yellow {{ background: var(--amber-lt);  color: var(--amber);  }}
.badge-red    {{ background: var(--red-lt);    color: var(--red);    }}
.badge-susp   {{ background: #FEF9C3; color: #713F12; font-size: 10px; margin-left: 4px; }}

/* SCORE */
.sc-wrap {{ display: flex; align-items: center; gap: 6px; }}
.sc-bar  {{ width: 52px; height: 5px; background: #E5E7EB; border-radius: 3px; overflow: hidden; }}
.sc-fill {{ height: 100%; border-radius: 3px; }}
.sc-txt  {{ font-size: 11px; color: var(--muted); font-family: 'IBM Plex Mono', monospace; min-width: 28px; }}

/* INDICATORS */
.inds {{ display: flex; gap: 2px; flex-wrap: wrap; }}
.ind     {{ font-size: 14px; cursor: default; }}
.ind-off {{ opacity: .2; filter: grayscale(1); }}

/* HEADLINE */
.hl-cell {{ max-width: 220px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--muted); font-size: 12px; }}

/* LINK */
a.pl {{ color: var(--blue); text-decoration: none; font-size: 12px; font-weight: 500; }}
a.pl:hover {{ text-decoration: underline; }}

/* PAYROLL */
.ps {{ font-size: 11px; font-weight: 600; }}
.ps-exact     {{ color: var(--green); }}
.ps-fuzzy     {{ color: var(--amber); }}
.ps-not_found {{ color: var(--red);   }}
.pm {{ font-size: 11px; color: var(--muted); max-width: 140px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; }}

/* TOOLTIP */
.tip {{
  display: inline-flex; align-items: center; justify-content: center;
  width: 15px; height: 15px; border-radius: 50%;
  background: var(--border); color: var(--muted);
  font-size: 10px; font-weight: 700; cursor: help;
  position: relative; vertical-align: middle; margin-left: 3px;
}}
.tip:hover::after {{
  content: attr(data-tip);
  position: absolute; bottom: 120%; left: 50%; transform: translateX(-50%);
  background: #1F2937; color: #fff;
  padding: 6px 10px; border-radius: 6px;
  font-size: 11px; font-weight: 400; white-space: nowrap;
  z-index: 999; pointer-events: none;
  box-shadow: 0 2px 8px rgba(0,0,0,.2);
}}

/* NO RESULTS */
.no-res {{ display: none; text-align: center; padding: 48px; color: var(--muted); font-size: 13px; }}

/* NOTES */
.note-input {{
  border: 1px solid var(--border); border-radius: 4px;
  padding: 4px 7px; font-size: 11px; font-family: 'Inter', sans-serif;
  color: var(--text); background: var(--bg); width: 120px;
  transition: border-color .15s;
}}
.note-input:focus {{ outline: none; border-color: var(--blue); }}

/* FOOTER */
footer {{
  border-top: 1px solid var(--border);
  padding: 14px 40px;
  font-size: 11px; color: var(--muted);
  display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;
  background: var(--surface);
}}
footer a {{ color: var(--blue); text-decoration: none; }}
footer a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
  <div class="header-inner">
    <div class="brand-row">
      <div class="brand">
        <div class="brand-icon">HC</div>
        <div>
          <div class="brand-name">LinkedIn HeadCheck</div>
          <div class="brand-sub">Security &amp; Workforce Verification Tool by Not Nulled Labs</div>
        </div>
      </div>
      <div class="header-meta">
        Generated: {ts}<br>
        Profiles analysed: <strong style="color:#fff">{total}</strong>
      </div>
    </div>
    <h1>People Audit — <span>{company}</span></h1>
  </div>

  <!-- HELP TABS -->
  <div class="help-bar">
    <button class="help-tab" onclick="toggleHelp('how', this)">How it works</button>
    <button class="help-tab" onclick="toggleHelp('scoring', this)">Scoring explained</button>
    <button class="help-tab" onclick="toggleHelp('glossary', this)">Glossary</button>
    <button class="help-tab" onclick="toggleHelp('nextsteps', this)" style="color:#86EFAC">Next steps</button>
  </div>

  <div class="help-panel" id="help-how">
    <h3>How This Report Was Generated</h3>
    <p>A LinkedIn company "People" page was exported as an HTML snapshot using the browser console command <code>copy(document.documentElement.outerHTML)</code>. LinkedIn HeadCheck then parsed that snapshot and scored each profile based on publicly visible signals.</p>
    <p>No scraping was performed. No LinkedIn API was used. The data reflects what was visible on screen at the time of export.</p>
    <p><strong>Important:</strong> Risk scores indicate profile completeness — not confirmed employment. A complete profile does not guarantee the person currently works here. All findings should be verified by HR against internal records.</p>
    <p style="margin-top:10px;padding:10px 14px;background:rgba(245,158,11,.12);border-left:3px solid #f59e0b;border-radius:4px;font-size:13px">
      <strong>⚠️ If you are a LinkedIn page admin:</strong> LinkedIn does not show your personal network in the admin view, even with <code>?viewAsMember=true</code>. This means mutual connections will be absent for all profiles, causing legitimate employees to appear as yellow instead of green. For accurate results, the export should be done by a non-admin employee navigating to the People page from their normal LinkedIn session.
    </p>
  </div>

  <div class="help-panel" id="help-scoring">
    <h3>How Risk Scores Work (0 – {MAX_SCORE})</h3>
    <div class="help-grid">
      <dl><dt>+2 — Profile photo</dt><dd>Has a visible profile picture. Absence forces the profile to Red regardless of other signals.</dd></dl>
      <dl><dt>+2 — Custom URL</dt><dd>Profile has a personalised slug (e.g. /in/john-smith). Auto-generated IDs like ACoAAA… suggest an unconfigured account.</dd></dl>
      <dl><dt>+1 — Headline present</dt><dd>Profile has a job title or headline text.</dd></dl>
      <dl><dt>+1 — Employer reference</dt><dd>Headline contains "at", "en", or similar linking the person to an employer.</dd></dl>
      <dl><dt>+2 or +3 — Mutual connections</dt><dd>LinkedIn shows connections shared with the company network. One mutual = +2, multiple = +3. Zero mutuals = −1 penalty.</dd></dl>
      <dl><dt>−2 — Suspicious name</dt><dd>Name contains digits, initials only, special characters, or other unusual patterns.</dd></dl>
    </div>
    <p style="margin-top:12px">Score ≥ 7 → Green &nbsp;·&nbsp; Score 4–6 → Yellow &nbsp;·&nbsp; Score ≤ 3 → Red</p>
    <p style="margin-top:10px;font-size:13px;opacity:.75">Profiles exported from a page admin account will show no mutual connections and will score lower as a result. This is a LinkedIn limitation.</p>
  </div>

  <div class="help-panel" id="help-glossary">
    <h3>Glossary</h3>
    <div class="help-grid">
      <dl><dt>Mutual connections</dt><dd>People in the LinkedIn network of the account used to export the page who are also connected to this profile. Not visible when exported from a page admin account.</dd></dl>
      <dl><dt>Custom URL</dt><dd>A profile address chosen by the user (e.g. /in/john-smith) as opposed to an auto-generated ID.</dd></dl>
      <dl><dt>Slug</dt><dd>The identifier part of a LinkedIn profile URL after /in/.</dd></dl>
      <dl><dt>Payroll match — Exact</dt><dd>The name appears in the payroll file with identical spelling.</dd></dl>
      <dl><dt>Payroll match — Similar</dt><dd>A close but not identical match was found (fuzzy matching, ≥85% similarity).</dd></dl>
      <dl><dt>Payroll match — Not found</dt><dd>No matching name found. May indicate a former employee, contractor, or error in either list.</dd></dl>
      <dl><dt>Suspicious name</dt><dd>The name contains digits, only initials, special characters, or other patterns uncommon in human names.</dd></dl>
      <dl><dt>Page admin limitation</dt><dd>LinkedIn page admins cannot view the People section with their personal network. Use a non-admin account for best results.</dd></dl>
    </div>
  </div>

  <div class="help-panel" id="help-nextsteps">
    <h3>What to Do After the Audit</h3>
    <p>Once you have identified suspicious profiles, these are the actions available to you depending on the case.</p>

    <div class="help-grid" style="margin-top:14px">
      <div>
        <dl><dt style="color:#86EFAC;margin-bottom:6px">👋 Former employee — forgot to update</dt>
        <dd>The most common case. Contact the person directly and ask them to edit the Experience section on their LinkedIn profile and remove or update the position. LinkedIn will automatically disassociate their profile. Changes can take up to 30 days to reflect.</dd></dl>
      </div>
      <div>
        <dl><dt style="color:#FCA5A5;margin-bottom:6px">🚨 Fake or malicious profile</dt>
        <dd>
          <strong>Step 1 — Report to LinkedIn</strong><br>
          Admins cannot remove members directly. Contact LinkedIn via their support form providing: the person's full name, a screenshot of the People page showing them, a link to their profile, and an explanation.<br>
          Form: <a href="https://www.linkedin.com/help/linkedin/ask/cp-master" target="_blank" style="color:#93C5FD">linkedin.com/help/linkedin/ask/cp-master</a><br><br>
          <strong>Step 2 — Report the profile</strong><br>
          On the person's LinkedIn profile, click ··· → Report / Block → select the appropriate reason (fake profile, incorrect information).<br><br>
          <strong>Step 3 — Escalate if needed</strong><br>
          If there is no response, contacting <a href="https://twitter.com/LinkedInHelp" target="_blank" style="color:#93C5FD">@LinkedInHelp</a> on X/Twitter can speed up the process.
        </dd></dl>
      </div>
    </div>

    <div style="margin-top:16px;padding:10px 14px;background:rgba(239,68,68,.1);border-left:3px solid #ef4444;border-radius:4px;font-size:11px">
      <strong>What admins cannot do:</strong> Admins cannot directly remove a member from the company page, cannot see a full list of associated members in the admin dashboard, and cannot prevent someone from self-associating with the company. LinkedIn's system relies entirely on self-reported data — which is exactly why this tool exists.
    </div>
  </div>
</div>

<!-- KPI BAR -->
<div class="kpi-bar">
  <div class="kpi"><div class="kpi-val c-blue">{total}</div><div class="kpi-lbl">Total</div></div>
  <div class="kpi"><div class="kpi-val c-green">{green}</div><div class="kpi-lbl">Low risk</div></div>
  <div class="kpi"><div class="kpi-val c-amber">{yellow}</div><div class="kpi-lbl">Review</div></div>
  <div class="kpi"><div class="kpi-val c-red">{red}</div><div class="kpi-lbl">High risk</div></div>
  {payroll_kpis}
</div>

<!-- FILTERS -->
<div class="filters">
  <input type="text" id="fSearch" placeholder="Search by name or headline…">
  <select id="fRisk">
    <option value="">All risk levels</option>
    <option value="green">Low risk</option>
    <option value="yellow">Needs review</option>
    <option value="red">High risk</option>
  </select>
  <select id="fMutual">
    <option value="">All connections</option>
    <option value="0">No mutual connections</option>
    <option value="1">1 mutual connection</option>
    <option value="2">Multiple mutual connections</option>
  </select>
  {payroll_sel}
  <button class="btn-export" onclick="exportNotes()">Export notes CSV</button>
  <span class="filter-info" id="fCount">{total} profiles shown</span>
</div>

<!-- TABLE -->
<div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th class="av-cell"></th>
        <th>Name <span class="tip" data-tip="Full name as shown on LinkedIn">?</span></th>
        <th>Headline <span class="tip" data-tip="Job title or headline from the profile">?</span></th>
        <th>Risk <span class="tip" data-tip="Green = low risk · Yellow = review needed · Red = high risk or no photo">?</span></th>
        <th>Score <span class="tip" data-tip="Completeness score from 0 to {MAX_SCORE}. Higher = more complete profile.">?</span></th>
        <th>Signals <span class="tip" data-tip="📷 photo · ✏️ headline · 🔗 custom URL · 🤝 mutual connections · ⚠️ suspicious name">?</span></th>
        {payroll_th}
        <th>Notes <span class="tip" data-tip="Add HR notes per profile. Export all notes with the button above.">?</span></th>
        <th>Profile</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
  <div class="no-res" id="noRes">No profiles match the current filters.</div>
</div>

<!-- FOOTER -->
<footer>
  <span>
    <a href="{REPO_URL}" target="_blank" rel="noopener">LinkedIn HeadCheck</a>
    &nbsp;·&nbsp;
    <a href="{BRAND_URL}" target="_blank" rel="noopener">{BRAND_NAME}</a>
    &nbsp;·&nbsp; v{VERSION}
  </span>
  <span>{company} &nbsp;·&nbsp; {ts}</span>
</footer>

<script>
const profiles   = {data_json};
const hasPayroll = {'true' if has_payroll else 'false'};
const MAX        = {MAX_SCORE};

// Escape HTML special characters before interpolating any user-controlled
// string into innerHTML. LinkedIn profile text is ultimately attacker-
// controlled, so we never trust it.
const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({{
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
}}[c]));

// Persist notes across page reloads so HR can pause and resume.
const NOTES_KEY = 'headcheck_notes_{co_slug}';
let notes = {{}};
try {{ notes = JSON.parse(localStorage.getItem(NOTES_KEY) || '{{}}'); }} catch (e) {{ notes = {{}}; }}
function saveNotes() {{
  try {{ localStorage.setItem(NOTES_KEY, JSON.stringify(notes)); }} catch (e) {{}}
}}

function scoreColor(s) {{
  if (s / MAX >= 0.7) return 'var(--green)';
  if (s / MAX >= 0.4) return 'var(--amber)';
  return 'var(--red)';
}}

const RISK_LABELS = {{ green:'Low risk', yellow:'Needs review', red:'High risk' }};
const PS_ICONS    = {{ exact:'&#10003; In payroll', fuzzy:'&#126; Similar', not_found:'&#10007; Not found' }};
const PS_CLS      = {{ exact:'ps-exact', fuzzy:'ps-fuzzy', not_found:'ps-not_found' }};
const MUTUAL_LABELS = ['No mutual', '1 mutual', 'Multiple mutuals'];

function ind(icon, active, tip) {{
  return `<span class="ind ${{active?'':'ind-off'}}" title="${{escapeHtml(tip)}}">${{icon}}</span>`;
}}

function payrollCells(p) {{
  if (!hasPayroll) return '';
  const st = p.payroll_status || 'not_found';
  const match = escapeHtml(p.payroll_match || '');
  return `<td><span class="ps ${{PS_CLS[st]||''}}">${{PS_ICONS[st]||'—'}}</span></td>`
       + `<td><span class="pm" title="${{match}}">${{match || '—'}}</span></td>`;
}}

function renderRow(p, idx) {{
  const safeName     = escapeHtml(p.name);
  const safeHeadline = escapeHtml(p.headline || '');
  const safeAvatar   = escapeHtml(p.avatar_url || '');
  const safeUrl      = escapeHtml(p.profile_url);
  const safeReason   = escapeHtml(p.suspicious_reason || '');

  // Render both img and placeholder — toggle visibility via onerror/onload
  // to avoid unescaped HTML chars inside onerror attribute breaking the parser
  const av = p.avatar_url
    ? `<span class="av-wrap">
        <img class="av" src="${{safeAvatar}}" alt=""
             loading="lazy"
             onerror="this.style.display='none';this.parentNode.querySelector('.av-ph').style.display='flex'">
        <span class="av-ph" style="display:none">&#128100;</span>
       </span>`
    : `<span class="av-wrap"><span class="av-ph">&#128100;</span></span>`;

  const pct = Math.round(p.score / MAX * 100);
  const sc  = `<div class="sc-wrap">
    <div class="sc-bar"><div class="sc-fill" style="width:${{pct}}%;background:${{scoreColor(p.score)}}"></div></div>
    <span class="sc-txt">${{p.score}}/${{MAX}}</span>
  </div>`;

  const inds = `<div class="inds">
    ${{ind('📷', p.has_photo,         'Has profile photo')}}
    ${{ind('✏️', p.has_headline,      'Has headline')}}
    ${{ind('🔗', !p.slug_is_generic,  'Custom profile URL')}}
    ${{ind('🤝', p.mutual_level > 0,  MUTUAL_LABELS[Math.min(p.mutual_level,2)])}}
    ${{p.suspicious_name ? `<span class="ind" title="Suspicious name: ${{safeReason}}">⚠️</span>` : ''}}
  </div>`;

  const suspBadge = p.suspicious_name
    ? `<span class="badge badge-susp" title="${{safeReason}}">⚠️ name</span>` : '';

  const noteVal = escapeHtml(notes[p.profile_url] || '');

  return `<tr
    data-idx="${{idx}}"
    data-name="${{escapeHtml(p.name.toLowerCase())}}"
    data-hl="${{escapeHtml((p.headline||'').toLowerCase())}}"
    data-risk="${{p.risk}}"
    data-mutual="${{p.mutual_level}}"
    data-payroll="${{p.payroll_status||''}}">
    <td class="av-cell">${{av}}</td>
    <td><strong>${{safeName}}</strong>${{suspBadge}}</td>
    <td class="hl-cell" title="${{safeHeadline}}">${{safeHeadline || '<em style="color:var(--muted)">—</em>'}}</td>
    <td><span class="badge badge-${{p.risk}}">${{RISK_LABELS[p.risk]}}</span></td>
    <td>${{sc}}</td>
    <td>${{inds}}</td>
    ${{payrollCells(p)}}
    <td><input class="note-input" type="text" placeholder="Add note…" value="${{noteVal}}"></td>
    <td><a class="pl" href="${{safeUrl}}" target="_blank" rel="noopener">View &rarr;</a></td>
  </tr>`;
}}

const tbody = document.getElementById('tbody');
tbody.innerHTML = profiles.map(renderRow).join('');

// Delegated handler — avoids injecting URLs into inline onchange attributes,
// which would break for any profile URL containing quotes or other special
// characters.
tbody.addEventListener('input', (e) => {{
  if (!e.target.classList.contains('note-input')) return;
  const row = e.target.closest('tr');
  const idx = parseInt(row.dataset.idx, 10);
  const url = profiles[idx] && profiles[idx].profile_url;
  if (!url) return;
  const val = e.target.value;
  if (val) notes[url] = val; else delete notes[url];
  saveNotes();
}});

function applyFilters() {{
  const q       = document.getElementById('fSearch').value.toLowerCase();
  const risk    = document.getElementById('fRisk').value;
  const mutual  = document.getElementById('fMutual').value;
  const payroll = hasPayroll ? document.getElementById('fPayroll').value : '';
  let n = 0;
  tbody.querySelectorAll('tr').forEach(row => {{
    const ok = (!q      || row.dataset.name.includes(q) || row.dataset.hl.includes(q))
            && (!risk   || row.dataset.risk    === risk)
            && (!mutual || row.dataset.mutual  === mutual)
            && (!payroll|| row.dataset.payroll === payroll);
    row.style.display = ok ? '' : 'none';
    if (ok) n++;
  }});
  document.getElementById('fCount').textContent = n + ' profile' + (n!==1?'s':'') + ' shown';
  document.getElementById('noRes').style.display = n===0?'block':'none';
}}

['fSearch','fRisk','fMutual'].forEach(id => {{
  const el = document.getElementById(id);
  if (el) el.addEventListener('input', applyFilters);
}});
if (hasPayroll) {{
  const el = document.getElementById('fPayroll');
  if (el) el.addEventListener('change', applyFilters);
}}

function toggleHelp(tab, btn) {{
  const panel = document.getElementById('help-' + tab);
  const wasActive = panel && panel.classList.contains('active');

  // Close all panels and deactivate all tabs first
  document.querySelectorAll('.help-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.help-tab').forEach(t => t.classList.remove('active'));

  // If it wasn't active before, open it; otherwise leave it closed (toggle)
  if (!wasActive && panel) {{
    panel.classList.add('active');
    btn.classList.add('active');
  }}
}}

function exportNotes() {{
  const rows = [['name','profile_url','risk','score','note']];
  let withNotes = 0;
  profiles.forEach(p => {{
    const note = notes[p.profile_url] || '';
    if (note) withNotes++;
    rows.push([p.name, p.profile_url, p.risk, p.score, note]);
  }});
  const csv = rows.map(r => r.map(v => '"'+String(v).replace(/"/g,'""')+'"').join(',')).join('\\n');
  const a = document.createElement('a');
  a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent('\\uFEFF'+csv);
  a.download = 'headcheck_notes.csv';
  a.click();
  // Informational only — CSV contains every profile so HR can annotate offline.
  console.log('[HeadCheck] Exported ' + profiles.length + ' rows, ' + withNotes + ' with notes.');
}}
</script>
</body>
</html>"""

    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

