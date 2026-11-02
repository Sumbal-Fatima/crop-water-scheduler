"""Plotly figures for the Streamlit app.

One colour per meaning, used the same way everywhere:
  blue   = water you apply (irrigation) and rainfall, drawn as different marks
  green  = crop water use (ETc)
  grey   = reference evapotranspiration (ET0), a reference line, not a series
  orange = the irrigation trigger (RAW)
Palette checked with the dataviz validator (blue/green/orange pass the
normal-vision and colour-blind separation checks on the chart surface).
Charts never use two y-axes: measures with different units get their own panel.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BLUE = "#2a78d6"
GREEN = "#008300"
ORANGE = "#eb6834"
GREY = "#7a8588"
INK = "#10282F"
MUTED = "#5A6F75"
GRID = "#E3ECEA"

PLOT_CONFIG = {"displayModeBar": False, "responsive": True}


def _layout(fig: go.Figure, title: str, height: int = 380, legend: bool = True) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=16, color=INK)),
        height=height, template="simple_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Figtree, system-ui, sans-serif", size=13, color=INK),
        margin=dict(l=10, r=10, t=70 if legend else 50, b=10), hovermode="x unified",
        hoverlabel=dict(bgcolor="white", font_size=13),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=12)),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickcolor=GRID, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor="rgba(0,0,0,0)", tickfont=dict(color=MUTED))
    return fig


def fig_water_demand(daily: pd.DataFrame, events: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(x=daily.index, y=daily["rain"], name="Rainfall", marker_color=BLUE, opacity=0.4,
                hovertemplate="%{y:.1f} mm")
    fig.add_scatter(x=daily.index, y=daily["et0"], name="Reference ET0",
                    line=dict(color=GREY, width=1.6, dash="dot"), hovertemplate="%{y:.1f} mm")
    fig.add_scatter(x=daily.index, y=daily["etc"], name="Crop water use (ETc)",
                    line=dict(color=GREEN, width=3), hovertemplate="%{y:.1f} mm")
    if len(events):
        d = pd.to_datetime(events["date"])
        fig.add_scatter(x=d, y=[0] * len(d), mode="markers", name="Irrigation",
                        marker=dict(symbol="triangle-up", size=14, color=BLUE, line=dict(width=2, color="white")),
                        customdata=events[["gross_mm", "net_mm"]].to_numpy(),
                        hovertemplate="Irrigate: %{customdata[0]:.0f} mm gross, %{customdata[1]:.0f} mm net")
    _layout(fig, "Crop water demand, rainfall and irrigation dates")
    fig.update_yaxes(title_text="mm per day")
    return fig


def fig_soil_water(daily: pd.DataFrame, events: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(x=daily.index, y=daily["depletion"], name="Root-zone depletion",
                    line=dict(color=BLUE, width=3), fill="tozeroy", fillcolor="rgba(42,120,214,0.12)",
                    hovertemplate="%{y:.0f} mm")
    fig.add_scatter(x=daily.index, y=daily["raw"], name="Irrigation trigger (RAW)",
                    line=dict(color=ORANGE, width=2, dash="dash"), hovertemplate="%{y:.0f} mm")
    fig.add_scatter(x=daily.index, y=daily["taw"], name="Wilting point (TAW)",
                    line=dict(color=GREY, width=2, dash="dot"), hovertemplate="%{y:.0f} mm")
    if len(events):
        d = pd.to_datetime(events["date"])
        fig.add_scatter(x=d, y=daily.loc[d, "raw"], mode="markers", name="Irrigation",
                        marker=dict(symbol="triangle-down", size=13, color=BLUE, line=dict(width=2, color="white")),
                        hoverinfo="skip")
    _layout(fig, "Soil water depletion (0 mm means the soil is full)")
    fig.update_yaxes(title_text="Depletion (mm)", autorange="reversed")
    return fig


def fig_kc(daily: pd.DataFrame) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
                        subplot_titles=("Crop coefficient (Kc)", "Effective root depth (m)"))
    fig.add_scatter(x=daily["day_after_sowing"], y=daily["kc"], name="Kc", showlegend=False,
                    line=dict(color=GREEN, width=3), hovertemplate="Kc %{y:.2f}", row=1, col=1)
    fig.add_scatter(x=daily["day_after_sowing"], y=daily["zr_m"], name="Root depth", showlegend=False,
                    line=dict(color=GREY, width=3), hovertemplate="%{y:.2f} m", row=2, col=1)
    _layout(fig, "How the crop changes through the season", height=430, legend=False)
    fig.update_xaxes(title_text="Days after sowing", row=2, col=1)
    for a in fig.layout.annotations:
        a.update(x=0, xanchor="left", font=dict(size=13, color=MUTED))
    return fig


def fig_ensemble(ens: pd.DataFrame, selected_year: int | None = None) -> go.Figure:
    years = ens["sowing_year"].astype(str)
    colors = [BLUE if (selected_year is None or y == selected_year) else "#9dbfe9" for y in ens["sowing_year"]]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.6, 0.4],
                        subplot_titles=("Gross irrigation needed (mm)", "Rainfall during the season (mm)"))
    fig.add_bar(x=years, y=ens["gross_irrigation_mm"], marker_color=colors, showlegend=False,
                hovertemplate="%{y:.0f} mm", row=1, col=1)
    fig.add_bar(x=years, y=ens["rain_mm"], marker_color=BLUE, opacity=0.45, showlegend=False,
                hovertemplate="%{y:.0f} mm", row=2, col=1)
    _layout(fig, "Irrigation need in past years, same sowing date", height=470, legend=False)
    fig.update_layout(bargap=0.25)
    for a in fig.layout.annotations:
        a.update(x=0, xanchor="left", font=dict(size=13, color=MUTED))
    return fig
