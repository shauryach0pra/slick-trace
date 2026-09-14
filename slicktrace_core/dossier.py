"""
Render the investigation report as a PDF.

The same content the JSON and Markdown reports carry, in the form an analyst
actually files: one document, paginated, with the checksums on it. Nothing here
computes anything - if a number is not already in `investigation_report.json`
it does not appear, so the PDF cannot drift from the artifact it renders.

ON THE FRAMING, WHICH IS THE POINT
    Two repositories in this problem statement's public field describe their
    PDF export as a court-ready dossier, one of them citing UNCLOS articles
    beside the vessel name. A PDF is a file format. It does not confer legal
    standing, and a document that looks like a charge sheet invites being read
    as one.

    This one states what it is not on the first page, before any vessel is
    named, and repeats the uncertainty statement on the last. The checksums
    verify that the files have not changed since the run; they say nothing
    about whether the analysis is right.
"""
from __future__ import annotations

import json
import os

TITLE = "Slick Trace investigation report"


def _require_reportlab():
    try:
        from reportlab.lib import colors  # noqa: F401
        from reportlab.platypus import SimpleDocTemplate  # noqa: F401
        return True
    except ImportError as exc:
        raise RuntimeError(
            "reportlab is not installed. Install it to render PDF dossiers:\n"
            "    pip install reportlab"
        ) from exc


def build_dossier(case_dir: str, out_path: str | None = None) -> str:
    """Render `investigation_report.json` from `case_dir` to a PDF."""
    _require_reportlab()
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    src = os.path.join(case_dir, "investigation_report.json")
    with open(src) as fh:
        rep = json.load(fh)
    out_path = out_path or os.path.join(case_dir, "investigation_dossier.pdf")

    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=9, leading=12.5,
                          alignment=TA_LEFT, spaceAfter=6)
    small = ParagraphStyle("small", parent=body, fontSize=7.6, leading=10.5,
                           textColor=colors.HexColor("#555555"))
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=15, spaceAfter=8,
                        textColor=colors.HexColor("#0b3d5c"))
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=10.5, spaceBefore=10,
                        spaceAfter=4, textColor=colors.HexColor("#12506f"))
    warn = ParagraphStyle("warn", parent=body, fontSize=8.6, leading=12,
                          backColor=colors.HexColor("#fdf3e3"),
                          borderColor=colors.HexColor("#d9a441"), borderWidth=0.6,
                          borderPadding=6, spaceAfter=10)

    def table(rows, widths):
        t = Table(rows, colWidths=widths, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b3d5c")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f4f7f9")]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cfd8de")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return t

    story = []
    story.append(Paragraph(f"{TITLE} — {rep['incident_id']}", h1))
    story.append(Paragraph(f"Generated {rep.get('generated_utc', '—')} · "
                           f"{rep.get('report_type', '')}", small))
    story.append(Spacer(1, 4 * mm))

    # What this is not, before any vessel is named.
    story.append(Paragraph(f"<b>What this document is not.</b> {rep.get('not_a', '')}",
                           warn))

    attr = rep.get("attribution") or {}
    scene = rep.get("scene") or {}

    story.append(Paragraph("Finding", h2))
    if attr.get("outcome") == "unknown_source":
        story.append(Paragraph(
            "<b>No vessel in this scene can account for the observed slick.</b> "
            "No candidate release reproduced the observation above the absolute "
            "fit gate. The system returns no name rather than the least-bad one; "
            "a source vessel may have left the scene before acquisition.", body))
    else:
        story.append(Paragraph(
            f"<b>Leading candidate: {attr.get('top_candidate', '—')}</b>. "
            "This is a ranking by physical consistency under tested assumptions — "
            "an investigative lead for a human analyst, not proof of responsibility.",
            body))

    story.append(Paragraph("Scene", h2))
    story.append(table([
        ["Field", "Value"],
        ["Incident", rep["incident_id"]],
        ["Acquired (UTC)", str(scene.get("acquired_utc", "—"))],
        ["Sensor", str(scene.get("sensor", "—"))],
        ["Data status", str(scene.get("data_status", "—"))],
        ["Pixel spacing", f"{scene.get('pixel_spacing_m', '—')} m"],
        ["Label source", str(scene.get("label_source", "—"))],
    ], [45 * mm, 115 * mm]))

    ev = rep.get("evidence_layers") or {}
    story.append(Paragraph("Evidence layers", h2))
    story.append(table([
        ["Layer", "Provenance"],
        ["AIS", str(ev.get("ais_source", "—"))],
        ["Forcing", str(ev.get("forcing_product", "—"))],
        ["Licence", str(ev.get("data_licence", "—"))],
    ], [30 * mm, 130 * mm]))

    hf = rep.get("historical_filtering") or {}
    counts = hf.get("status_counts") or {}
    if counts:
        story.append(Paragraph("Traffic filtering", h2))
        story.append(table(
            [["State", "Vessels"]] + [[k, str(v)] for k, v in counts.items()],
            [45 * mm, 25 * mm]))
        story.append(Paragraph(
            "Unassessed is reported separately from excluded: missing evidence is not "
            "exoneration, and collapsing the two would silently convert one into the "
            "other.", small))

    frag = rep.get("rank_fragility") or {}
    if frag:
        story.append(Paragraph("Rank fragility", h2))
        flipped = frag.get("flip_found")
        story.append(Paragraph(
            f"Leader retained in {frag.get('lead_retained_fraction', '—')} of "
            f"{frag.get('n_points_tested', '—')} tested perturbations. "
            + ("A tested perturbation changed the leader; the smallest is recorded in "
               "the JSON report." if flipped else
               "No tested perturbation changed the leader."), body))
        story.append(Paragraph(
            "Absence of a flip is evidence of stability across the tested set, not a "
            "proof of stability: single-axis and two-axis perturbations only.", small))

    story.append(PageBreak())

    story.append(Paragraph("File integrity", h2))
    sums = rep.get("checksums_sha256") or {}
    if sums:
        story.append(table(
            [["File", "SHA-256 (first 16)"]]
            + [[k, str(v)[:16]] for k, v in sorted(sums.items())],
            [95 * mm, 45 * mm]))
    story.append(Paragraph(rep.get("checksum_note", ""), small))

    story.append(Paragraph("Uncertainty", h2))
    unc = rep.get("uncertainty_statement")
    if isinstance(unc, list):
        for line in unc:
            story.append(Paragraph(f"• {line}", body))
    elif unc:
        story.append(Paragraph(str(unc), body))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"<b>Restated.</b> {rep.get('not_a', '')}", warn))

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(20 * mm, 12 * mm,
                          f"{rep['incident_id']} · investigative lead, not proof of "
                          f"responsibility")
        canvas.drawRightString(190 * mm, 12 * mm, f"page {doc.page}")
        canvas.restoreState()

    SimpleDocTemplate(out_path, pagesize=A4,
                      leftMargin=20 * mm, rightMargin=20 * mm,
                      topMargin=18 * mm, bottomMargin=20 * mm,
                      title=f"{TITLE} — {rep['incident_id']}",
                      author="Slick Trace").build(
        story, onFirstPage=_footer, onLaterPages=_footer)
    return out_path
