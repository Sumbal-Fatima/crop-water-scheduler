"""Climatology (typical-year weather) and simple climate-change scenarios."""
from __future__ import annotations

import numpy as np
import pandas as pd


def apply_scenario(raw: pd.DataFrame, delta_t: float = 0.0, rain_factor: float = 1.0) -> pd.DataFrame:
    """Return a copy of the weather with a uniform warming and rainfall change.

    delta_t     : added to Tmax and Tmin (deg C)
    rain_factor : multiplier on daily rainfall (1.0 = unchanged, 0.8 = 20 % drier)

    Relative humidity, wind and solar radiation are kept unchanged, so vapour
    pressure deficit rises with temperature (as it does when RH stays constant).
    This is a simple sensitivity analysis, not a downscaled climate projection.
    """
    out = raw.copy()
    out["tmax"] = out["tmax"] + delta_t
    out["tmin"] = out["tmin"] + delta_t
    out["rain"] = out["rain"] * rain_factor
    return out


def _circular_smooth(values: np.ndarray, window: int) -> np.ndarray:
    """Centered moving average that wraps around the end of the year."""
    if window <= 1:
        return values
    if window % 2 == 0:
        window += 1
    k = window // 2
    ext = np.concatenate([values[-k:], values, values[:k]])
    return np.convolve(ext, np.ones(window) / window, mode="valid")


def climatology(daily: pd.DataFrame, et0_window: int = 7, rain_window: int = 31,
                stat: str = "median") -> pd.DataFrame:
    """Typical-year ET0 and rainfall for each day of year (1..366).

    `daily` must be indexed by date with columns `et0` and `rain`.

    Method: each calendar year is first smoothed on its own (ET0 over
    `et0_window` days, rainfall over `rain_window` days, wrapping at year end);
    then the value for each day of year is taken across years with `stat`.

    stat = "median" (default): robust "typical year". A single extreme wet year
        (or a bad value in gridded rainfall) cannot dominate, and no artificial
        flat steps appear. This is the right choice for planning irrigation,
        because mean rainfall in dry climates is pulled upwards by rare floods
        that the crop cannot rely on.
    stat = "mean": long-term average (includes the rare wet years).
    """
    if stat not in ("median", "mean"):
        raise ValueError("stat must be 'median' or 'mean'")
    d = daily[["et0", "rain"]].dropna()
    if d.empty:
        raise ValueError("No data available to build a climatology.")

    per_year = {}
    for col, window in (("et0", et0_window), ("rain", rain_window)):
        rows = []
        for _, g in d.groupby(d.index.year):
            s = g[col].groupby(g.index.dayofyear).mean().reindex(range(1, 367))
            if s.notna().sum() < 300:          # skip incomplete years
                continue
            s = s.interpolate(limit_direction="both")
            rows.append(_circular_smooth(s.to_numpy(), window))
        if not rows:                           # fewer than one complete year of data
            s = d[col].groupby(d.index.dayofyear).mean().reindex(range(1, 367))
            s = s.interpolate(limit_direction="both")
            rows.append(_circular_smooth(s.to_numpy(), window))
        arr = np.vstack(rows)
        per_year[col] = np.median(arr, axis=0) if stat == "median" else arr.mean(axis=0)

    out = pd.DataFrame(per_year, index=pd.RangeIndex(1, 367, name="doy"))
    return out


def rainfall_outlier_years(season_rain: pd.Series, factor: float = 3.0,
                           min_mm: float = 150.0) -> list[int]:
    """Years whose season rainfall is suspiciously large compared with the median.

    `season_rain` is indexed by year. A year is flagged when it exceeds both
    `factor` x the median and `min_mm`. Gridded rainfall products (NASA POWER,
    ERA5) can contain very large values; flagged years deserve a check against a
    local station before the numbers are trusted.
    """
    s = season_rain.dropna()
    if len(s) < 4:
        return []
    med = float(s.median())
    return [int(y) for y, v in s.items() if v > factor * max(med, 1.0) and v > min_mm]
