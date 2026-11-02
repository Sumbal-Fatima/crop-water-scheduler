"""Weather data access.

Sources
-------
* NASA POWER daily API (free, no key, global, 1981-near real time)
* User-supplied CSV
* A clearly-labelled synthetic generator for offline demos / tests ONLY

NASA POWER "AG" community variables used
    T2M_MAX, T2M_MIN      air temperature at 2 m (deg C)
    RH2M                  mean relative humidity at 2 m (%)
    WS2M                  wind speed at 2 m (m/s)
    ALLSKY_SFC_SW_DWN     all-sky surface shortwave radiation (MJ m-2 day-1)
    PRECTOTCORR           bias-corrected precipitation (mm/day)
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .et0 import extraterrestrial_radiation

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMS = {
    "T2M_MAX": "tmax",
    "T2M_MIN": "tmin",
    "RH2M": "rh",
    "WS2M": "wind",
    "ALLSKY_SFC_SW_DWN": "rs",
    "PRECTOTCORR": "rain",
}
FILL_VALUE = -999.0
CACHE_DIR = Path(".cache") / "nasa_power"
# Data newer than this many days may still be revised / incomplete, so it is
# not cached on disk.
LATENCY_DAYS = 15


class WeatherDataError(RuntimeError):
    """Raised when weather data cannot be retrieved or parsed."""


# --------------------------------------------------------------------------- #
# NASA POWER
# --------------------------------------------------------------------------- #
def parse_power_json(payload: dict) -> tuple[pd.DataFrame, float | None]:
    """Convert a NASA POWER JSON response into (DataFrame, elevation_m)."""
    try:
        params = payload["properties"]["parameter"]
    except (KeyError, TypeError) as exc:
        raise WeatherDataError(f"Unexpected NASA POWER response: {str(payload)[:200]}") from exc
    cols = {}
    for api_name, short in PARAMS.items():
        if api_name not in params:
            raise WeatherDataError(f"NASA POWER response lacks parameter {api_name}")
        cols[short] = pd.Series(params[api_name], dtype=float)
    df = pd.DataFrame(cols)
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df.index.name = "date"
    df = df.sort_index().replace(FILL_VALUE, np.nan)
    elevation = None
    try:
        elevation = float(payload["geometry"]["coordinates"][2])
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return df, elevation


def _request_power(lat: float, lon: float, start: date, end: date, retries: int = 3) -> dict:
    query = {
        "parameters": ",".join(PARAMS),
        "community": "AG",
        "longitude": f"{lon:.4f}",
        "latitude": f"{lat:.4f}",
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(POWER_URL, params=query, timeout=60)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            last_err = exc
            time.sleep(1.5 * (attempt + 1))
    raise WeatherDataError(f"Could not reach NASA POWER after {retries} attempts: {last_err}")


def fetch_nasa_power(lat: float, lon: float, start: date, end: date,
                     use_cache: bool = True) -> tuple[pd.DataFrame, float | None]:
    """Download daily weather for a point, one calendar year per request.

    Completed years are cached on disk (`.cache/nasa_power`) so repeated runs
    are fast and work offline.
    """
    today = date.today()
    end = min(end, today)
    if start > end:
        raise WeatherDataError("Start date is after the last available date.")
    frames, elevation = [], None
    for year in range(start.year, end.year + 1):
        y0, y1 = max(start, date(year, 1, 1)), min(end, date(year, 12, 31))
        full_year = (y0 == date(year, 1, 1)) and (y1 == date(year, 12, 31))
        cacheable = use_cache and full_year and (y1 < today - timedelta(days=LATENCY_DAYS))
        cache_file = CACHE_DIR / f"{lat:.3f}_{lon:.3f}_{year}.json"
        payload = None
        if cacheable and cache_file.exists():
            try:
                payload = json.loads(cache_file.read_text())
            except (OSError, ValueError):
                payload = None
        if payload is None:
            payload = _request_power(lat, lon, y0, y1)
            if cacheable:
                try:
                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    cache_file.write_text(json.dumps(payload))
                except OSError:
                    pass
        df, elev = parse_power_json(payload)
        elevation = elevation if elevation is not None else elev
        frames.append(df)
    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out, elevation


# --------------------------------------------------------------------------- #
# CSV upload
# --------------------------------------------------------------------------- #
_ALIASES = {
    "date": ["date", "datetime", "day"],
    "tmax": ["tmax", "t_max", "tmax_c", "t2m_max", "temp_max"],
    "tmin": ["tmin", "t_min", "tmin_c", "t2m_min", "temp_min"],
    "rh": ["rh", "rh_mean", "humidity", "rh2m", "rhmean"],
    "wind": ["wind", "u2", "ws2m", "wind_speed", "windspeed"],
    "rs": ["rs", "solar", "srad", "radiation", "allsky_sfc_sw_dwn"],
    "rain": ["rain", "precip", "precipitation", "prectotcorr", "rainfall"],
}


def load_weather_csv(file, wind_height_m: float = 2.0) -> pd.DataFrame:
    """Read a CSV with daily weather. Column names are matched case-insensitively.

    Required: date, tmax, tmin, rh (mean %), wind (m/s), rain (mm)
    Optional: rs (MJ m-2 day-1; Hargreaves estimate is used where missing)
    If wind was measured at a height other than 2 m, pass `wind_height_m`.
    """
    from .et0 import wind_at_2m

    raw = pd.read_csv(file)
    lower = {c.lower().strip(): c for c in raw.columns}
    rename = {}
    for std, names in _ALIASES.items():
        for n in names:
            if n in lower:
                rename[lower[n]] = std
                break
    df = raw.rename(columns=rename)
    required = ["date", "tmax", "tmin", "rh", "wind", "rain"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise WeatherDataError(f"CSV is missing column(s): {', '.join(missing)}")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    keep = [c for c in ["tmax", "tmin", "rh", "wind", "rs", "rain"] if c in df.columns]
    df = df[keep].apply(pd.to_numeric, errors="coerce").replace(FILL_VALUE, np.nan)
    if wind_height_m != 2.0:
        df["wind"] = wind_at_2m(df["wind"], wind_height_m)
    if "rs" not in df.columns:
        df["rs"] = np.nan
    return df


# --------------------------------------------------------------------------- #
# Cleaning
# --------------------------------------------------------------------------- #
def clean_weather(df: pd.DataFrame) -> pd.DataFrame:
    """Put the data on a continuous daily index, fill short gaps, drop the rest.

    * gaps up to 5 days in temperature / RH / wind / radiation are interpolated
    * rows still missing temperature, RH or wind are dropped (the pipeline then
      fills those days from climatology and flags them)
    * missing rainfall on a valid day is treated as 0 mm
    * physically impossible values are clipped
    """
    d = df.copy()
    d = d[~d.index.duplicated(keep="last")].sort_index()
    d = d.reindex(pd.date_range(d.index.min(), d.index.max(), freq="D"))
    d.index.name = "date"
    for c in ["tmax", "tmin", "rh", "wind", "rs"]:
        if c in d:
            d[c] = d[c].interpolate(limit=5, limit_area="inside")
    d = d.dropna(subset=["tmax", "tmin", "rh", "wind"])
    swap = d["tmax"] < d["tmin"]
    if swap.any():
        d.loc[swap, ["tmax", "tmin"]] = d.loc[swap, ["tmin", "tmax"]].values
    d["rh"] = d["rh"].clip(2, 100)
    d["wind"] = d["wind"].clip(lower=0)
    if "rs" in d:
        d["rs"] = d["rs"].clip(lower=0)
    d["rain"] = d["rain"].fillna(0.0).clip(lower=0)
    return d


# --------------------------------------------------------------------------- #
# Synthetic weather - DEMO / TESTS ONLY
# --------------------------------------------------------------------------- #
def synthetic_demo_weather(lat: float, start: date, end: date, seed: int = 42) -> pd.DataFrame:
    """Plausible subtropical-semi-arid weather (Punjab-like). NOT REAL DATA.

    Exists so the app and tests can run without internet. Results computed from
    it must never be reported as real.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, end, freq="D")
    doy = idx.dayofyear.values
    phase = 2 * np.pi * (doy - 200) / 365.0           # peak heat mid-July (N hemisphere)
    sign = 1.0 if lat >= 0 else -1.0
    tmean = 24.0 + sign * 11.0 * np.cos(phase) + rng.normal(0, 1.2, len(idx))
    trange = 13.0 - 3.0 * np.maximum(0, np.sin(2 * np.pi * (doy - 180) / 365)) + rng.normal(0, 0.8, len(idx))
    tmax = tmean + trange / 2
    tmin = tmean - trange / 2
    monsoon = ((doy > 180) & (doy < 260)).astype(float)
    rh = np.clip(45 + 25 * monsoon + rng.normal(0, 8, len(idx)), 15, 95)
    wind = np.clip(1.6 + 0.6 * monsoon + rng.normal(0, 0.4, len(idx)), 0.3, None)
    ra = extraterrestrial_radiation(lat, doy)
    rs = np.clip(ra * (0.72 - 0.20 * monsoon) + rng.normal(0, 1.2, len(idx)), 2, None)
    wet = rng.random(len(idx)) < (0.04 + 0.30 * monsoon)
    rain = np.where(wet, rng.gamma(0.9, 9.0, len(idx)), 0.0)
    return pd.DataFrame({"tmax": tmax, "tmin": tmin, "rh": rh, "wind": wind,
                         "rs": rs, "rain": rain}, index=pd.DatetimeIndex(idx, name="date"))
