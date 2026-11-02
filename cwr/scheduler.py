"""Daily root-zone water balance and irrigation scheduling (FAO-56 Ch. 8).

Root-zone depletion Dr (mm below field capacity):

    Dr,i = Dr,i-1 - Peff,i - I,i + ETa,i + DP,i

    TAW  = 1000 (theta_fc - theta_wp) Zr              total available water (mm)
    p    = p_table + 0.04 (5 - ETc)  (limited 0.1-0.8)  allowable depletion fraction
    RAW  = p TAW                                      readily available water (mm)
    Ks   = 1                          if Dr <= RAW
         = (TAW - Dr) / ((1 - p) TAW) otherwise       stress coefficient
    ETc  = Kc ET0                      ETa = Ks ETc

Irrigation rule: irrigate on the first day the end-of-day depletion would exceed
RAW, refilling the root zone to field capacity (or a fixed net depth if given).
Gross irrigation = net / application efficiency.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from .crops import Crop, kc_curve, root_depth_curve, stage_names
from .soils import Soil

M3_PER_HA_PER_MM = 10.0
M3_PER_ACRE_PER_MM = 4.0469     # 1 mm over 1 acre = 4.0469 m3


@dataclass
class ScheduleResult:
    daily: pd.DataFrame
    events: pd.DataFrame
    summary: dict


def season_weather_slice(weather: pd.DataFrame, sowing: date, days: int) -> pd.DataFrame:
    """Return exactly `days` rows of weather starting at the sowing date."""
    idx = pd.date_range(pd.Timestamp(sowing), periods=days, freq="D")
    w = weather.loc[idx[0]:idx[-1]]
    start, end = idx[0], idx[-1]
    if len(w) != days:
        raise ValueError(
            f"Weather covers {len(w)} of the {days} season days "
            f"({start.date()} to {end.date()}). Extend the weather series."
        )
    return w


def run_schedule(weather: pd.DataFrame, crop: Crop, soil: Soil, sowing: date, *,
                 irrigate: bool = True,
                 eff_rain: float = 0.8,
                 application_efficiency: float = 0.7,
                 p_override: float | None = None,
                 initial_depletion_fraction: float = 0.0,
                 irrigation_depth_mm: float | None = None,
                 min_depth_mm: float = 5.0) -> ScheduleResult:
    """Simulate one crop season.

    Parameters
    ----------
    weather : DataFrame indexed by date with columns `et0` and `rain` (mm/day)
    eff_rain : fraction of rainfall that enters the root zone (rest is runoff /
               interception). Water above field capacity is lost as deep percolation.
    application_efficiency : net/gross ratio (drip ~0.9, sprinkler ~0.75,
               furrow ~0.6, basin/flood ~0.5)
    p_override : fixed depletion fraction instead of the table value
    initial_depletion_fraction : share of TAW already depleted at sowing
               (0 = profile at field capacity, e.g. after pre-sowing irrigation)
    irrigation_depth_mm : fixed *net* depth per irrigation; None = refill to field capacity
    min_depth_mm : irrigations smaller than this are skipped
    irrigate : False gives the rainfed (no irrigation) scenario and the stress it causes
    """
    n = crop.season_days
    w = season_weather_slice(weather, sowing, n)
    et0 = w["et0"].to_numpy(float)
    rain = w["rain"].to_numpy(float)
    kc = kc_curve(crop)
    zr = root_depth_curve(crop)
    stages = stage_names(crop)
    awc = soil.awc_mm_per_m / 1000.0            # m3/m3 available water
    if awc <= 0:
        raise ValueError("Soil field capacity must exceed wilting point.")

    cols = {k: np.zeros(n) for k in
            ["etc", "eta", "ks", "peff", "irr_net", "irr_gross", "dp", "dr", "taw", "raw", "p"]}
    dr_prev = initial_depletion_fraction * 1000.0 * awc * zr[0]

    for i in range(n):
        taw = 1000.0 * awc * zr[i]
        etc = kc[i] * et0[i]
        p = p_override if p_override is not None else crop.p + 0.04 * (5.0 - etc)
        p = float(np.clip(p, 0.1, 0.8))
        raw = p * taw
        dr0 = min(dr_prev, taw)
        ks = 1.0 if dr0 <= raw else max(0.0, (taw - dr0) / ((1.0 - p) * taw))
        eta = ks * etc
        peff = eff_rain * rain[i]

        dr_t = dr0 - peff + eta                 # before irrigation / drainage
        irr = 0.0
        if irrigate and dr_t > raw:
            need = dr_t if irrigation_depth_mm is None else irrigation_depth_mm
            if need >= min_depth_mm:
                irr = need
        dr_new = dr_t - irr
        dp = 0.0
        if dr_new < 0.0:                        # excess water drains below the root zone
            dp, dr_new = -dr_new, 0.0
        if dr_new > taw:                        # cannot deplete below wilting point
            eta -= dr_new - taw
            dr_new = taw

        cols["etc"][i], cols["eta"][i], cols["ks"][i] = etc, eta, ks
        cols["peff"][i], cols["irr_net"][i] = peff, irr
        cols["irr_gross"][i] = irr / application_efficiency if irr else 0.0
        cols["dp"][i], cols["dr"][i] = dp, dr_new
        cols["taw"][i], cols["raw"][i], cols["p"][i] = taw, raw, p
        dr_prev = dr_new

    daily = pd.DataFrame(
        {"day_after_sowing": np.arange(1, n + 1), "stage": stages, "kc": kc, "zr_m": zr,
         "et0": et0, "etc": cols["etc"], "eta": cols["eta"], "ks": cols["ks"],
         "rain": rain, "eff_rain": cols["peff"],
         "irrigation_net": cols["irr_net"], "irrigation_gross": cols["irr_gross"],
         "deep_percolation": cols["dp"], "depletion": cols["dr"],
         "taw": cols["taw"], "raw": cols["raw"], "p": cols["p"]},
        index=w.index,
    )
    if "source" in w:
        daily["weather_source"] = w["source"].to_numpy()
    daily.index.name = "date"
    daily["initial_depletion"] = np.nan
    daily.iloc[0, daily.columns.get_loc("initial_depletion")] = (
        initial_depletion_fraction * 1000.0 * awc * zr[0])

    events = _build_events(daily)
    summary = _summarise(daily, events, crop, soil, irrigate)
    return ScheduleResult(daily=daily, events=events, summary=summary)


def _build_events(daily: pd.DataFrame) -> pd.DataFrame:
    ev = daily[daily["irrigation_net"] > 0].copy()
    if ev.empty:
        return pd.DataFrame(columns=["date", "day_after_sowing", "stage", "net_mm", "gross_mm",
                                     "m3_per_ha", "m3_per_acre", "days_since_last"])
    out = pd.DataFrame({
        "date": ev.index.date,
        "day_after_sowing": ev["day_after_sowing"].to_numpy(),
        "stage": ev["stage"].to_numpy(),
        "net_mm": ev["irrigation_net"].round(1).to_numpy(),
        "gross_mm": ev["irrigation_gross"].round(1).to_numpy(),
        "m3_per_ha": (ev["irrigation_gross"] * M3_PER_HA_PER_MM).round(0).to_numpy(),
        "m3_per_acre": (ev["irrigation_gross"] * M3_PER_ACRE_PER_MM).round(0).to_numpy(),
    })
    out["days_since_last"] = out["day_after_sowing"].diff()
    return out.reset_index(drop=True)


def _summarise(daily: pd.DataFrame, events: pd.DataFrame, crop: Crop, soil: Soil,
               irrigate: bool) -> dict:
    etc_total = float(daily["etc"].sum())
    eta_total = float(daily["eta"].sum())
    gross = float(daily["irrigation_gross"].sum())
    net = float(daily["irrigation_net"].sum())
    summary = {
        "crop": crop.name,
        "soil": soil.name,
        "season_days": int(len(daily)),
        "sowing_date": daily.index[0].date(),
        "harvest_date": daily.index[-1].date(),
        "et0_total_mm": round(float(daily["et0"].sum()), 1),
        "etc_total_mm": round(etc_total, 1),
        "eta_total_mm": round(eta_total, 1),
        "rain_total_mm": round(float(daily["rain"].sum()), 1),
        "eff_rain_total_mm": round(float(daily["eff_rain"].sum()), 1),
        "net_irrigation_mm": round(net, 1),
        "gross_irrigation_mm": round(gross, 1),
        "n_irrigations": int(len(events)),
        "mean_interval_days": (round(float(events["days_since_last"].mean()), 1)
                               if len(events) > 1 else None),
        "deep_percolation_mm": round(float(daily["deep_percolation"].sum()), 1),
        "stress_days": int((daily["ks"] < 0.999).sum()),
        "eta_etc_ratio": round(eta_total / etc_total, 3) if etc_total > 0 else 1.0,
        "gross_m3_per_ha": round(gross * M3_PER_HA_PER_MM, 0),
        "gross_m3_per_acre": round(gross * M3_PER_ACRE_PER_MM, 0),
        "irrigated": irrigate,
    }
    if "weather_source" in daily:
        summary["days_from_climatology"] = int((daily["weather_source"] == "climatology").sum())
    return summary


def run_ensemble(daily_weather: pd.DataFrame, crop: Crop, soil: Soil, month: int, day: int,
                 years: list[int], **kwargs) -> pd.DataFrame:
    """Run the same sowing calendar date in each historical year.

    Shows how much the seasonal irrigation demand varies from wet to dry years.
    Years whose season is not fully covered by observed data are skipped.
    """
    rows = []
    for y in years:
        try:
            sow = date(y, month, day)
        except ValueError:                       # 29 Feb in non-leap year
            sow = date(y, month, 28)
        try:
            res = run_schedule(daily_weather, crop, soil, sow, **kwargs)
        except ValueError:
            continue
        s = res.summary
        rows.append({"sowing_year": y, "sowing_date": sow, "et0_mm": s["et0_total_mm"],
                     "etc_mm": s["etc_total_mm"], "rain_mm": s["rain_total_mm"],
                     "net_irrigation_mm": s["net_irrigation_mm"],
                     "gross_irrigation_mm": s["gross_irrigation_mm"],
                     "n_irrigations": s["n_irrigations"]})
    return pd.DataFrame(rows)
