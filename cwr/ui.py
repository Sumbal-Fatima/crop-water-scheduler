"""Look and feel for the Streamlit app: theme CSS and the few custom HTML blocks.

Design notes
------------
* One signature element: the season ribbon, a horizontal strip of the crop's
  growth stages with a pin on every irrigation date. It answers "what happens
  when" at a glance and is the only decorated element on the page.
* Palette is taken from the subject: canal water (deep blue-green), crop
  (green) and the straw colour of ripening wheat. Irrigation is always the
  chart blue, so the same event has the same colour in the ribbon and charts.
* Type: Bricolage Grotesque for headings (it has some character), Figtree for
  text and numbers. Both fall back to the system sans if offline.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

INK = "#10282F"
MUTED = "#5A6F75"
CANAL = "#0E5A6B"
WATER = "#2a78d6"          # irrigation, same blue as in the charts
LINE = "#D5E2DF"
MIST = "#F3F8F6"

STAGE_COLORS = {
    "Initial": ("#D3E8DA", INK),
    "Development": ("#93C7A6", INK),
    "Mid-season": ("#2E7D4F", "#FFFFFF"),
    "Late-season": ("#CDBB8A", INK),
}

CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Figtree:wght@400;500;600&display=swap');

html, body, [class*="css"], .stApp {{ font-family: 'Figtree', system-ui, -apple-system, 'Segoe UI', sans-serif; }}
.stApp {{ background: {MIST}; color: {INK}; }}
h1, h2, h3, .mast-title, .answer-date, [data-testid="stMetricValue"] {{
  font-family: 'Bricolage Grotesque', 'Figtree', system-ui, sans-serif; letter-spacing: -0.01em;
}}
header[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer, .stDeployButton {{ visibility: hidden; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1180px; }}

/* sidebar */
section[data-testid="stSidebar"] {{ border-right: 1px solid {LINE}; }}
section[data-testid="stSidebar"] h2 {{
  font-size: 1.02rem; font-weight: 700; color: {CANAL};
  margin: 1.4rem 0 0.4rem; padding-bottom: 0.35rem; border-bottom: 1px solid {LINE};
}}
section[data-testid="stSidebar"] h2:first-of-type {{ margin-top: 0.2rem; }}
section[data-testid="stSidebar"] label p {{ font-size: 0.88rem; color: {INK}; }}

/* masthead */
.mast-title {{ font-size: 2.35rem; font-weight: 700; line-height: 1.1; color: {INK}; margin: 0; }}
.mast-sub {{ color: {MUTED}; font-size: 1.04rem; margin: 0.45rem 0 1.4rem; max-width: 46rem; line-height: 1.5; }}

/* answer card */
.answer {{
  background: #fff; border: 1px solid {LINE}; border-left: 6px solid {CANAL};
  border-radius: 14px; padding: 1.5rem 1.7rem 1.3rem; margin: 0 0 1.4rem;
  box-shadow: 0 1px 2px rgba(16,40,47,0.04);
}}
.answer-kicker {{ color: {MUTED}; font-size: 0.95rem; font-weight: 500; }}
.answer-date {{ font-size: 2.6rem; font-weight: 700; line-height: 1.12; color: {CANAL}; margin: 0.1rem 0 0.2rem; }}
.answer-sub {{ font-size: 1.02rem; color: {INK}; max-width: 44rem; line-height: 1.5; }}
.answer-sub b {{ font-weight: 600; }}

/* season ribbon */
.ribbon-wrap {{ margin-top: 1.5rem; }}
.ribbon-title {{ font-size: 0.86rem; color: {MUTED}; margin-bottom: 0.2rem; }}
.ribbon-marks {{ position: relative; height: 3.6rem; }}
.pin {{ position: absolute; bottom: 0; transform: translateX(-50%); text-align: center; white-space: nowrap; }}
.pin-text {{ font-size: 0.78rem; line-height: 1.15; color: {INK}; }}
.pin-text b {{ display: block; font-weight: 600; }}
.pin-drop {{
  width: 14px; height: 14px; margin: 3px auto 0; background: {WATER};
  border-radius: 50% 50% 50% 0; transform: rotate(-45deg); border: 2px solid #fff;
  box-shadow: 0 0 0 1px {WATER};
}}
.ribbon {{ display: flex; height: 2.1rem; border-radius: 8px; overflow: hidden; gap: 2px; }}
.seg {{ display: flex; align-items: center; justify-content: center; font-size: 0.78rem; font-weight: 500;
  overflow: hidden; white-space: nowrap; padding: 0 6px; }}
.ribbon-axis {{ display: flex; justify-content: space-between; font-size: 0.78rem; color: {MUTED}; margin-top: 0.3rem; }}

/* metric tiles */
[data-testid="stMetric"] {{
  background: #fff; border: 1px solid {LINE}; border-radius: 12px; padding: 0.9rem 1.05rem;
}}
[data-testid="stMetricLabel"] p {{ white-space: normal; color: {MUTED}; font-size: 0.86rem; }}
[data-testid="stMetricValue"] {{ font-size: 1.75rem; font-weight: 700; color: {INK}; white-space: normal; }}
[data-testid="stMetricDelta"] {{ font-size: 0.8rem; }}

/* tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 1.4rem; border-bottom: 1px solid {LINE}; }}
.stTabs [data-baseweb="tab"] {{ height: 2.8rem; padding: 0 0.1rem; background: transparent; font-weight: 500; color: {MUTED}; }}
.stTabs [aria-selected="true"] {{ color: {CANAL}; }}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: {CANAL}; height: 3px; }}

/* buttons */
.stButton > button[kind="primary"], .stDownloadButton > button {{
  border-radius: 10px; font-weight: 600; padding: 0.55rem 1rem;
}}
.stButton > button[kind="primary"] {{ background: {CANAL}; border: 1px solid {CANAL}; }}
.stButton > button[kind="primary"]:hover {{ background: #0A4856; border-color: #0A4856; }}
.stDownloadButton > button {{ border: 1px solid {LINE}; background: #fff; color: {INK}; }}
.stDownloadButton > button:hover {{ border-color: {CANAL}; color: {CANAL}; }}

/* notices and data */
[data-testid="stAlert"] {{ border-radius: 12px; }}
[data-testid="stDataFrame"] {{ border: 1px solid {LINE}; border-radius: 10px; overflow: hidden; }}

/* empty state */
.how {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; margin-top: 0.6rem; }}
.how > div {{ background: #fff; border: 1px solid {LINE}; border-radius: 12px; padding: 1.1rem 1.2rem; }}
.how .n {{ font-family: 'Bricolage Grotesque', sans-serif; font-weight: 700; color: {CANAL}; font-size: 1.5rem; }}
.how h4 {{ margin: 0.1rem 0 0.35rem; font-size: 1.05rem; color: {INK}; }}
.how p {{ margin: 0; color: {MUTED}; font-size: 0.93rem; line-height: 1.5; }}

.fine {{ color: {MUTED}; font-size: 0.82rem; margin-top: 2.2rem; line-height: 1.5; }}

@media (max-width: 760px) {{
  .mast-title {{ font-size: 1.8rem; }}
  .answer-date {{ font-size: 2rem; }}
  .how {{ grid-template-columns: 1fr; }}
  .seg {{ font-size: 0.68rem; padding: 0 3px; }}
}}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; animation: none !important; }} }}
"""


def inject_css() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def masthead() -> None:
    st.markdown(
        '<h1 class="mast-title">Crop water and irrigation scheduler</h1>'
        '<p class="mast-sub">Find out how much water your crop needs and when to apply it. '
        'Built on the FAO-56 Penman-Monteith method, using daily NASA POWER weather for any location.</p>',
        unsafe_allow_html=True)


def empty_state() -> None:
    st.markdown(
        '<div class="how">'
        '<div><div class="n">1</div><h4>Choose your field</h4>'
        '<p>Pick a location, crop, sowing date and soil in the sidebar, then press Calculate.</p></div>'
        '<div><div class="n">2</div><h4>We work out crop water use</h4>'
        '<p>Daily weather gives reference evapotranspiration, which is scaled by the crop coefficient for each growth stage.</p></div>'
        '<div><div class="n">3</div><h4>Get your irrigation calendar</h4>'
        '<p>A daily soil water balance shows which dates to irrigate and how many millimetres to apply.</p></div>'
        '</div>'
        '<p class="fine" style="margin-top:1.2rem">No internet connection? Choose Demo data in the sidebar to try the tool. '
        'Demo weather is synthetic and only for testing.</p>',
        unsafe_allow_html=True)


def _fmt_date(d) -> str:
    return pd.Timestamp(d).strftime("%d %b").lstrip("0")


def season_ribbon(daily: pd.DataFrame, events: pd.DataFrame) -> str:
    """HTML for the growth-stage ribbon with a pin on each irrigation date."""
    n = len(daily)
    stage_days = daily["stage"].value_counts(sort=False)
    order = [s for s in STAGE_COLORS if s in stage_days.index]
    segs = []
    for s in order:
        bg, fg = STAGE_COLORS[s]
        label = s if stage_days[s] / n > 0.12 else ""
        segs.append(f'<div class="seg" style="flex:{int(stage_days[s])};background:{bg};color:{fg}" '
                    f'title="{escape(s)}: {int(stage_days[s])} days">{escape(label)}</div>')
    pins = []
    show_text = len(events) <= 6
    for _, r in events.iterrows():
        pct = (float(r["day_after_sowing"]) - 0.5) / n * 100
        left = max(4.0, min(96.0, pct))
        tip = (f'Day {int(r["day_after_sowing"])}, {_fmt_date(r["date"])}: '
               f'{r["gross_mm"]:.0f} mm gross ({r["net_mm"]:.0f} mm net)')
        text = (f'<div class="pin-text"><b>{_fmt_date(r["date"])}</b>{r["gross_mm"]:.0f} mm</div>'
                if show_text else "")
        pins.append(f'<div class="pin" style="left:{left:.2f}%" title="{escape(tip)}">{text}'
                    f'<div class="pin-drop"></div></div>')
    return (
        '<div class="ribbon-wrap">'
        '<div class="ribbon-title">Growing season with irrigation dates</div>'
        f'<div class="ribbon-marks">{"".join(pins)}</div>'
        f'<div class="ribbon">{"".join(segs)}</div>'
        f'<div class="ribbon-axis"><span>Sown {_fmt_date(daily.index[0])}</span>'
        f'<span>Harvest {_fmt_date(daily.index[-1])}</span></div>'
        '</div>')


def answer_card(res) -> None:
    """The headline: when to irrigate next, how much, and the season at a glance."""
    s, ev, daily = res.summary, res.events, res.daily
    if len(ev):
        f = ev.iloc[0]
        date_txt = pd.Timestamp(f["date"]).strftime("%d %b %Y").lstrip("0")
        kicker = "First irrigation"
        sub = (f'Day {int(f["day_after_sowing"])} after sowing, in the {escape(str(f["stage"]).lower())} stage. '
               f'Apply about <b>{f["gross_mm"]:.0f} mm</b> at the field inlet '
               f'({f["net_mm"]:.0f} mm reaches the root zone). '
               f'The season needs <b>{s["n_irrigations"]} irrigation{"s" if s["n_irrigations"] != 1 else ""}</b>, '
               f'<b>{s["gross_irrigation_mm"]:.0f} mm</b> in total.')
    else:
        date_txt = "No irrigation needed"
        kicker = "This season"
        sub = (f'Rainfall of {s["eff_rain_total_mm"]:.0f} mm (effective) covers the crop\'s water use '
               f'of {s["etc_total_mm"]:.0f} mm under these settings.')
    st.markdown(
        f'<div class="answer"><div class="answer-kicker">{kicker}</div>'
        f'<div class="answer-date">{escape(date_txt)}</div>'
        f'<div class="answer-sub">{sub}</div>'
        f'{season_ribbon(daily, ev)}</div>',
        unsafe_allow_html=True)


def footer() -> None:
    st.markdown(
        '<p class="fine">Weather data from NASA POWER (gridded, about 50 km). Method: Allen, Pereira, Raes and '
        'Smith (1998), FAO Irrigation and Drainage Paper 56. Crop and soil values are typical, so replace them '
        'with local data before using results for field decisions.</p>',
        unsafe_allow_html=True)
