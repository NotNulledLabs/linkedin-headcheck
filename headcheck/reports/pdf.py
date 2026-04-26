"""
Executive PDF report.

Multi-page PDF grouped by risk bucket (red first, then yellow, then green),
with clickable profile URLs and a summary header. Generated with reportlab.
"""
from datetime import datetime

from ..constants import VERSION, BRAND_NAME, MAX_SCORE
from ..scoring import RISK_GREEN_MIN, RISK_YELLOW_MIN


def generate_pdf(profiles: list[dict], company: str, has_payroll: bool, out: str):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    W_PAGE = A4[0]
    W      = W_PAGE - 28*mm
    ts     = datetime.now().strftime("%B %d, %Y")
    total  = len(profiles)
    green  = sum(1 for p in profiles if p["risk"] == "green")
    yellow = sum(1 for p in profiles if p["risk"] == "yellow")
    red    = sum(1 for p in profiles if p["risk"] == "red")

    C_WHITE  = colors.white
    C_BG     = colors.HexColor("#F2F4F8")
    C_SURF   = colors.HexColor("#F8FAFD")
    C_BORDER = colors.HexColor("#D9DEE9")
    C_TEXT   = colors.HexColor("#111827")
    C_MUTED  = colors.HexColor("#4B5563")
    C_BLUE   = colors.HexColor("#1D4ED8")
    C_BLUEDK = colors.HexColor("#1E3A8A")
    C_GREEN  = colors.HexColor("#166534")
    C_AMBER  = colors.HexColor("#92400E")
    C_RED    = colors.HexColor("#991B1B")

    def ps(name, **kw): return ParagraphStyle(name, **kw)

    s_label = ps("lbl",  fontSize=8,  fontName="Helvetica-Bold",    textColor=C_WHITE,  leading=11)
    s_title = ps("ttl",  fontSize=19, fontName="Helvetica-Bold",    textColor=C_TEXT,   leading=23, spaceAfter=3)
    s_co    = ps("co",   fontSize=12, fontName="Helvetica-Bold",    textColor=C_BLUE,   leading=15, spaceAfter=2)
    s_meta  = ps("meta", fontSize=8,  fontName="Helvetica",         textColor=C_MUTED,  leading=12, spaceAfter=2)
    s_h2    = ps("h2",   fontSize=11, fontName="Helvetica-Bold",    textColor=C_TEXT,   leading=14, spaceBefore=10, spaceAfter=5)
    s_small = ps("sm",   fontSize=7,  fontName="Helvetica",         textColor=C_MUTED,  leading=10)
    s_disc  = ps("dc",   fontSize=7,  fontName="Helvetica-Oblique", textColor=C_MUTED,  leading=10)

    def hr(sp=4): return HRFlowable(width="100%", thickness=0.5, color=C_BORDER, spaceAfter=sp, spaceBefore=sp)

    doc = SimpleDocTemplate(out, pagesize=A4,
        leftMargin=14*mm, rightMargin=14*mm,
        topMargin=14*mm, bottomMargin=16*mm)

    story = []

    # Header band
    hdr = Table([[Paragraph(f"LinkedIn HeadCheck  ·  Security & Workforce Verification  ·  v{VERSION}", s_label)]],
                colWidths=[W])
    hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), C_BLUEDK),
        ("TOPPADDING",    (0,0),(-1,-1), 9),
        ("BOTTOMPADDING", (0,0),(-1,-1), 9),
        ("LEFTPADDING",   (0,0),(-1,-1), 12),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("People Audit Report", s_title))
    story.append(Paragraph(company, s_co))
    story.append(Paragraph(f"Generated {ts}  ·  {total} profiles analysed", s_meta))
    story.append(Spacer(1, 3*mm))
    story.append(hr())

    # KPIs
    story.append(Paragraph("Summary", s_h2))

    def kv(val, lbl, color):
        """Return (value_paragraph, label_paragraph) for a KPI cell."""
        return (
            Paragraph(str(val), ps(f"kv{lbl}", fontSize=20, fontName="Helvetica-Bold", textColor=color, leading=22)),
            Paragraph(lbl,      ps(f"kl{lbl}", fontSize=7,  fontName="Helvetica",      textColor=C_MUTED, leading=10)),
        )

    def kpi_table(cells, col_count):
        """Build a two-row KPI table (values on top, labels below) from kv() tuples."""
        values = [c[0] for c in cells]
        labels = [c[1] for c in cells]
        t = Table([values, labels], colWidths=[W/col_count]*col_count)
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), C_SURF),
            ("ALIGN",         (0,0),(-1,-1), "CENTER"),
            ("TOPPADDING",    (0,0),(-1,-1), 10),
            ("BOTTOMPADDING", (0,0),(-1,-1), 8),
            ("LINEBEFORE",    (1,0),(-1,-1), 0.5, C_BORDER),
            ("LINEBELOW",     (0,0),(-1,0),  0.5, C_BORDER),
            ("BOX",           (0,0),(-1,-1), 0.5, C_BORDER),
        ]))
        return t

    story.append(kpi_table([
        kv(total,  "Total profiles", C_BLUE),
        kv(green,  "Low risk",       C_GREEN),
        kv(yellow, "Needs review",   C_AMBER),
        kv(red,    "High risk",      C_RED),
    ], col_count=4))
    story.append(Spacer(1, 3*mm))

    if has_payroll:
        exact     = sum(1 for p in profiles if p.get("payroll_status") == "exact")
        fuzzy_n   = sum(1 for p in profiles if p.get("payroll_status") == "fuzzy")
        not_found = sum(1 for p in profiles if p.get("payroll_status") == "not_found")
        story.append(Paragraph("Payroll Cross-Reference", s_h2))
        story.append(kpi_table([
            kv(exact,     "In payroll",     C_GREEN),
            kv(fuzzy_n,   "Similar name",   C_AMBER),
            kv(not_found, "Not in payroll", C_RED),
        ], col_count=3))
        story.append(Spacer(1, 3*mm))

    story.append(hr())

    # Risk explanation
    story.append(Paragraph("Risk Classification", s_h2))
    for lbl, color, desc in [
        (f"Low risk (score >= {RISK_GREEN_MIN})",                 C_GREEN, "Complete, active profile. Has photo, custom URL, headline, and/or mutual connections."),
        (f"Needs review (score {RISK_YELLOW_MIN}-{RISK_GREEN_MIN-1})",  C_AMBER, "Partial profile. Some signals present but missing key indicators. Manual verification recommended."),
        (f"High risk (score <= {RISK_YELLOW_MIN-1})",              C_RED,   "Ghost or minimal profile, or profile with no photo. Priority for HR investigation."),
    ]:
        story.append(Paragraph(f"<b>{lbl}</b>",
            ps(f"rh{lbl[:3]}", fontSize=9, fontName="Helvetica-Bold", textColor=color, leading=12, spaceBefore=4, spaceAfter=1)))
        story.append(Paragraph(desc, s_small))

    story.append(Spacer(1, 3*mm))
    story.append(hr())

    # Profile tables grouped by risk
    for risk_key, risk_color, section_title in [
        ("red",    C_RED,   "High Risk — Priority Review"),
        ("yellow", C_AMBER, "Needs Review"),
        ("green",  C_GREEN, "Low Risk"),
    ]:
        subset = [p for p in profiles if p["risk"] == risk_key]
        if not subset:
            continue

        story.append(Paragraph(f"{section_title}  ({len(subset)} profiles)", s_h2))

        if has_payroll:
            col_hdrs = ["Name", "Headline", "Profile URL", "Score", "Signals", "Payroll", "Match"]
            col_w    = [W*.18, W*.22, W*.20, W*.08, W*.12, W*.10, W*.10]
        else:
            col_hdrs = ["Name", "Headline", "Profile URL", "Score", "Signals"]
            col_w    = [W*.22, W*.28, W*.28, W*.10, W*.12]

        def th(t): return Paragraph(t, ps(f"th{t[:4]}", fontSize=7, fontName="Helvetica-Bold", textColor=C_MUTED))
        def td(t, bold=False, color=C_TEXT, size=8):
            fn = "Helvetica-Bold" if bold else "Helvetica"
            return Paragraph(str(t), ps(f"td{str(t)[:4]}", fontSize=size, fontName=fn, textColor=color, leading=11))

        rows = [[th(h) for h in col_hdrs]]

        for p in subset:
            sigs, miss = [], []
            # Photo signal — three states. PHOTO_NOT_LOADED is unknown
            # (lazy-load), neither a positive signal nor a red flag.
            photo_state = p.get("photo_state",
                                "loaded" if p.get("has_photo") else "absent")
            if photo_state == "loaded":
                sigs.append("Photo")
            elif photo_state == "not_loaded":
                miss.append("photo not loaded at export")
            else:
                miss.append("NO PHOTO")
            if p["has_headline"]:        sigs.append("Title")
            else:                        miss.append("no title")
            if not p["slug_is_generic"]: sigs.append("Custom URL")
            else:                        miss.append("generic URL")
            if p["mutual_level"] == 1:   sigs.append("1 mutual")
            elif p["mutual_level"] >= 2: sigs.append("Multi mutual")
            else:                        miss.append("no mutual")
            if p["suspicious_name"]:     miss.append(f"susp name ({p['suspicious_reason']})")

            sig_txt = (", ".join(sigs) if sigs else "—") + ("\nMissing: " + ", ".join(miss) if miss else "")
            url_short = p["profile_url"].replace("https://www.linkedin.com/in/", "li/in/")

            row = [
                td(p["name"], bold=True),
                td((p["headline"][:65] + "…" if len(p.get("headline","")) > 65 else p.get("headline","")) or "—", color=C_MUTED, size=7),
                Paragraph(f'<link href="{p["profile_url"]}">{url_short}</link>',
                    ps("url", fontSize=7, fontName="Helvetica", textColor=C_BLUE, leading=10)),
                td(f"{p['score']}/{MAX_SCORE}", bold=True, color=risk_color),
                Paragraph(sig_txt, ps("sig", fontSize=7, fontName="Helvetica", textColor=C_TEXT, leading=10)),
            ]
            if has_payroll:
                ps_val = p.get("payroll_status","not_found")
                ps_colors = {"exact":C_GREEN,"fuzzy":C_AMBER,"not_found":C_RED}
                ps_labels = {"exact":"In payroll","fuzzy":"Similar","not_found":"Not found"}
                row.append(td(ps_labels.get(ps_val,"—"), color=ps_colors.get(ps_val,C_MUTED), size=7))
                row.append(td((p.get("payroll_match") or "—")[:22], color=C_MUTED, size=7))

            rows.append(row)

        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        row_styles = [
            ("BACKGROUND",    (0,0),(-1,0),  C_SURF),
            ("LINEBELOW",     (0,0),(-1,0),  1.0, risk_color),
            ("LINEBELOW",     (0,1),(-1,-1), 0.3, C_BORDER),
            ("BOX",           (0,0),(-1,-1), 0.5, C_BORDER),
            ("TOPPADDING",    (0,0),(-1,-1), 5),
            ("BOTTOMPADDING", (0,0),(-1,-1), 5),
            ("LEFTPADDING",   (0,0),(-1,-1), 7),
            ("RIGHTPADDING",  (0,0),(-1,-1), 7),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ]
        for i in range(1, len(rows)):
            if i % 2 == 0:
                row_styles.append(("BACKGROUND",(0,i),(-1,i), C_BG))
        tbl.setStyle(TableStyle(row_styles))
        story.append(tbl)
        story.append(Spacer(1, 4*mm))

    story.append(hr())

    # ── NEXT STEPS SECTION ────────────────────────────────────────────────────
    story.append(Paragraph("What to Do After the Audit", s_h2))
    story.append(Paragraph(
        "Once HR has identified suspicious profiles, the following actions are available.",
        ps("ns_intro", fontSize=9, fontName="Helvetica", textColor=C_TEXT, leading=13, spaceAfter=6)
    ))

    # Case 1
    story.append(Paragraph(
        "Former employee who forgot to update their profile",
        ps("ns_h", fontSize=9, fontName="Helvetica-Bold", textColor=C_GREEN, leading=12, spaceBefore=6, spaceAfter=2)
    ))
    story.append(Paragraph(
        "The most common case. Contact the person directly and ask them to edit the Experience section "
        "on their LinkedIn profile and remove or update the position. LinkedIn will automatically "
        "disassociate their profile from the company page. Changes can take up to 30 days to reflect.",
        ps("ns_b", fontSize=8, fontName="Helvetica", textColor=C_TEXT, leading=12, spaceAfter=4)
    ))

    # Case 2
    story.append(Paragraph(
        "Fake or malicious profile",
        ps("ns_h2", fontSize=9, fontName="Helvetica-Bold", textColor=C_RED, leading=12, spaceBefore=4, spaceAfter=2)
    ))
    for step_title, step_body in [
        ("Step 1 — Report to LinkedIn via support form",
         "Page admins cannot remove members directly — only the member can edit their own profile. "
         "Contact LinkedIn providing: the person's full name, a screenshot of the People page showing them, "
         "a link to their profile, and an explanation of why the association is incorrect. "
         "Submit at: linkedin.com/help/linkedin/ask/cp-master "
         "(a confirmed company email address is required)."),
        ("Step 2 — Report the individual profile",
         "On the person's LinkedIn profile, click the More button (···) → Report / Block → "
         "select the appropriate reason (fake profile, incorrect information). "
         "LinkedIn will review and may remove the profile or the company association."),
        ("Step 3 — Escalate if there is no response",
         "If LinkedIn support does not respond within a reasonable time, "
         "contacting @LinkedInHelp on X/Twitter can help speed up the process for clear-cut cases."),
    ]:
        story.append(Paragraph(
            f"<b>{step_title}</b>",
            ps(f"st_{step_title[:4]}", fontSize=8, fontName="Helvetica-Bold", textColor=C_TEXT, leading=12, spaceBefore=3, spaceAfter=1)
        ))
        story.append(Paragraph(
            step_body,
            ps(f"sb_{step_title[:4]}", fontSize=8, fontName="Helvetica", textColor=C_MUTED, leading=12, spaceAfter=3)
        ))

    # What admins cannot do — red-tinted box
    cannot_data = [[Paragraph(
        "<b>What admins cannot do</b>  —  Admins cannot directly remove a member from the company page, "
        "cannot see a full list of associated members in the admin dashboard, and cannot prevent someone "
        "from self-associating with the company. LinkedIn's system relies entirely on self-reported data — "
        "which is exactly why this tool exists.",
        ps("cannot", fontSize=7, fontName="Helvetica", textColor=C_RED, leading=11)
    )]]
    cannot_tbl = Table(cannot_data, colWidths=[W])
    cannot_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#FEF2F2")),
        ("LINEBELOW",     (0,0), (-1,-1), 0, C_BORDER),
        ("LINEBEFORE",    (0,0), (0,-1),  2, C_RED),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
    ]))
    story.append(Spacer(1, 3*mm))
    story.append(cannot_tbl)
    story.append(Spacer(1, 4*mm))

    story.append(hr())
    story.append(Paragraph(
        "Disclaimer: This report was generated automatically from publicly visible LinkedIn profile data. "
        "Risk scores reflect profile completeness only and do not confirm or deny current employment. "
        "All findings must be verified by HR against internal records before any action is taken. "
        "Handle as a confidential internal HR document.",
        s_disc))

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(C_MUTED)
        canvas.drawString(14*mm, 9*mm, f"LinkedIn HeadCheck  ·  {BRAND_NAME}  ·  {company}  ·  {ts}")
        canvas.drawRightString(W_PAGE - 14*mm, 9*mm, f"Page {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
