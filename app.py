"""Crop Water Requirement & Irrigation Scheduling Tool - Streamlit app.

Run:  streamlit run app.py
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from cwr import CROPS, SOILS, compute_daily, run_ensemble, run_schedule, season_frame
from cwr.climate import climatology, rainfall_outlier_years
from cwr.crops import kc_curve
from cwr.plots import fig_ensemble, fig_kc, fig_soil_water, fig_water_demand
from cwr.report import build_pdf
from cwr.soils import Soil
from cwr.weather import (WeatherDataError, clean_weather, fetch_nasa_power,
                         load_weather_csv, synthetic_demo_weather)

st.set_page_config(page_title="Crop Water & Irrigation Scheduler", page_icon="💧", layout="wide")

PRESET_LOCATIONS = {
    "Khanewal, Punjab": (30.30, 71.93),
    "Faisalabad, Punjab": (31.42, 73.08),
    "Multan, Punjab": (30.20, 71.47),
    "Lahore, Punjab": (31.52, 74.36),
    "Hyderabad, Sindh": (25.39, 68.37),
    "Peshawar, KP": (34.01, 71.58),
    "Custom coordinates": (None, None),
}
EFFICIENCY_PRESETS = {
    "Drip (0.90)": 0.90, "Sprinkler (0.75)": 0.75, "Furrow (0.60)": 0.60,
    "Basin / flood (0.50)": 0.50, "Custom": None,
}
HISTORY_YEARS = 10


def show_plot(fig):
    try:
        st.plotly_chart(fig, width="stretch")
    except TypeError:                      # older Streamlit
        st.plotly_chart(fig, use_container_width=True)


def show_df(df, **kw):
    try:
        st.dataframe(df, width="stretch", hide_index=True, **kw)
    except TypeError:
        st.dataframe(df, use_container_width=True, hide_index=True, **kw)


@st.cache_data(show_spinner=False, ttl=6 * 3600)
def load_nasa(lat: float, lon: float, first_year: int):
    raw, elev = fetch_nasa_power(lat, lon, date(first_year, 1, 1), date.today())
    return clean_weather(raw), elev


@st.cache_data(show_spinner=False)
def load_demo(lat: float, first_year: int):
    raw = synthetic_demo_weather(lat, date(first_year, 1, 1), date.today() - timedelta(days=6))
    return clean_weather(raw), 128.0


# --------------------------------------------------------------------------- #
# Sidebar - inputs
# --------------------------------------------------------------------------- #
st.title("💧 Crop Water Requirement & Irrigation Scheduling")
st.caption("FAO-56 Penman-Monteith ET0 · single crop coefficient · daily root-zone water balance · "
           "NASA POWER weather")

with st.sidebar:
    st.header("1. Location & weather")
    preset = st.selectbox("Location", list(PRESET_LOCATIONS), key="preset")
    lat0, lon0 = PRESET_LOCATIONS[preset]
    lat = st.number_input("Latitude (°N)", -60.0, 70.0, lat0 if lat0 is not None else 30.30,
                          step=0.01, format="%.2f", key="lat", disabled=lat0 is not None)
    lon = st.number_input("Longitude (°E)", -180.0, 180.0, lon0 if lon0 is not None else 71.93,
                          step=0.01, format="%.2f", key="lon", disabled=lon0 is not None)
    if lat0 is not None:
        lat, lon = lat0, lon0
    source = st.radio("Weather source", ["NASA POWER (online)", "Upload CSV",
                                         "Demo data (synthetic, offline)"], key="source")
    csv_file, wind_h, csv_elev = None, 2.0, 100.0
    if source == "Upload CSV":
        csv_file = st.file_uploader("Daily weather CSV", type="csv")
        st.caption("Columns: date, tmax, tmin, rh (mean %), wind (m/s), rain (mm); optional rs "
                   "(MJ/m²/day).")
        wind_h = st.number_input("Wind measurement height (m)", 0.5, 20.0, 2.0, 0.5)
        csv_elev = st.number_input("Elevation (m)", -100.0, 5000.0, 100.0, 10.0)

    st.header("2. Crop & soil")
    crop_name = st.selectbox("Crop", list(CROPS), key="crop")
    base_crop = CROPS[crop_name]
    sowing = st.date_input("Sowing / transplanting date", value=date(date.today().year, 11, 15)
                           if date.today().month >= 10 else date.today(), key="sowing")
    soil_name = st.selectbox("Soil texture", list(SOILS) + ["Custom"], index=3, key="soil")
    if soil_name == "Custom":
        c1, c2 = st.columns(2)
        fc = c1.number_input("θ field cap.", 0.05, 0.60, 0.28, 0.01)
        wp = c2.number_input("θ wilting pt.", 0.01, 0.40, 0.14, 0.01)
        soil = Soil("Custom", fc, wp)
    else:
        soil = SOILS[soil_name]

    with st.expander("Edit crop parameters"):
        st.caption("Typical FAO-56 values - replace with local data if you have it.")
        a, b, c = st.columns(3)
        kc_ini = a.number_input("Kc ini", 0.05, 1.5, base_crop.kc_ini, 0.05, key=f"kci_{crop_name}")
        kc_mid = b.number_input("Kc mid", 0.2, 1.8, base_crop.kc_mid, 0.05, key=f"kcm_{crop_name}")
        kc_end = c.number_input("Kc end", 0.05, 1.5, base_crop.kc_end, 0.05, key=f"kce_{crop_name}")
        a, b, c, d = st.columns(4)
        l_ini = a.number_input("L ini", 1, 120, base_crop.l_ini, key=f"li_{crop_name}")
        l_dev = b.number_input("L dev", 1, 200, base_crop.l_dev, key=f"ld_{crop_name}")
        l_mid = c.number_input("L mid", 1, 300, base_crop.l_mid, key=f"lm_{crop_name}")
        l_late = d.number_input("L late", 1, 200, base_crop.l_late, key=f"ll_{crop_name}")
        a, b, c = st.columns(3)
        zr_ini = a.number_input("Zr ini (m)", 0.05, 1.0, base_crop.zr_ini, 0.05, key=f"zi_{crop_name}")
        zr_max = b.number_input("Zr max (m)", 0.1, 3.0, base_crop.zr_max, 0.05, key=f"zm_{crop_name}")
        p_dep = c.number_input("p (depletion)", 0.1, 0.8, base_crop.p, 0.05, key=f"p_{crop_name}")
    crop = base_crop.with_changes(kc_ini=kc_ini, kc_mid=kc_mid, kc_end=kc_end, l_ini=int(l_ini),
                                  l_dev=int(l_dev), l_mid=int(l_mid), l_late=int(l_late),
                                  zr_ini=zr_ini, zr_max=max(zr_max, zr_ini), p=p_dep)
    if base_crop.note:
        st.caption(f"ℹ️ {base_crop.note}")

    st.header("3. Irrigation management")
    eff_label = st.selectbox("Irrigation method (application efficiency)", list(EFFICIENCY_PRESETS), index=2)
    eff_val = EFFICIENCY_PRESETS[eff_label]
    app_eff = eff_val if eff_val is not None else st.slider("Application efficiency", 0.3, 1.0, 0.65, 0.05)
    eff_rain = st.slider("Effective rainfall (share of rain that enters root zone)", 0.3, 1.0, 0.8, 0.05)
    init_dep = st.slider("Soil already depleted at sowing (share of TAW)", 0.0, 1.0, 0.0, 0.05,
                         help="0 = soil at field capacity (e.g. after a pre-sowing irrigation).")
    fixed = st.checkbox("Fixed irrigation depth instead of refilling to field capacity")
    fixed_depth = st.number_input("Net depth per irrigation (mm)", 10.0, 200.0, 60.0, 5.0) if fixed else None

    st.header("4. Climate scenario (optional)")
    d_t = st.slider("Warming added to Tmax and Tmin (°C)", 0.0, 5.0, 0.0, 0.5)
    r_f = st.slider("Rainfall change (%)", -50, 50, 0, 5)

    run = st.button("Calculate", type="primary")

# --------------------------------------------------------------------------- #
# Calculation
# --------------------------------------------------------------------------- #
if run:
    st.session_state["go"] = True
if not st.session_state.get("go"):
    st.info("Set up your field in the sidebar and press **Calculate**. Choose *Demo data* to try the "
            "tool without internet (synthetic weather, for testing only).")
    c1, c2, c3 = st.columns(3)
    c1.markdown("**1. Weather** → NASA POWER daily data for your coordinates.")
    c2.markdown("**2. ET0** → FAO-56 Penman-Monteith, then ETc = Kc × ET0.")
    c3.markdown("**3. Schedule** → daily soil water balance tells you when and how much to irrigate.")
    st.stop()

first_year = date.today().year - HISTORY_YEARS
try:
    with st.spinner("Fetching weather and running the water balance..."):
        if source == "NASA POWER (online)":
            raw, elevation = load_nasa(round(lat, 3), round(lon, 3), first_year)
            data_label = "NASA POWER (AG community)"
        elif source == "Upload CSV":
            if csv_file is None:
                st.warning("Upload a CSV file first.")
                st.stop()
            raw, elevation = clean_weather(load_weather_csv(csv_file, wind_h)), csv_elev
            data_label = "User CSV"
        else:
            raw, elevation = load_demo(round(lat, 2), first_year)
            data_label = "SYNTHETIC DEMO DATA - not real"
        daily = compute_daily(raw, lat, elevation, delta_t=d_t, rain_factor=1 + r_f / 100)
        last_obs = daily.index.max().date()
        clim = climatology(daily)
        season = season_frame(daily, clim, sowing, crop.season_days)
        kw = dict(eff_rain=eff_rain, application_efficiency=app_eff, initial_depletion_fraction=init_dep,
                  irrigation_depth_mm=fixed_depth)
        res = run_schedule(season, crop, soil, sowing, **kw)
        rainfed = run_schedule(season, crop, soil, sowing, irrigate=False, **{**kw, "irrigation_depth_mm": None})
        years = sorted({y for y in range(daily.index.min().year, daily.index.max().year + 1)})
        ens = run_ensemble(daily, crop, soil, sowing.month, sowing.day, years, **kw)
except WeatherDataError as exc:
    st.error(f"Weather data problem: {exc}")
    st.info("Tip: pick *Upload CSV* or *Demo data*, or try again in a minute.")
    st.stop()
except Exception as exc:  # noqa: BLE001 - show a readable message in the UI
    st.error(f"Could not complete the calculation: {exc}")
    st.stop()

s = res.summary
if source.startswith("Demo"):
    st.warning("⚠️ You are viewing **synthetic demo weather**. Do not use these numbers for real decisions.")
if s.get("days_from_climatology"):
    st.info(f"Weather is observed until **{last_obs:%d %b %Y}**. The remaining "
            f"**{s['days_from_climatology']} season days** use a typical year (the median of the last "
            f"{HISTORY_YEARS} years for that calendar day). See the *Other years* tab for the range.")
if d_t or r_f:
    st.info(f"Climate scenario active: +{d_t} °C, rainfall {r_f:+d} %.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Crop water requirement (ETc)", f"{s['etc_total_mm']:.0f} mm")
m2.metric("Net irrigation requirement", f"{s['net_irrigation_mm']:.0f} mm")
m3.metric("Irrigations", s["n_irrigations"],
          f"every ~{s['mean_interval_days']:.0f} days" if s["mean_interval_days"] else None, delta_color="off")
m4.metric("Gross water (per acre)", f"{s['gross_m3_per_acre']:,.0f} m³",
          f"{s['gross_irrigation_mm']:.0f} mm at the field inlet", delta_color="off")

tab_sched, tab_charts, tab_other, tab_daily, tab_method = st.tabs(
    ["📅 Schedule", "📈 Charts", "📊 Other years", "🧮 Daily table", "📘 Method"])

with tab_sched:
    if len(res.events):
        show_df(res.events.rename(columns={
            "date": "Date", "day_after_sowing": "Days after sowing", "stage": "Growth stage",
            "net_mm": "Net (mm)", "gross_mm": "Gross (mm)", "m3_per_ha": "m³/ha",
            "m3_per_acre": "m³/acre", "days_since_last": "Days since last"}))
        first = res.events.iloc[0]
        st.success(f"First irrigation: **{first['date']:%d %b %Y}** (day {int(first['day_after_sowing'])}) - "
                   f"apply about **{first['gross_mm']:.0f} mm** gross.")
    else:
        st.success("No irrigation needed in this season under the chosen settings.")
    st.markdown(
        f"**Season** {s['sowing_date']:%d %b %Y} → {s['harvest_date']:%d %b %Y} ({s['season_days']} days) · "
        f"rain {s['rain_total_mm']:.0f} mm (effective {s['eff_rain_total_mm']:.0f}) · "
        f"deep percolation {s['deep_percolation_mm']:.0f} mm")
    rs_ = rainfed.summary
    st.caption(f"Without any irrigation, the crop would use only {rs_['eta_etc_ratio']*100:.0f}% of its "
               f"potential water demand and be stressed on {rs_['stress_days']} days.")

with tab_charts:
    show_plot(fig_water_demand(res.daily, res.events))
    show_plot(fig_soil_water(res.daily, res.events))
    show_plot(fig_kc(res.daily))

with tab_other:
    if ens.empty:
        st.info("Not enough complete historical seasons for this sowing date.")
    else:
        show_plot(fig_ensemble(ens, sowing.year if sowing.year in set(ens["sowing_year"]) else None))
        odd = rainfall_outlier_years(ens.set_index("sowing_year")["rain_mm"])
        if odd:
            st.warning(
                f"Season rainfall in {', '.join(map(str, odd))} is far above the other years "
                f"(more than 3x the median). Gridded rainfall can contain very large values, so check "
                f"these years against a local rain gauge before trusting them. The typical-year "
                f"schedule uses the median, so these years do not inflate it.")
        st.markdown(
            f"Across **{len(ens)} past seasons**, gross irrigation ranged from "
            f"**{ens['gross_irrigation_mm'].min():.0f}** to **{ens['gross_irrigation_mm'].max():.0f} mm** "
            f"(median {ens['gross_irrigation_mm'].median():.0f} mm), with "
            f"{int(ens['n_irrigations'].min())}-{int(ens['n_irrigations'].max())} irrigations.")
        show_df(ens.round(1).rename(columns={
            "sowing_year": "Year", "sowing_date": "Sowing", "et0_mm": "ET0 (mm)", "etc_mm": "ETc (mm)",
            "rain_mm": "Rain (mm)", "net_irrigation_mm": "Net irr. (mm)",
            "gross_irrigation_mm": "Gross irr. (mm)", "n_irrigations": "# irrigations"}))

with tab_daily:
    show_df(res.daily.reset_index().round(2))

with tab_method:
    st.markdown("""
**Reference evapotranspiration** - FAO-56 Penman-Monteith (Allen et al., 1998, Eq. 6), computed from daily
Tmax/Tmin, mean relative humidity, 2 m wind, solar radiation and elevation.

**Crop water requirement** - ETc = Kc × ET0 with a four-stage Kc curve (initial, development, mid, late).

**Soil water balance** - Dr,i = Dr,i-1 − Peff − I + ETa + DP, with TAW = 1000(θFC − θWP)·Zr,
RAW = p·TAW, and the stress coefficient Ks = (TAW − Dr)/((1 − p)·TAW) once Dr > RAW.
Irrigation is triggered when depletion would pass RAW and refills the root zone to field capacity
(or applies your fixed depth). Gross = net ÷ application efficiency.
The soil profile is assumed to be at field capacity down to the full rooting depth at sowing (as after a
good pre-sowing irrigation); use the "already depleted at sowing" slider if it is not.

**Data** - NASA POWER daily gridded data (about 50 km resolution). Dates beyond the latest data use a
typical year: for each calendar day, the median of the last 10 years (each year smoothed first), so rare
extreme wet years do not make the forecast too optimistic.

**Limits** - Single-Kc method (no separate soil evaporation), no groundwater contribution, no salinity
leaching requirement, rice puddling and percolation are not modelled, Kc values are typical not local.
Validate against field soil-moisture readings before relying on it for real decisions.
""")

# --------------------------------------------------------------------------- #
# Downloads
# --------------------------------------------------------------------------- #
st.divider()
inputs = {
    "Location": f"{preset} ({lat:.2f}N, {lon:.2f}E), elevation {elevation:.0f} m",
    "Weather data": data_label,
    "Crop": f"{crop.name} - sown {sowing:%d %b %Y}, {crop.season_days} days",
    "Soil": f"{soil.name} (FC {soil.theta_fc:.3f}, WP {soil.theta_wp:.3f})",
    "Irrigation method": f"efficiency {app_eff:.2f}; effective rain {eff_rain:.0%}",
    "Climate scenario": f"+{d_t} C, rainfall {r_f:+d}%" if (d_t or r_f) else "none (observed climate)",
}
d1, d2, d3 = st.columns(3)
d1.download_button("⬇️ Schedule (CSV)", res.events.to_csv(index=False).encode(), "irrigation_schedule.csv",
                   "text/csv")
d2.download_button("⬇️ Daily water balance (CSV)", res.daily.reset_index().to_csv(index=False).encode(),
                   "daily_water_balance.csv", "text/csv")
try:
    pdf = build_pdf(res.summary, res.events, res.daily, inputs)
    d3.download_button("⬇️ Report (PDF)", pdf, "irrigation_report.pdf", "application/pdf")
except Exception as exc:  # noqa: BLE001
    d3.caption(f"PDF unavailable: {exc}")
