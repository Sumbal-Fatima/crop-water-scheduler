"""FAO-56 Penman-Monteith reference evapotranspiration (ET0).

Every function follows Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998),
"Crop evapotranspiration - Guidelines for computing crop water requirements",
FAO Irrigation and Drainage Paper 56. Equation numbers refer to that document.

All functions accept scalars or NumPy arrays and are vectorised.

Units
-----
temperature      deg C
pressure         kPa
radiation        MJ m-2 day-1
wind speed       m s-1 (at 2 m height unless stated)
ET0              mm day-1
"""
from __future__ import annotations

import numpy as np
import pandas as pd

GSC = 0.0820          # solar constant, MJ m-2 min-1
SIGMA = 4.903e-9      # Stefan-Boltzmann constant, MJ K-4 m-2 day-1


def _a(x):
    return np.asarray(x, dtype=float)


# --------------------------------------------------------------------------- #
# Atmospheric parameters
# --------------------------------------------------------------------------- #
def atmospheric_pressure(elevation_m):
    """Eq. 7 - atmospheric pressure (kPa) from elevation (m)."""
    return 101.3 * ((293.0 - 0.0065 * _a(elevation_m)) / 293.0) ** 5.26


def psychrometric_constant(pressure_kpa):
    """Eq. 8 - psychrometric constant (kPa / deg C)."""
    return 0.000665 * _a(pressure_kpa)


# --------------------------------------------------------------------------- #
# Vapour pressure
# --------------------------------------------------------------------------- #
def saturation_vapour_pressure(t):
    """Eq. 11 - saturation vapour pressure e0(T) in kPa."""
    t = _a(t)
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def mean_saturation_vapour_pressure(tmax, tmin):
    """Eq. 12 - mean saturation vapour pressure es (kPa)."""
    return (saturation_vapour_pressure(tmax) + saturation_vapour_pressure(tmin)) / 2.0


def slope_vapour_pressure_curve(t):
    """Eq. 13 - slope of the saturation vapour pressure curve (kPa / deg C)."""
    t = _a(t)
    return 4098.0 * saturation_vapour_pressure(t) / (t + 237.3) ** 2


def actual_vapour_pressure(tmax=None, tmin=None, rh_mean=None,
                           rh_max=None, rh_min=None, tdew=None):
    """Actual vapour pressure ea (kPa).

    Uses the best available humidity data, in the order recommended by FAO-56:
      1. dew point temperature          (Eq. 14)
      2. RHmax and RHmin                (Eq. 17)
      3. mean relative humidity         (Eq. 19)
    """
    if tdew is not None:
        return saturation_vapour_pressure(tdew)
    if rh_max is not None and rh_min is not None:
        return (saturation_vapour_pressure(tmin) * _a(rh_max) / 100.0 +
                saturation_vapour_pressure(tmax) * _a(rh_min) / 100.0) / 2.0
    if rh_mean is not None:
        return _a(rh_mean) / 100.0 * mean_saturation_vapour_pressure(tmax, tmin)
    raise ValueError("Provide tdew, or rh_max and rh_min, or rh_mean.")


# --------------------------------------------------------------------------- #
# Solar geometry and radiation
# --------------------------------------------------------------------------- #
def inverse_relative_distance(doy):
    """Eq. 23 - inverse relative distance Earth-Sun."""
    return 1.0 + 0.033 * np.cos(2.0 * np.pi * _a(doy) / 365.0)


def solar_declination(doy):
    """Eq. 24 - solar declination (rad)."""
    return 0.409 * np.sin(2.0 * np.pi * _a(doy) / 365.0 - 1.39)


def sunset_hour_angle(lat_deg, doy):
    """Eq. 25 - sunset hour angle (rad). Clipped for polar day / night."""
    phi = np.radians(_a(lat_deg))
    delta = solar_declination(doy)
    return np.arccos(np.clip(-np.tan(phi) * np.tan(delta), -1.0, 1.0))


def daylight_hours(lat_deg, doy):
    """Eq. 34 - maximum possible daylight hours N."""
    return 24.0 / np.pi * sunset_hour_angle(lat_deg, doy)


def extraterrestrial_radiation(lat_deg, doy):
    """Eq. 21 - extraterrestrial radiation Ra (MJ m-2 day-1)."""
    phi = np.radians(_a(lat_deg))
    delta = solar_declination(doy)
    ws = sunset_hour_angle(lat_deg, doy)
    dr = inverse_relative_distance(doy)
    return (24.0 * 60.0 / np.pi) * GSC * dr * (
        ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws)
    )


def clear_sky_radiation(ra, elevation_m):
    """Eq. 37 - clear-sky solar radiation Rso (MJ m-2 day-1)."""
    return (0.75 + 2e-5 * _a(elevation_m)) * _a(ra)


def solar_from_sunshine(n_hours, lat_deg, doy, a_s=0.25, b_s=0.50):
    """Eq. 35 - Angstrom formula: Rs from measured sunshine hours."""
    ra = extraterrestrial_radiation(lat_deg, doy)
    big_n = daylight_hours(lat_deg, doy)
    return (a_s + b_s * _a(n_hours) / big_n) * ra


def solar_from_hargreaves(tmax, tmin, ra, krs=0.16):
    """Eq. 50 - Hargreaves radiation estimate from temperature range.

    krs = 0.16 for interior locations, 0.19 for coastal locations.
    """
    return krs * np.sqrt(np.maximum(_a(tmax) - _a(tmin), 0.0)) * _a(ra)


def net_radiation(rs, tmax, tmin, ea, ra, elevation_m, albedo=0.23):
    """Eqs. 38-40 - net radiation Rn = Rns - Rnl (MJ m-2 day-1)."""
    rs, tmax, tmin, ea = _a(rs), _a(tmax), _a(tmin), _a(ea)
    rso = clear_sky_radiation(ra, elevation_m)
    rns = (1.0 - albedo) * rs
    ratio = np.clip(rs / np.maximum(rso, 1e-6), 0.3, 1.0)
    tk4 = ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2.0
    rnl = SIGMA * tk4 * (0.34 - 0.14 * np.sqrt(np.maximum(ea, 0.0))) * (1.35 * ratio - 0.35)
    return rns - rnl


# --------------------------------------------------------------------------- #
# Wind
# --------------------------------------------------------------------------- #
def wind_at_2m(uz, height_m):
    """Eq. 47 - convert wind speed measured at `height_m` to 2 m."""
    return _a(uz) * 4.87 / np.log(67.8 * height_m - 5.42)


# --------------------------------------------------------------------------- #
# Penman-Monteith
# --------------------------------------------------------------------------- #
def et0_penman_monteith(tmax, tmin, rs, u2, ea, lat_deg, doy, elevation_m,
                        albedo=0.23, g=0.0):
    """Eq. 6 - FAO-56 Penman-Monteith reference evapotranspiration (mm/day).

    Parameters
    ----------
    tmax, tmin : daily max / min air temperature (deg C)
    rs         : incoming solar radiation (MJ m-2 day-1)
    u2         : wind speed at 2 m (m/s)
    ea         : actual vapour pressure (kPa), see `actual_vapour_pressure`
    lat_deg    : latitude, degrees (north positive)
    doy        : day of year (1-366)
    elevation_m: station elevation (m)
    albedo     : 0.23 for the grass reference surface
    g          : soil heat flux (MJ m-2 day-1); ~0 for daily time steps
    """
    tmax, tmin, rs, u2, ea = map(_a, (tmax, tmin, rs, u2, ea))
    tmean = (tmax + tmin) / 2.0
    gamma = psychrometric_constant(atmospheric_pressure(elevation_m))
    delta = slope_vapour_pressure_curve(tmean)
    es = mean_saturation_vapour_pressure(tmax, tmin)
    ea = np.minimum(ea, es)                      # air cannot be supersaturated
    ra = extraterrestrial_radiation(lat_deg, doy)
    rn = net_radiation(rs, tmax, tmin, ea, ra, elevation_m, albedo)
    u2 = np.maximum(u2, 0.5)                     # FAO-56 sec. 3.4: min. 0.5 m/s
    numerator = 0.408 * delta * (rn - g) + gamma * 900.0 / (tmean + 273.0) * u2 * (es - ea)
    denominator = delta + gamma * (1.0 + 0.34 * u2)
    return np.maximum(numerator / denominator, 0.0)


def et0_from_dataframe(df: pd.DataFrame, lat_deg: float, elevation_m: float) -> pd.Series:
    """Compute daily ET0 for a DataFrame indexed by date.

    Required columns : tmax, tmin, rh (mean RH %), wind (m/s at 2 m)
    Optional column  : rs (MJ m-2 day-1). Missing values are filled with the
                       Hargreaves estimate (Eq. 50).
    """
    doy = df.index.dayofyear.values
    tmax = df["tmax"].to_numpy(float)
    tmin = df["tmin"].to_numpy(float)
    ea = actual_vapour_pressure(tmax=tmax, tmin=tmin, rh_mean=df["rh"].to_numpy(float))
    ra = extraterrestrial_radiation(lat_deg, doy)
    if "rs" in df:
        rs = df["rs"].to_numpy(float)
    else:
        rs = np.full(len(df), np.nan)
    missing = ~np.isfinite(rs)
    if missing.any():
        rs = np.where(missing, solar_from_hargreaves(tmax, tmin, ra), rs)
    et0 = et0_penman_monteith(tmax, tmin, rs, df["wind"].to_numpy(float),
                              ea, lat_deg, doy, elevation_m)
    return pd.Series(et0, index=df.index, name="et0")
