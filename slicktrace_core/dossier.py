"""
Render the investigation report as a PDF.

The same content the JSON and Markdown reports carry, in the form an analyst
actually files: one document, paginated, with the checksums on it. Nothing here
computes anything - if a number is not already in `investigation_report.json`
it does not appear, so the PDF cannot drift from the artifact it renders. (The
only other input is the case's own `scene.png`, one of the checksummed files.)

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

ON THE DESIGN
    Quiet and typographic: one typeface in a few weights, near-black text and
    two greys, a single accent colour for the answer, hairlines instead of boxes,
    large figures, generous white space.
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
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.platypus import (CondPageBreak, Flowable, Image, KeepTogether, PageBreak,
                                    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

    src = os.path.join(case_dir, "investigation_report.json")
    with open(src) as fh:
        rep = json.load(fh)
    out_path = out_path or os.path.join(case_dir, "investigation_dossier.pdf")

    # ---- palette and type -------------------------------------------------------------------
    INK, SEC, TER = colors.HexColor("#1d1d1f"), colors.HexColor("#6e6e73"), colors.HexColor("#86868b")
    HAIR, FILL = colors.HexColor("#d2d2d7"), colors.HexColor("#f5f5f7")
    ACCENT, AMBER, AMBER_FILL = colors.HexColor("#0071e3"), colors.HexColor("#b25e00"), colors.HexColor("#ff9500")
    GREEN = colors.HexColor("#248a3d")
    W, H = A4
    LM = RM = 22 * mm
    CW = W - LM - RM                                   # content width

    def style(name, size, leading=None, font="Helvetica", color=INK, **kw):
        return ParagraphStyle(name, fontName=font, fontSize=size, leading=leading or size * 1.38,
                              textColor=color, alignment=TA_LEFT, **kw)

    body = style("body", 9.2, 13.6, color=INK)
    sec = style("sec", 9.2, 13.6, color=SEC)
    small = style("small", 7.8, 11.2, color=SEC)
    eyebrow = style("eyebrow", 7.4, 9, "Helvetica-Bold", TER)
    h2 = style("h2", 15, 19, "Helvetica-Bold", INK, spaceBefore=4, spaceAfter=2)
    headline = style("headline", 23, 28, "Helvetica-Bold", INK)
    kv_k = style("kvk", 8.4, 12, color=SEC)
    kv_v = style("kvv", 8.4, 12, color=INK)
    mono = style("mono", 7, 10, "Courier", SEC)

    def P(text, st=body):
        return Paragraph(text, st)

    def esc(v):
        return (str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    def pct(x, digits=0):
        return "—" if x is None else f"{x * 100:.{digits}f}%"

    def when(ts):
        # "2026-09-10T04:30:00+00:00" -> "10 Sep 2026, 04:30 UTC" (formatting only)
        try:
            from datetime import datetime
            d = datetime.fromisoformat(str(ts))
            return d.strftime("%-d %b %Y, %H:%M UTC")
        except Exception:
            return str(ts)

    # ---- drawn elements ---------------------------------------------------------------------
    class Gauge(Flowable):
        """The fit gauge: a 270-degree ring filled to the mean IoU, the gate marked."""
        def __init__(self, value, gate, tone, size=30 * mm):
            super().__init__(); self.v, self.g, self.tone, self.s = value, gate, tone, size
        def wrap(self, *a): return self.s, self.s
        def draw(self):
            c, s = self.canv, self.s
            cx = cy = s / 2; r = s * 0.40; lw = s * 0.075
            c.setLineCap(1); c.setLineWidth(lw)
            c.setStrokeColor(colors.HexColor("#e8e8ed"))
            c.arc(cx - r, cy - r, cx + r, cy + r, -45, 270)
            if self.v is not None:
                c.setStrokeColor(self.tone)
                c.arc(cx - r, cy - r, cx + r, cy + r, 225, -270 * max(0.004, min(1, self.v)))
            if self.g is not None:
                import math
                a = math.radians(225 - 270 * self.g)
                c.setLineWidth(1.2); c.setStrokeColor(AMBER_FILL)
                c.line(cx + (r - lw * 0.9) * math.cos(a), cy + (r - lw * 0.9) * math.sin(a),
                       cx + (r + lw * 0.9) * math.cos(a), cy + (r + lw * 0.9) * math.sin(a))
            c.setFillColor(INK); c.setFont("Helvetica-Bold", s * 0.2)
            c.drawCentredString(cx, cy - s * 0.02, "—" if self.v is None else f"{self.v:.2f}")
            c.setFillColor(TER); c.setFont("Helvetica", s * 0.075)
            c.drawCentredString(cx, cy - s * 0.15, "MEAN IoU")

    class Symbol(Flowable):
        """A small filled circle with a check, a cross or a caution mark."""
        def __init__(self, kind, d=4.6 * mm):
            super().__init__(); self.kind, self.d = kind, d
        def wrap(self, *a): return self.d, self.d
        def draw(self):
            c, d = self.canv, self.d
            fill = {"for": ACCENT, "against": AMBER_FILL, "caution": AMBER_FILL, "neutral": TER}[self.kind]
            c.setFillColor(fill); c.circle(d / 2, d / 2, d / 2, stroke=0, fill=1)
            c.setStrokeColor(colors.white); c.setLineWidth(1.1); c.setLineCap(1); c.setLineJoin(1)
            if self.kind == "for":
                p = c.beginPath(); p.moveTo(d * 0.28, d * 0.52); p.lineTo(d * 0.44, d * 0.36); p.lineTo(d * 0.72, d * 0.66)
                c.drawPath(p, stroke=1, fill=0)
            elif self.kind in ("against", "neutral"):
                c.line(d * 0.33, d * 0.33, d * 0.67, d * 0.67); c.line(d * 0.67, d * 0.33, d * 0.33, d * 0.67)
            else:
                c.line(d / 2, d * 0.62, d / 2, d * 0.40); c.circle(d / 2, d * 0.28, 0.35, stroke=1, fill=0)

    class Bar(Flowable):
        """A thin rounded bar filled to a fraction, for a value in [0, 1]."""
        def __init__(self, frac, tone, w=34 * mm, h=2.2 * mm):
            super().__init__(); self.f, self.tone, self.w, self.h = frac, tone, w, h
        def wrap(self, *a): return self.w, self.h
        def draw(self):
            c = self.canv
            c.setFillColor(colors.HexColor("#e8e8ed")); c.roundRect(0, 0, self.w, self.h, self.h / 2, stroke=0, fill=1)
            f = max(0.0, min(1.0, self.f or 0))
            if f > 0:
                c.setFillColor(self.tone); c.roundRect(0, 0, max(self.h, self.w * f), self.h, self.h / 2, stroke=0, fill=1)

    class Note(Flowable):
        """A soft grey panel with a coloured dot - for what this document is not."""
        def __init__(self, text, dot=AMBER_FILL, width=CW):
            super().__init__(); self.p = Paragraph(text, style("note", 8.6, 12.8, color=INK)); self.dot, self.w = dot, width
        def wrap(self, aw, ah):
            _, ph = self.p.wrap(self.w - 13 * mm, ah); self.h = ph + 7 * mm; return self.w, self.h
        def draw(self):
            c = self.canv
            c.setFillColor(FILL); c.roundRect(0, 0, self.w, self.h, 3.2 * mm, stroke=0, fill=1)
            c.setFillColor(self.dot); c.circle(6 * mm, self.h - 5.3 * mm, 1.2 * mm, stroke=0, fill=1)
            self.p.drawOn(c, 10 * mm, 3.5 * mm)

    def hairline_table(rows, widths, head=False, pad=5, valign="MIDDLE", extra=()):
        t = Table(rows, colWidths=widths, hAlign="LEFT", repeatRows=1 if head else 0)
        st = [("VALIGN", (0, 0), (-1, -1), valign), ("LEFTPADDING", (0, 0), (-1, -1), 0),
              ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), pad),
              ("BOTTOMPADDING", (0, 0), (-1, -1), pad), ("LINEBELOW", (0, 0), (-1, -2), 0.4, HAIR)]
        if head:
            st += [("LINEBELOW", (0, 0), (-1, 0), 0.6, INK)]
        t.setStyle(TableStyle(st + list(extra)))
        return t

    def kv(rows, kw=40 * mm):
        return hairline_table([[P(esc(k), kv_k), P(v if isinstance(v, str) and v.startswith("<") else esc(v), kv_v)] for k, v in rows],
                              [kw, CW - kw], pad=4)

    def section(title, lead=None):
        out = [Spacer(1, 7 * mm), P(esc(title), h2)]
        if lead:
            out += [Spacer(1, 1 * mm), P(esc(lead), sec)]
        out.append(Spacer(1, 3.5 * mm))
        return out

    # ---- the report's fields ------------------------------------------------------------------
    attr = rep.get("attribution") or {}
    scene = rep.get("scene") or {}
    ranking = attr.get("ranking") or []
    top = ranking[0] if ranking else {}
    runner = ranking[1] if len(ranking) > 1 else None
    unknown = attr.get("outcome") == "unknown_source"
    gate = attr.get("abstention_iou_gate")
    base = (attr.get("baseline_comparison") or {})
    nearest = (base.get("ranking") or [{}])[0]
    frag = rep.get("rank_fragility") or {}
    nxt = rep.get("next_observation") or {}
    loss_gap = (nxt.get("current_ambiguity") or {}).get("mean_loss_gap") if nxt.get("applicable") else None
    hf = rep.get("historical_filtering") or {}
    first_entry = next((a.get("first_entry_hours_before") for a in hf.get("assessments", [])
                        if a.get("vessel_key") == top.get("vessel_key")), None)
    tone = AMBER_FILL if unknown else ACCENT
    iid = rep["incident_id"]

    story = []

    # ============ page 1: the finding =====================================================
    story.append(Spacer(1, 2 * mm))
    story.append(Note(f"<b>What this document is not.</b> {esc(rep.get('not_a', ''))}"))
    story.append(Spacer(1, 9 * mm))
    story.append(P("FINDING", eyebrow))
    story.append(Spacer(1, 2.5 * mm))
    if unknown:
        head = f'<font color="{AMBER.hexval()[2:] and "#b25e00"}">No vessel</font> fits the slick well enough to be named.'
        sub = (f"Forward replay tested {len(ranking)} candidates. None recreates the observed slick above the fit gate, "
               "so the system returns no name rather than the least-bad one; the source may not be in the data.")
    else:
        head = f'<font color="#0071e3">{esc(attr.get("top_candidate", "—"))}</font> is the best physical fit.'
        sub = (f"Forward replay tested {len(ranking)} candidates" + (f"; the runner-up fits at {runner['mean_iou']:.2f}." if runner else ".")
               + " A ranking by physical consistency under tested assumptions — an investigative lead for a human analyst.")
    hero = Table([[[P(head, headline), Spacer(1, 3 * mm), P(esc(sub), sec)], Gauge(top.get("mean_iou"), gate, tone)]],
                 colWidths=[CW - 36 * mm, 36 * mm], hAlign="LEFT")
    hero.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    story.append(hero)
    story.append(Spacer(1, 8 * mm))

    # the key figures, as a strip of large numbers between two hairlines
    def figure(label, value, note):
        return [P(esc(label).upper(), eyebrow), Spacer(1, 1.6 * mm), P(value, style("fig", 19, 22, "Helvetica-Bold", INK)),
                Spacer(1, 1 * mm), P(esc(note), small)]
    figs_abstain = [figure("Best fit", f"{top.get('mean_iou', 0):.2f}" if top else "—", "mean IoU of the best replay"),
                    figure("Fit gate", str(gate), "needed to name a vessel"),
                    figure("Next best", f"{runner['mean_iou']:.2f}" if runner else "—", "mean IoU of the runner-up"),
                    figure("Candidates", str(len(ranking)), "replayed by forward replay")]
    figs = [figure("Mean IoU", f"{top.get('mean_iou', 0):.2f}" if top else "—", f"the fit gate is {gate}"),
            figure("Variants won", f"{top.get('ensemble_win_count', '—')}<font size=11 color='#86868b'> / {top.get('n_ensemble', '—')}</font>",
                   "forcing variants where it fits best"),
            figure("Lead retained", pct(frag.get("lead_retained_fraction")) if frag.get("testable") else "—",
                   f"of {frag.get('n_points_tested', '—')} tested changes"),
            figure("Candidates", str(len(ranking)), "replayed by forward replay")]
    # an abstention shows the figures behind the decision, not a leader's support
    strip = Table([figs_abstain if unknown else figs], colWidths=[CW / 4] * 4, hAlign="LEFT")
    strip.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("LEFTPADDING", (1, 0), (-1, 0), 5 * mm), ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm), ("LINEABOVE", (0, 0), (-1, 0), 0.6, INK),
                               ("LINEBELOW", (0, 0), (-1, 0), 0.4, HAIR), ("LINEBEFORE", (1, 0), (-1, 0), 0.4, HAIR)]))
    story.append(strip)
    story.append(Spacer(1, 8 * mm))

    # the evidence, each a short fact led by a symbol, two by two
    rows = []
    if unknown:
        rows.append(("caution", f"The best fit reaches <b>{top.get('mean_iou', 0):.2f}</b>, below the <b>{gate}</b> gate"))
        rows.append(("caution", f"None of the <b>{len(ranking)}</b> replayed candidates recreates the slick well enough"))
        if runner: rows.append(("caution", f"The next-best candidate fits at only <b>{runner['mean_iou']:.2f}</b>"))
        if nearest.get("vessel_key"):
            rows.append(("neutral", f"The nearest vessel, <b>{esc(nearest['vessel_key'])}</b>, {nearest.get('distance_deg', 0):.4f}° away, is not named either"))
    else:
        rows.append(("for", f"Best fit under <b>{top.get('ensemble_win_count')} of {top.get('n_ensemble')}</b> forcing variants"))
        if loss_gap is not None:
            rows.append(("for", f"Ahead of the runner-up by a mean loss gap of <b>{loss_gap}</b>"))
        if first_entry is not None:
            rows.append(("for", f"Inside the origin area <b>{first_entry:g} h</b> before the image"))
        if nearest.get("vessel_key"):
            if nearest["vessel_key"] != attr.get("top_candidate"):
                rows.append(("against", f"The nearest vessel, <b>{esc(nearest['vessel_key'])}</b>, {nearest.get('distance_deg', 0):.4f}° away, is not supported"))
            else:
                rows.append(("for", "It is also the vessel nearest the slick"))
    cells = [[Symbol(k), P(t, body)] for k, t in rows]
    grid, half = [], (CW - 8 * mm) / 2
    for i in range(0, len(cells), 2):
        pair = cells[i:i + 2] + ([["", ""]] if len(cells[i:i + 2]) == 1 else [])
        grid.append([x for cell in pair for x in cell])
    ev = Table(grid, colWidths=[7 * mm, half - 7 * mm, 7 * mm + 8 * mm, half - 7 * mm], hAlign="LEFT")
    ev.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("LEFTPADDING", (2, 0), (2, -1), 8 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.append(P("EVIDENCE", eyebrow)); story.append(Spacer(1, 3 * mm)); story.append(ev)

    story += section("Candidates, ranked by physical fit",
                     "Each candidate's release replayed forward under six forcing variants and compared with the observed slick.")
    head_st = style("th", 7.4, 9, "Helvetica-Bold", TER)
    trs = [[P("#", head_st), P("VESSEL", head_st), P("MEAN IoU", head_st), "", P("VARIANTS WON", head_st), P("RELEASE STARTS", head_st)]]
    for i, r in enumerate(ranking):
        lead_row = i == 0 and not unknown
        vst = style(f"v{i}", 9, 12, "Helvetica-Bold" if lead_row else "Helvetica", ACCENT if lead_row else INK)
        trs.append([P(str(i + 1), sec), P(esc(r.get("vessel_key", "")), vst),
                    Bar(r.get("mean_iou"), ACCENT if lead_row else (AMBER_FILL if unknown and i == 0 else colors.HexColor("#8e8e93"))),
                    P(f"{r.get('mean_iou', 0):.3f}", body), P(f"{r.get('ensemble_win_count', 0)} of {r.get('n_ensemble', 0)}", body),
                    P(when(r.get("release_start")), sec)])
    story.append(hairline_table(trs, [8 * mm, 30 * mm, 38 * mm, 16 * mm, 26 * mm, CW - 118 * mm], head=True, pad=5))
    if nearest.get("vessel_key"):
        rank_of = next((i + 1 for i, r in enumerate(ranking) if r.get("vessel_key") == nearest["vessel_key"]), None)
        story.append(Spacer(1, 3 * mm))
        story.append(P(f"The proximity baseline — the vessel nearest the slick when the image was taken — would pick "
                       f"<b>{esc(nearest['vessel_key'])}</b>" + (f", ranked {rank_of} by forward replay." if rank_of else
                       ", which forward replay did not replay."), sec))

    story.append(CondPageBreak(95 * mm))

    # ============ page 2: the scene and robustness ========================================
    story += section("The scene", "The radar image the slick was detected in. Radar darkness alone is not proof of oil.")
    img_path = os.path.join(case_dir, "scene.png")
    facts = kv([("Acquired", when(scene.get("acquired_utc"))), ("Sensor", scene.get("sensor", "—")),
                ("Pixel spacing", f"{scene.get('pixel_spacing_m', '—')} m"), ("Data status", scene.get("data_status", "—")),
                ("Label source", scene.get("label_source", "—")), ("Projection", scene.get("metric_crs", "—"))], kw=26 * mm)
    facts._argW = [26 * mm, CW - 62 * mm - 26 * mm]
    if os.path.exists(img_path):
        im = Image(img_path, width=56 * mm, height=56 * mm)
        pair = Table([[im, facts]], colWidths=[62 * mm, CW - 62 * mm], hAlign="LEFT")
        pair.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(pair)
    else:
        story.append(facts)

    if frag.get("testable"):
        story += section("Robustness", "Does the leader survive small changes to the model's assumptions?")
        sf = frag.get("smallest_flip") or {}
        change = ", ".join(f"{(frag.get('axes') or {}).get(k, {}).get('label', k)} {v}" for k, v in (sf.get("changed_axes") or {}).items())
        right = [P(f"<b>{frag.get('n_points_tested', '—')}</b> tested changes to the model's assumptions; "
                   f"<b>{frag.get('n_points_flipped', 0)}</b> changed the leader.", body), Spacer(1, 2 * mm)]
        if frag.get("flip_found") and sf:
            right.append(P(f"The smallest change that flips it: <b>{esc(change)}</b> (magnitude {sf.get('magnitude')}), "
                           f"under which <b>{esc(sf.get('top_candidate', ''))}</b> leads.", sec))
        else:
            right.append(P("No tested change moved the leader.", sec))
        right += [Spacer(1, 2 * mm), P(esc(frag.get("coverage_note", "")), small)]
        rob = Table([[[P(pct(frag.get("lead_retained_fraction")), style("big", 34, 38, "Helvetica-Bold", INK)),
                       P("LEAD RETAINED", eyebrow)], right]], colWidths=[42 * mm, CW - 42 * mm], hAlign="LEFT")
        rob.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(rob)

    # ============ page 2 continues with exposure; page 3: filtering, coverage, provenance ===
    fx = rep.get("forward_exposure") or {}
    if fx.get("horizons"):
        story += section("Forward exposure", "Where the oil is modelled to drift after the image. "
                         + str(fx.get("forcing_mode", "")).split(" — ")[0].capitalize() + " — not an operational forecast.")
        names = [a.get("name", "") for a in (fx["horizons"][0].get("sensitive_area_exposure") or [])]
        th = [P("AFTER THE IMAGE", head_st), P("MODELLED SPREAD", head_st), P("SHORELINE", head_st)] + [P(esc(n.replace(" (synthetic)", "")).upper(), head_st) for n in names]
        tr = [th]
        for h in fx["horizons"]:
            ex = {a.get("name"): a.get("modelled_particle_fraction") for a in (h.get("sensitive_area_exposure") or [])}
            tr.append([P(f"<b>+{h.get('horizon_hours')} h</b>  <font color='#86868b'>{when(h.get('valid_utc'))}</font>", body),
                       P(f"{h.get('envelope_area_km2', 0):.0f} km<super>2</super>", body),
                       P(pct(h.get("modelled_shoreline_fraction")), body)] + [P(pct(ex.get(n)), body) for n in names])
        rest = CW - 62 * mm - 32 * mm - 26 * mm
        story.append(hairline_table(tr, [62 * mm, 32 * mm, 26 * mm] + [rest / max(1, len(names))] * len(names), head=True, pad=5))

    counts = hf.get("status_counts") or {}
    if counts:
        story.append(CondPageBreak(120 * mm))
        story += section("Traffic filtering", f"Every vessel in the scene, checked against where the oil could have come from over the {hf.get('hours_back', 24)} hours before the image.")
        meaning = hf.get("state_meaning") or {}
        story.append(hairline_table([[P(f"<b>{v}</b>", style("cnt", 13, 16, "Helvetica-Bold", INK)), P(esc(k.capitalize()), body), P(esc(meaning.get(k, "")), sec)]
                                     for k, v in counts.items()], [14 * mm, 26 * mm, CW - 40 * mm], pad=5))
        story.append(Spacer(1, 2.5 * mm))
        story.append(P("Unassessed is reported separately from excluded: missing evidence is not exoneration.", small))

    cov = (rep.get("unmatched_contacts") or {}).get("conditions") or {}
    if cov:
        story += section("Coverage-aware matching", "Matching radar contacts to AIS when some AIS is hidden — tested on synthetic contacts.")
        label = {"hidden_ais_recovery_rate": "Hidden AIS recovered", "false_unmatched_alert_rate": "False alerts", "mistaken_promotion_rate": "Mistaken promotions"}
        ct = [[P("RATE", head_st), P("VESSELS HIDDEN", head_st), P("AREA GOES DARK", head_st)]]
        for k, lab in label.items():
            ct.append([P(lab, body)] + [P(f"<b>{pct(cov.get(c, {}).get(k))}</b>  <font color='#86868b'>{cov.get(c, {}).get(k.replace('_rate', '_n'), '')}</font>", body)
                                       for c in ("selective", "coverage_failure")])
        story.append(hairline_table(ct, [62 * mm, 50 * mm, CW - 112 * mm], head=True, pad=5))

    ev_layers = rep.get("evidence_layers") or {}
    meta = rep.get("run_metadata") or {}
    story.append(CondPageBreak(70 * mm))
    story += section("Provenance")
    story.append(kv([("AIS", ev_layers.get("ais_source", "—")), ("Forcing", ev_layers.get("forcing_product", "—")),
                     ("Licence", ev_layers.get("data_licence", "—")), ("Generated", when(rep.get("generated_utc"))),
                     ("Software", f"Python {meta.get('python', '—')} · {meta.get('platform', '—')}")], kw=26 * mm))

    sums = rep.get("checksums_sha256") or {}
    if sums:
        story.append(CondPageBreak(110 * mm))   # integrity, then the closing uncertainty statement
        story += section("File integrity", rep.get("checksum_note", ""))
        story.append(hairline_table([[P(esc(k), kv_v), P(esc(v), mono)] for k, v in sorted(sums.items())],
                                    [50 * mm, CW - 50 * mm], pad=3))

    unc = rep.get("uncertainty_statement")
    lines = unc if isinstance(unc, list) else ([unc] if unc else [])
    closing = [Spacer(1, 7 * mm), P("Uncertainty", h2), Spacer(1, 3 * mm)]
    for line in lines:
        closing.append(Table([[P("—", sec), P(esc(line), body)]], colWidths=[6 * mm, CW - 6 * mm], hAlign="LEFT",
                             style=[("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    closing += [Spacer(1, 6 * mm), Note(f"<b>Restated.</b> {esc(rep.get('not_a', ''))}")]
    story.append(KeepTogether(closing))

    # ---- running header and footer, with "Page n of N" ------------------------------------
    header_when = when(scene.get("acquired_utc"))

    class NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw); self._pages = []
        def showPage(self):
            self._pages.append(dict(self.__dict__)); self._startPage()
        def save(self):
            n = len(self._pages)
            for st in self._pages:
                self.__dict__.update(st); self._chrome(n); super().showPage()
            super().save()
        def _chrome(self, n):
            self.saveState()
            top = H - 14 * mm
            self.setFont("Helvetica-Bold", 8.4); self.setFillColor(INK); self.drawString(LM, top, "Slick Trace")
            self.setFont("Helvetica", 8.4); self.setFillColor(TER); self.drawString(LM + 16.6 * mm, top, "Investigation dossier")
            self.setFillColor(SEC); self.drawRightString(W - RM, top, f"{iid}  ·  {header_when}")
            self.setStrokeColor(HAIR); self.setLineWidth(0.4); self.line(LM, top - 3.2 * mm, W - RM, top - 3.2 * mm)
            self.line(LM, 15 * mm, W - RM, 15 * mm)
            self.setFont("Helvetica", 7.4); self.setFillColor(TER)
            self.drawString(LM, 10.5 * mm, "An investigative lead, not proof of responsibility")
            self.drawRightString(W - RM, 10.5 * mm, f"Page {self._pageNumber} of {n}")
            self.restoreState()

    SimpleDocTemplate(out_path, pagesize=A4, leftMargin=LM, rightMargin=RM, topMargin=24 * mm, bottomMargin=21 * mm,
                      title=f"{TITLE} — {iid}", author="Slick Trace",
                      subject="Investigation dossier — an investigative lead, not proof of responsibility").build(
        story, canvasmaker=NumberedCanvas)
    return out_path
