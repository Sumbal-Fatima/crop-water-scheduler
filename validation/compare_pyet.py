"""Cross-check this project's ET0 against the independent `pyet` library.

    pip install pyet
    python validation/compare_pyet.py

Both implement FAO-56 Penman-Monteith, so they should agree to within rounding.
Reports mean absolute difference (mm/day) and maximum difference on 3 years of
synthetic daily weather at three latitudes/elevations.
"""
from datetime import date
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cwr.et0 import actual_vapour_pressure, et0_from_dataframe, extraterrestrial_radiation
from cwr.weather import synthetic_demo_weather

try:
    import pyet
except ImportError:
    sys.exit("pyet is not installed: pip install pyet")

SITES = [("Khanewal", 30.3, 128.0), ("Peshawar", 34.0, 331.0), ("Gilgit-like highland", 35.9, 1500.0)]

print(f"{'site':<22}{'MAD mm/d':>10}{'max |diff|':>12}{'mean ET0':>10}")
for name, lat, z in SITES:
    w = synthetic_demo_weather(lat, date(2022, 1, 1), date(2024, 12, 31), seed=7)
    ours = et0_from_dataframe(w, lat, z)
    tmean = (w.tmax + w.tmin) / 2
    ea = actual_vapour_pressure(tmax=w.tmax.values, tmin=w.tmin.values, rh_mean=w.rh.values)
    ra = extraterrestrial_radiation(lat, w.index.dayofyear.values)
    rn = pd.Series(
        (1 - 0.23) * w.rs.values
        - 4.903e-9 * (((w.tmax.values + 273.16) ** 4 + (w.tmin.values + 273.16) ** 4) / 2)
        * (0.34 - 0.14 * np.sqrt(ea))
        * (1.35 * np.clip(w.rs.values / ((0.75 + 2e-5 * z) * ra), 0.3, 1.0) - 0.35),
        index=w.index)
    ref = pyet.pm_fao56(tmean=tmean, wind=w.wind, rn=rn, tmax=w.tmax, tmin=w.tmin, rh=w.rh,
                        elevation=z, lat=np.radians(lat))
    diff = (ours - ref).abs()
    print(f"{name:<22}{diff.mean():>10.4f}{diff.max():>12.4f}{ours.mean():>10.2f}")
