from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.schemas.report import ReportHeatmapSegment, ReportRequest

PAGE_W, PAGE_H = A4
LEFT = 44
RIGHT = 44
TOP = 40
BOTTOM = 38
CONTENT_W = PAGE_W - LEFT - RIGHT

BG = colors.HexColor("#F8FAFC")
TEXT = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#475569")
PRIMARY = colors.HexColor("#1D4ED8")
BORDER = colors.HexColor("#CBD5E1")


def _risk_to_color(value: float) -> colors.Color:
    v = max(0.0, min(1.0, value))
    # Green -> Yellow -> Red
    if v < 0.5:
        t = v / 0.5
        return colors.Color(0.07 + (0.98 - 0.07) * t, 0.62 + (0.85 - 0.62) * t, 0.28 - 0.06 * t)
    t = (v - 0.5) / 0.5
    return colors.Color(0.98 - 0.77 * t, 0.85 - 0.67 * t, 0.22 - 0.12 * t)


def _new_page(pdf: canvas.Canvas, page_no: int, title: str) -> tuple[int, int]:
    if page_no > 0:
        pdf.showPage()

    pdf.setFillColor(BG)
    pdf.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    pdf.setFillColor(colors.white)
    pdf.rect(0, PAGE_H - 56, PAGE_W, 56, fill=1, stroke=0)
    pdf.setFillColor(PRIMARY)
    pdf.rect(0, PAGE_H - 56, PAGE_W, 4, fill=1, stroke=0)
    pdf.setFillColor(TEXT)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(LEFT, PAGE_H - 36, title)

    page_no += 1
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(PAGE_W - RIGHT, 18, f"Page {page_no}")
    return page_no, PAGE_H - TOP - 34


def _ensure_space(pdf: canvas.Canvas, y: float, need: float, page_no: int, title: str) -> tuple[int, float]:
    if y - need >= BOTTOM:
        return page_no, y
    return _new_page(pdf, page_no, title)


def _section_title(pdf: canvas.Canvas, y: float, text: str) -> float:
    pdf.setFillColor(TEXT)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(LEFT, y, text)
    pdf.setStrokeColor(BORDER)
    pdf.setLineWidth(0.8)
    pdf.line(LEFT, y - 4, PAGE_W - RIGHT, y - 4)
    return y - 18


def _draw_kv_cards(pdf: canvas.Canvas, y: float, items: list[tuple[str, str]]) -> float:
    cols = 3
    gap = 10
    card_h = 48
    card_w = (CONTENT_W - gap * (cols - 1)) / cols

    for idx, (label, value) in enumerate(items):
        row = idx // cols
        col = idx % cols
        x = LEFT + col * (card_w + gap)
        cy = y - row * (card_h + 8)
        pdf.setFillColor(colors.white)
        pdf.setStrokeColor(BORDER)
        pdf.roundRect(x, cy - card_h, card_w, card_h, 6, fill=1, stroke=1)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(x + 8, cy - 16, label)
        pdf.setFillColor(TEXT)
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(x + 8, cy - 34, value)

    rows = (len(items) + cols - 1) // cols
    return y - rows * (card_h + 8)


def _draw_table(
    pdf: canvas.Canvas,
    y: float,
    headers: list[str],
    rows: list[list[str]],
    col_widths: list[float],
    title: str,
    page_no: int,
    report_title: str,
) -> tuple[int, float]:
    row_h = 16
    min_need = row_h * 3 + 16
    page_no, y = _ensure_space(pdf, y, min_need, page_no, report_title)
    y = _section_title(pdf, y, title)

    x = LEFT
    header_y = y
    pdf.setFillColor(colors.HexColor("#E2E8F0"))
    pdf.rect(LEFT, header_y - row_h + 3, sum(col_widths), row_h, fill=1, stroke=0)
    pdf.setFillColor(TEXT)
    pdf.setFont("Helvetica-Bold", 8)
    for i, h in enumerate(headers):
        pdf.drawString(x + 4, header_y - 8, h)
        x += col_widths[i]

    y = header_y - row_h
    pdf.setFont("Helvetica", 8)
    for row_idx, row in enumerate(rows):
        page_no, y = _ensure_space(pdf, y, row_h + 6, page_no, report_title)
        x = LEFT
        if row_idx % 2 == 0:
            pdf.setFillColor(colors.white)
            pdf.rect(LEFT, y - row_h + 3, sum(col_widths), row_h, fill=1, stroke=0)
        pdf.setFillColor(TEXT)
        for i, cell in enumerate(row):
            pdf.drawString(x + 4, y - 8, str(cell)[:48])
            x += col_widths[i]
        y -= row_h

    pdf.setStrokeColor(BORDER)
    pdf.rect(LEFT, header_y - row_h * (len(rows) + 1) + 3, sum(col_widths), row_h * (len(rows) + 1), fill=0, stroke=1)
    return page_no, y - 8


def _draw_stress_bar_chart(pdf: canvas.Canvas, y: float, stresses: dict[str, float], page_no: int, report_title: str) -> tuple[int, float]:
    page_no, y = _ensure_space(pdf, y, 240, page_no, report_title)
    y = _section_title(pdf, y, "Stress Distribution")
    if not stresses:
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(LEFT, y, "No stress data")
        return page_no, y - 18

    x0 = LEFT
    y0 = y - 190
    w = CONTENT_W
    h = 170
    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(BORDER)
    pdf.roundRect(x0, y0, w, h, 8, fill=1, stroke=1)

    items = sorted(stresses.items(), key=lambda i: abs(i[1]), reverse=True)[:16]
    max_v = max(abs(v) for _, v in items) or 1.0
    bar_gap = (w - 28) / max(1, len(items))
    bar_w = max(5, bar_gap * 0.68)

    pdf.setStrokeColor(colors.HexColor("#94A3B8"))
    pdf.line(x0 + 14, y0 + 20, x0 + w - 12, y0 + 20)
    for idx, (rod_id, stress) in enumerate(items):
        x = x0 + 14 + idx * bar_gap + (bar_gap - bar_w) / 2
        bh = (abs(stress) / max_v) * (h - 38)
        color = colors.HexColor("#2563EB") if stress >= 0 else colors.HexColor("#DC2626")
        pdf.setFillColor(color)
        pdf.rect(x, y0 + 20, bar_w, bh, fill=1, stroke=0)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 7)
        pdf.drawString(x, y0 + 9, rod_id[:8])

    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(x0 + 14, y0 + h - 10, f"Top 16 rods by |stress|, normalized to {max_v:.5f}")
    return page_no, y0 - 10


def _draw_quasi_static_chart(
    pdf: canvas.Canvas, y: float, steps: list[dict], page_no: int, report_title: str
) -> tuple[int, float]:
    if not steps:
        return page_no, y
    page_no, y = _ensure_space(pdf, y, 230, page_no, report_title)
    y = _section_title(pdf, y, "Quasi-static Trends")

    x0 = LEFT
    y0 = y - 180
    w = CONTENT_W
    h = 160
    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(BORDER)
    pdf.roundRect(x0, y0, w, h, 8, fill=1, stroke=1)

    xs = [int(s.get("step_index", 0) or 0) for s in steps]
    stress_vals = [float(s.get("max_abs_stress", 0) or 0) for s in steps]
    risk_vals = [float(s.get("max_risk", 0) or 0) for s in steps]

    if len(xs) < 2:
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(x0 + 12, y0 + h / 2, "Not enough steps for trend chart")
        return page_no, y0 - 8

    max_x = max(xs)
    min_x = min(xs)
    sx = lambda v: x0 + 20 + (v - min_x) / max(1e-9, max_x - min_x) * (w - 44)

    max_stress = max(stress_vals) or 1.0
    max_risk = max(risk_vals) or 1.0
    sy_stress = lambda v: y0 + 24 + (v / max_stress) * (h - 42)
    sy_risk = lambda v: y0 + 24 + (v / max_risk) * (h - 42)

    pdf.setStrokeColor(colors.HexColor("#CBD5E1"))
    pdf.line(x0 + 20, y0 + 24, x0 + w - 24, y0 + 24)
    pdf.line(x0 + 20, y0 + 24, x0 + 20, y0 + h - 18)

    # Stress line
    pdf.setStrokeColor(colors.HexColor("#1D4ED8"))
    pdf.setLineWidth(1.8)
    for i in range(len(xs) - 1):
        pdf.line(sx(xs[i]), sy_stress(stress_vals[i]), sx(xs[i + 1]), sy_stress(stress_vals[i + 1]))
    # Risk line
    pdf.setStrokeColor(colors.HexColor("#EF4444"))
    pdf.setLineWidth(1.4)
    for i in range(len(xs) - 1):
        pdf.line(sx(xs[i]), sy_risk(risk_vals[i]), sx(xs[i + 1]), sy_risk(risk_vals[i + 1]))

    for i, x in enumerate(xs):
        pdf.setFillColor(colors.HexColor("#1D4ED8"))
        pdf.circle(sx(x), sy_stress(stress_vals[i]), 2.2, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#EF4444"))
        pdf.circle(sx(x), sy_risk(risk_vals[i]), 2.0, fill=1, stroke=0)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 7)
        pdf.drawCentredString(sx(x), y0 + 11, str(x))

    pdf.setFillColor(colors.HexColor("#1D4ED8"))
    pdf.rect(x0 + w - 140, y0 + h - 16, 10, 2, fill=1, stroke=0)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(x0 + w - 126, y0 + h - 16, "max |stress|")

    pdf.setFillColor(colors.HexColor("#EF4444"))
    pdf.rect(x0 + w - 140, y0 + h - 30, 10, 2, fill=1, stroke=0)
    pdf.setFillColor(MUTED)
    pdf.drawString(x0 + w - 126, y0 + h - 30, "max risk")
    return page_no, y0 - 10


def _risk_from_segments(segments: list[ReportHeatmapSegment], position: float) -> float:
    if not segments:
        return 0.0
    p = max(0.0, min(1.0, position))
    ordered = sorted(segments, key=lambda s: s.position)
    if p <= ordered[0].position:
        return float(ordered[0].risk)
    if p >= ordered[-1].position:
        return float(ordered[-1].risk)
    for i in range(len(ordered) - 1):
        a = ordered[i]
        b = ordered[i + 1]
        if a.position <= p <= b.position:
            span = max(1e-9, b.position - a.position)
            t = (p - a.position) / span
            return float(a.risk + (b.risk - a.risk) * t)
    return float(ordered[-1].risk)


def _draw_structure_with_gradient(
    pdf: canvas.Canvas, y: float, report: ReportRequest, page_no: int, report_title: str
) -> tuple[int, float]:
    page_no, y = _ensure_space(pdf, y, 290, page_no, report_title)
    y = _section_title(pdf, y, "Model With Defect Probability Gradient")
    if not report.nodes or not report.rods:
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(LEFT, y, "No model geometry in report payload")
        return page_no, y - 18

    x0 = LEFT
    y0 = y - 245
    w = CONTENT_W
    h = 220
    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(BORDER)
    pdf.roundRect(x0, y0, w, h, 8, fill=1, stroke=1)

    xs = [n.x for n in report.nodes]
    ys = [n.y for n in report.nodes]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(1e-9, max_x - min_x)
    span_y = max(1e-9, max_y - min_y)

    def tx(v: float) -> float:
        return x0 + 18 + (v - min_x) / span_x * (w - 36)

    def ty(v: float) -> float:
        return y0 + 18 + (v - min_y) / span_y * (h - 48)

    node_map = {n.id: n for n in report.nodes}
    heatmap_by_rod = {item.rod_id: item.segments for item in report.risk_heatmap}
    top_risk_by_rod = {item.rod_id: item.risk for item in report.top_risky_rods}

    # Draw rods as many tiny segments to mimic gradient.
    for rod in report.rods:
        a = node_map.get(rod.start_node_id)
        b = node_map.get(rod.end_node_id)
        if not a or not b:
            continue
        x1, y1 = tx(a.x), ty(a.y)
        x2, y2 = tx(b.x), ty(b.y)
        segments = heatmap_by_rod.get(rod.id, [])
        seg_count = 24
        for s in range(seg_count):
            t0 = s / seg_count
            t1 = (s + 1) / seg_count
            tm = (t0 + t1) * 0.5
            risk = (
                _risk_from_segments(segments, tm)
                if segments
                else float(top_risk_by_rod.get(rod.id, 0.0))
            )
            pdf.setStrokeColor(_risk_to_color(risk))
            pdf.setLineWidth(3.4)
            pdf.line(
                x1 + (x2 - x1) * t0,
                y1 + (y2 - y1) * t0,
                x1 + (x2 - x1) * t1,
                y1 + (y2 - y1) * t1,
            )

        mx = (x1 + x2) * 0.5
        my = (y1 + y2) * 0.5
        pdf.setFillColor(colors.white)
        pdf.setStrokeColor(colors.HexColor("#94A3B8"))
        pdf.circle(mx, my, 6, fill=1, stroke=1)
        pdf.setFillColor(TEXT)
        pdf.setFont("Helvetica", 7)
        pdf.drawCentredString(mx, my - 2, rod.id[:6])

    # Draw defects with probability labels.
    for defect in report.defects:
        rod = next((r for r in report.rods if r.id == defect.rod_id), None)
        if rod is None:
            continue
        a = node_map.get(rod.start_node_id)
        b = node_map.get(rod.end_node_id)
        if not a or not b:
            continue
        pos = max(0.0, min(1.0, defect.position if defect.position is not None else 0.5))
        x = tx(a.x) + (tx(b.x) - tx(a.x)) * pos
        yy = ty(a.y) + (ty(b.y) - ty(a.y)) * pos
        segments = heatmap_by_rod.get(rod.id, [])
        risk = _risk_from_segments(segments, pos) if segments else float(top_risk_by_rod.get(rod.id, 0.0))
        pdf.setFillColor(colors.HexColor("#111827"))
        pdf.setStrokeColor(colors.white)
        pdf.circle(x, yy, 4.6, fill=1, stroke=1)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 6)
        pdf.drawCentredString(x, yy - 2, "D")
        pdf.setFillColor(TEXT)
        pdf.setFont("Helvetica", 7)
        pdf.drawString(x + 6, yy + 6, f"{defect.id}: p={risk:.2f}")

    # Nodes on top.
    for node in report.nodes:
        cx, cy = tx(node.x), ty(node.y)
        pdf.setFillColor(colors.white)
        pdf.setStrokeColor(colors.HexColor("#1E293B"))
        pdf.circle(cx, cy, 3, fill=1, stroke=1)
        pdf.setFillColor(TEXT)
        pdf.setFont("Helvetica", 7)
        pdf.drawString(cx + 4, cy + 2, node.id)

    # Gradient legend
    lg_x = x0 + w - 170
    lg_y = y0 + h - 18
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(lg_x, lg_y + 8, "Defect probability")
    bar_w = 140
    for i in range(bar_w):
        r = i / max(1, bar_w - 1)
        pdf.setStrokeColor(_risk_to_color(r))
        pdf.setLineWidth(4)
        pdf.line(lg_x + i, lg_y, lg_x + i + 1, lg_y)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 7)
    pdf.drawString(lg_x, lg_y - 9, "0.0")
    pdf.drawRightString(lg_x + bar_w, lg_y - 9, "1.0")
    return page_no, y0 - 10


def _recommendations(report: ReportRequest) -> list[str]:
    recs: list[str] = []
    highest_risk = max((item.risk for item in report.top_risky_rods), default=0.0)
    max_stress = max((abs(v) for v in report.stresses.values()), default=0.0)

    if highest_risk >= 0.8:
        recs.append("Immediate inspection for rods with probability >= 0.80.")
    elif highest_risk >= 0.6:
        recs.append("Short-term NDT inspection for rods with probability >= 0.60.")
    else:
        recs.append("Risk profile is moderate; keep routine monitoring cycle.")

    if max_stress > 0:
        recs.append(f"Maximum |stress| = {max_stress:.6f}. Prioritize high-stress members.")
    if report.defects_count > 0:
        recs.append(f"Defects in model: {report.defects_count}. Validate geometry and depth parameters.")
    return recs


def generate_report_pdf(report: ReportRequest) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_no = 0

    page_no, y = _new_page(pdf, page_no, report.title)

    pdf.setFillColor(TEXT)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(LEFT, y, report.title)
    y -= 10
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(LEFT, y - 6, "Automated structural report with AI risk visualization")
    y -= 26

    y = _draw_kv_cards(
        pdf,
        y,
        [
            ("Nodes", str(report.nodes_count)),
            ("Rods", str(report.rods_count)),
            ("Defects", str(report.defects_count)),
            ("Stress points", str(len(report.stresses))),
            ("Risky rods (AI)", str(len(report.top_risky_rods))),
            ("Quasi-static steps", str(len(report.quasi_static_steps or []))),
        ],
    )
    y -= 8

    page_no, y = _draw_structure_with_gradient(pdf, y, report, page_no, report.title)
    page_no, y = _draw_stress_bar_chart(pdf, y, report.stresses, page_no, report.title)
    page_no, y = _draw_quasi_static_chart(pdf, y, report.quasi_static_steps or [], page_no, report.title)

    top_risk_rows = [
        [str(i + 1), item.rod_id, f"{item.risk:.4f}"]
        for i, item in enumerate(sorted(report.top_risky_rods, key=lambda r: r.risk, reverse=True)[:15])
    ]
    page_no, y = _draw_table(
        pdf,
        y,
        headers=["Rank", "Rod", "Probability"],
        rows=top_risk_rows or [["-", "-", "-"]],
        col_widths=[46, 220, 90],
        title="Top Risky Rods",
        page_no=page_no,
        report_title=report.title,
    )

    defect_rows = [
        [
            d.id,
            d.rod_id,
            d.defect_type,
            "-" if d.position is None else f"{d.position:.2f}",
            "-" if d.depth is None else f"{d.depth:.2f}",
        ]
        for d in report.defects[:20]
    ]
    page_no, y = _draw_table(
        pdf,
        y,
        headers=["Defect", "Rod", "Type", "Pos", "Depth"],
        rows=defect_rows or [["-", "-", "-", "-", "-"]],
        col_widths=[88, 88, 130, 52, 52],
        title="Defect Table",
        page_no=page_no,
        report_title=report.title,
    )

    step_rows = [
        [
            str(s.get("step_index", "-")),
            str(s.get("name", "-"))[:18],
            f"{float(s.get('load_factor', 0) or 0):.3f}",
            f"{float(s.get('max_abs_stress', 0) or 0):.5f}",
            f"{float(s.get('max_risk', 0) or 0):.4f}",
        ]
        for s in (report.quasi_static_steps or [])[:24]
    ]
    page_no, y = _draw_table(
        pdf,
        y,
        headers=["Step", "Name", "Load", "Max |stress|", "Max risk"],
        rows=step_rows or [["-", "-", "-", "-", "-"]],
        col_widths=[44, 170, 62, 96, 72],
        title="Quasi-static Step Summary",
        page_no=page_no,
        report_title=report.title,
    )

    page_no, y = _ensure_space(pdf, y, 100, page_no, report.title)
    y = _section_title(pdf, y, "Recommendations")
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(TEXT)
    for rec in _recommendations(report):
        page_no, y = _ensure_space(pdf, y, 16, page_no, report.title)
        pdf.drawString(LEFT, y, f"• {rec}")
        y -= 14

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
