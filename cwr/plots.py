"""Plotly figures for the Streamlit app."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BLUE = "#2563eb"
GREEN = "#16a34a"
ORANGE = "#ea580c"
GREY = "#64748b"
RED = "#dc2626"
TEAL = "#0891b2"

_LAYOUT = dict(template="plotly_white", margin=dict(l=40, r=20, t=50, b=40),
               legend=dict(orientation="h", y=-0.2), font=dict(size=13))


def fig_water_demand(daily: pd.DataFrame, events: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(x=daily.index, y=daily["rain"], name="Rainfall", marker_color=TEAL, opacity=0.7)
    fig.add_scatter(x=daily.index, y=daily["et0"], name="ET0", line=dict(color=GREY, width=1.5))
    fig.add_scatter(x=daily.index, y=daily["etc"], name="ETc (crop)", line=dict(color=GREEN, width=2.5))
    if len(events):
        d = pd.to_datetime(events["date"])
        fig.add_scatter(x=d, y=[0] * len(d), mode="markers", name="Irrigation",
                        marker=dict(symbol="triangle-up", size=13, color=BLUE,
                                    line=dict(width=1, color="white")),
                        customdata=events[["gross_mm", "net_mm"]].to_numpy(),
                        hovertemplate="%{x|%d %b}<br>gross %{customdata[0]} mm<br>net %{customdata[1]} mm<extra></extra>")
    fig.update_layout(title="Daily crop water demand, rainfall and irrigation dates",
                      yaxis_title="mm / day", **_LAYOUT)
    return fig


def fig_soil_water(daily: pd.DataFrame, events: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(x=daily.index, y=daily["taw"], name="TAW (wilting point)",
                    line=dict(color=RED, dash="dot"))
    fig.add_scatter(x=daily.index, y=daily["raw"], name="RAW (irrigation trigger)",
                    line=dict(color=ORANGE, dash="dash"))
    fig.add_scatter(x=daily.index, y=daily["depletion"], name="Root-zone depletion",
                    line=dict(color=BLUE, width=2.5), fill="tozeroy",
                    fillcolor="rgba(37,99,235,0.12)")
    if len(events):
        d = pd.to_datetime(events["date"])
        fig.add_scatter(x=d, y=daily.loc[d, "raw"], mode="markers", name="Irrigation",
                        marker=dict(symbol="triangle-down", size=12, color=BLUE,
                                    line=dict(width=1, color="white")))
    fig.update_layout(title="Soil water depletion (0 = field capacity)",
                      yaxis_title="Depletion (mm)", yaxis_autorange="reversed", **_LAYOUT)
    return fig


def fig_kc(daily: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_scatter(x=daily["day_after_sowing"], y=daily["kc"], name="Kc",
                    line=dict(color=GREEN, width=3), secondary_y=False)
    fig.add_scatter(x=daily["day_after_sowing"], y=daily["zr_m"], name="Root depth (m)",
                    line=dict(color=ORANGE, dash="dash"), secondary_y=True)
    fig.update_layout(title="Crop coefficient and root depth", **_LAYOUT)
    fig.update_xaxes(title_text="Days after sowing")
    fig.update_yaxes(title_text="Kc", secondary_y=False)
    fig.update_yaxes(title_text="Root depth (m)", secondary_y=True)
    return fig


def fig_ensemble(ens: pd.DataFrame, selected_year: int | None = None) -> go.Figure:
    colors = [BLUE if (selected_year is None or y == selected_year) else "#93c5fd"
              for y in ens["sowing_year"]]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=ens["sowing_year"].astype(str), y=ens["gross_irrigation_mm"],
                name="Gross irrigation (mm)", marker_color=colors, secondary_y=False)
    fig.add_scatter(x=ens["sowing_year"].astype(str), y=ens["rain_mm"], name="Season rainfall (mm)",
                    mode="lines+markers", line=dict(color=TEAL), secondary_y=True)
    fig.update_layout(title="Irrigation need in different years (same sowing date)", **_LAYOUT)
    fig.update_yaxes(title_text="Gross irrigation (mm)", secondary_y=False)
    fig.update_yaxes(title_text="Rainfall (mm)", secondary_y=True)
    return fig
