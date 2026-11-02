"""Soil water holding properties (FAO-56 Table 19, mid-range values).

theta_fc : volumetric water content at field capacity (m3/m3)
theta_wp : volumetric water content at permanent wilting point (m3/m3)

Mid-points of the FAO-56 ranges are used. If you have measured values for the
field (pressure plate, TDR, lab report), enter them as a custom soil in the app.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Soil:
    name: str
    theta_fc: float
    theta_wp: float

    @property
    def awc_mm_per_m(self) -> float:
        """Available water capacity in mm of water per metre of soil."""
        return 1000.0 * (self.theta_fc - self.theta_wp)


SOILS: dict[str, Soil] = {
    "Sand": Soil("Sand", 0.12, 0.045),
    "Loamy sand": Soil("Loamy sand", 0.15, 0.065),
    "Sandy loam": Soil("Sandy loam", 0.23, 0.11),
    "Loam": Soil("Loam", 0.25, 0.12),
    "Silt loam": Soil("Silt loam", 0.29, 0.15),
    "Silty clay loam": Soil("Silty clay loam", 0.335, 0.205),
    "Clay loam": Soil("Clay loam", 0.32, 0.18),
    "Silty clay": Soil("Silty clay", 0.36, 0.23),
    "Clay": Soil("Clay", 0.36, 0.22),
}
