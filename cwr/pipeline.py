"""Glue code: raw weather -> ET0 -> season weather (observed + climatology)."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from .climate import apply_scenario, climatology
from .et0 import et0_from_dataframe


def compute_daily(raw: pd.DataFrame, lat: float, elevation_m: float,
                  delta_t: float = 0.0, rain_factor: float = 1.0) -> pd.DataFrame:
    """Apply an optional climate scenario and compute daily ET0.

    Returns a DataFrame indexed by date with columns et0, rain, tmax, tmin.
    """
    scen = apply_scenario(raw, delta_t, rain_factor) if (delta_t or rain_factor != 1.0) else raw
    et0 = et0_from_dataframe(scen, lat, elevation_m)
    out = pd.DataFrame({"et0": et0, "rain": scen["rain"],
                        "tmax": scen["tmax"], "tmin": scen["tmin"]})
    out.index.name = "date"
    return out


def season_frame(daily: pd.DataFrame, clim: pd.DataFrame, start: date, days: int) -> pd.DataFrame:
    """Weather for one season: observed values where available, otherwise
    the multi-year climatological mean (flagged in the `source` column)."""
    idx = pd.date_range(pd.Timestamp(start), periods=days, freq="D")
    out = pd.DataFrame(index=idx)
    out["et0"] = daily["et0"].reindex(idx)
    out["rain"] = daily["rain"].reindex(idx)
    missing = out["et0"].isna() | out["rain"].isna()
    doy = idx.dayofyear
    out.loc[missing, "et0"] = clim["et0"].reindex(doy[missing]).to_numpy()
    out.loc[missing, "rain"] = clim["rain"].reindex(doy[missing]).to_numpy()
    out["source"] = np.where(missing, "climatology", "observed")
    out.index.name = "date"
    return out


def build_climatology(daily: pd.DataFrame) -> pd.DataFrame:
    return climatology(daily)
