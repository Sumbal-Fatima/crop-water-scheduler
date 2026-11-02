"""One-page-plus PDF report (reportlab + matplotlib)."""
from __future__ import annotations

import io
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _chart_png(daily: pd.DataFrame, events: pd.DataFrame) -> io.BytesIO:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6.2), sharex=True)
    ax1.bar(daily.index, daily["rain"], color="#0891b2", alpha=0.7, label="Rainfall")
    ax1.plot(daily.index, daily["et0"], color="#64748b", lw=1.2, label="ET0")
    ax1.plot(daily.index, daily["etc"], color="#16a34a", lw=2, label="ETc")
    if len(events):
        d = pd.to_datetime(events["date"])
        ax1.plot(d, [0] * len(d), "^", color="#2563eb", ms=9, label="Irrigation",
                 clip_on=False, zorder=5, markeredgecolor="white")
    ax1.set_ylabel("mm / day")
    ax1.legend(ncol=4, fontsize=8, loc="upper left")
    ax1.set_title("Crop water demand and irrigation dates", fontsize=10)
    ax2.plot(daily.index, daily["depletion"], color="#2563eb", lw=2, label="Depletion")
    ax2.plot(daily.index, daily["raw"], color="#ea580c", ls="--", label="RAW (trigger)")
    ax2.plot(daily.index, daily["taw"], color="#dc2626", ls=":", label="TAW")
    ax2.invert_yaxis()
    ax2.set_ylabel("Depletion (mm)")
    ax2.legend(ncol=3, fontsize=8)
    ax2.set_title("Root-zone soil water depletion (0 = field capacity)", fontsize=10)
    fig.autofmt_xdate()
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf


def build_pdf(summary: dict, events: pd.DataFrame, daily: pd.DataFrame,
              inputs: dict) -> bytes:
    """Return the PDF report as bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.6 * cm, bottomMargin=1.6 * cm,
                            title="Crop water requirement and irrigation schedule")
    ss = getSampleStyleSheet()
    story = [Paragraph("Crop Water Requirement &amp; Irrigation Schedule", ss["Title"]),
             Paragraph(f"Generated {datetime.now():%d %b %Y %H:%M} | FAO-56 Penman-Monteith "
                       f"single-Kc method", ss["Normal"]),
             Spacer(1, 0.4 * cm)]

    def table(rows, widths, header=True):
        t = Table(rows, colWidths=widths, hAlign="LEFT")
        style = [("FONTSIZE", (0, 0), (-1, -1), 8.5),
                 ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
        if header:
            style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                      ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
        t.setStyle(TableStyle(style))
        return t

    story.append(Paragraph("Inputs", ss["Heading2"]))
    story.append(table([[k, str(v)] for k, v in inputs.items()], [7.5 * cm, 9 * cm], header=False))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Seasonal summary", ss["Heading2"]))
    rows = [
        ["Season", f"{summary['sowing_date']} to {summary['harvest_date']} ({summary['season_days']} days)"],
        ["Reference ET0", f"{summary['et0_total_mm']} mm"],
        ["Crop water requirement ETc", f"{summary['etc_total_mm']} mm"],
        ["Rainfall (total / effective)", f"{summary['rain_total_mm']} / {summary['eff_rain_total_mm']} mm"],
        ["Net irrigation requirement", f"{summary['net_irrigation_mm']} mm"],
        ["Gross irrigation (after efficiency)", f"{summary['gross_irrigation_mm']} mm"],
        ["Number of irrigations", str(summary["n_irrigations"])],
        ["Gross volume", f"{summary['gross_m3_per_ha']:.0f} m3/ha  |  {summary['gross_m3_per_acre']:.0f} m3/acre"],
        ["Deep percolation loss", f"{summary['deep_percolation_mm']} mm"],
    ]
    if summary.get("days_from_climatology"):
        rows.append(["Days using climatological (average) weather", str(summary["days_from_climatology"])])
    story.append(table(rows, [7.5 * cm, 9 * cm], header=False))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Image(_chart_png(daily, events), width=16.5 * cm, height=12.8 * cm))

    story.append(Paragraph("Irrigation schedule", ss["Heading2"]))
    if len(events):
        head = ["#", "Date", "Day", "Stage", "Net mm", "Gross mm", "m3/ha", "m3/acre"]
        data = [head] + [[i + 1, str(r.date), int(r.day_after_sowing), r.stage, r.net_mm, r.gross_mm,
                          f"{r.m3_per_ha:.0f}", f"{r.m3_per_acre:.0f}"]
                         for i, r in enumerate(events.itertuples())]
        story.append(table(data, [0.9 * cm, 2.6 * cm, 1.3 * cm, 3.1 * cm, 1.8 * cm, 2.1 * cm, 2.1 * cm, 2.3 * cm]))
    else:
        story.append(Paragraph("No irrigation required under the chosen settings.", ss["Normal"]))

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "<b>Notes.</b> Weather: NASA POWER (gridded, ~50 km) unless stated otherwise. Crop and soil "
        "parameters are typical FAO-56 values; replace them with local data for field decisions. "
        "Use as decision support, not as a substitute for soil-moisture monitoring.", ss["Italic"]))
    doc.build(story)
    return buf.getvalue()
