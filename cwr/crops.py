"""Crop database (single crop coefficient approach, FAO-56 Chapter 6).

Kc values: FAO-56 Table 12. Stage lengths: FAO-56 Table 11 (typical values for
warm/subtropical regions). Rooting depth: Table 22. Depletion fraction p
(for ETc ~ 5 mm/day): Table 22.

These are *typical* values and are rounded. Stage lengths depend strongly on
variety, sowing date and climate - always replace them with local data when
you have it (the app lets you edit every number).
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

STAGES = ("Initial", "Development", "Mid-season", "Late-season")


@dataclass(frozen=True)
class Crop:
    name: str
    kc_ini: float
    kc_mid: float
    kc_end: float
    l_ini: int
    l_dev: int
    l_mid: int
    l_late: int
    zr_ini: float      # effective root depth at sowing (m)
    zr_max: float      # maximum effective root depth (m)
    p: float           # allowable depletion fraction (for ETc ~ 5 mm/day)
    note: str = ""

    @property
    def season_days(self) -> int:
        return self.l_ini + self.l_dev + self.l_mid + self.l_late

    def with_changes(self, **kwargs) -> "Crop":
        return replace(self, **kwargs)


CROPS: dict[str, Crop] = {
    "Wheat": Crop("Wheat", 0.30, 1.15, 0.25, 20, 25, 60, 30, 0.30, 1.20, 0.55,
                  "Sown Nov-Dec in Pakistan / N. India; 135 days."),
    "Maize": Crop("Maize", 0.30, 1.20, 0.35, 25, 40, 40, 30, 0.30, 1.00, 0.55,
                  "Grain maize; 135 days."),
    "Cotton": Crop("Cotton", 0.35, 1.15, 0.70, 30, 50, 55, 45, 0.30, 1.30, 0.65,
                   "180 days; Kc_end 0.70 if not defoliated early."),
    "Rice (see note)": Crop("Rice (see note)", 1.05, 1.20, 0.90, 30, 30, 60, 30,
                            0.20, 0.50, 0.20,
                            "Flooded paddy: puddling and percolation losses are NOT "
                            "modelled; treat output as crop ET only."),
    "Sugarcane": Crop("Sugarcane", 0.40, 1.25, 0.75, 50, 70, 220, 140, 0.30, 1.20, 0.65,
                      "Long-season ratoon/plant cane, 480 days."),
    "Potato": Crop("Potato", 0.50, 1.15, 0.75, 25, 30, 45, 30, 0.25, 0.60, 0.35,
                   "130 days."),
    "Tomato": Crop("Tomato", 0.60, 1.15, 0.80, 30, 40, 40, 25, 0.25, 0.80, 0.40,
                   "135 days."),
    "Sunflower": Crop("Sunflower", 0.35, 1.075, 0.35, 25, 35, 45, 25, 0.30, 0.80, 0.45,
                      "130 days."),
    "Canola / mustard": Crop("Canola / mustard", 0.35, 1.075, 0.35, 20, 25, 60, 25,
                             0.30, 1.00, 0.60, "130 days; winter crop."),
    "Sorghum": Crop("Sorghum", 0.30, 1.00, 0.55, 20, 35, 40, 30, 0.30, 1.00, 0.55,
                    "125 days."),
}


def kc_curve(crop: Crop) -> np.ndarray:
    """Daily Kc for the whole season (FAO-56 Fig. 25 shape, length = season_days).

    Kc_ini is held constant, then increases linearly to Kc_mid during the
    development stage, stays constant, and declines linearly to Kc_end.
    """
    n = crop.season_days
    day = np.arange(1, n + 1, dtype=float)
    e1 = crop.l_ini
    e2 = e1 + crop.l_dev
    e3 = e2 + crop.l_mid
    kc = np.empty(n)
    ini = day <= e1
    dev = (day > e1) & (day <= e2)
    mid = (day > e2) & (day <= e3)
    late = day > e3
    kc[ini] = crop.kc_ini
    kc[dev] = crop.kc_ini + (day[dev] - e1) / crop.l_dev * (crop.kc_mid - crop.kc_ini)
    kc[mid] = crop.kc_mid
    kc[late] = crop.kc_mid + (day[late] - e3) / crop.l_late * (crop.kc_end - crop.kc_mid)
    return kc


def root_depth_curve(crop: Crop) -> np.ndarray:
    """Effective root depth (m) per day: linear growth from zr_ini to zr_max
    over the initial + development stages, then constant."""
    n = crop.season_days
    day = np.arange(1, n + 1, dtype=float)
    grow_days = max(crop.l_ini + crop.l_dev, 1)
    frac = np.clip(day / grow_days, 0.0, 1.0)
    return crop.zr_ini + frac * (crop.zr_max - crop.zr_ini)


def stage_names(crop: Crop) -> np.ndarray:
    """Stage label for each day of the season."""
    labels = (["Initial"] * crop.l_ini + ["Development"] * crop.l_dev +
              ["Mid-season"] * crop.l_mid + ["Late-season"] * crop.l_late)
    return np.array(labels)
