"""cwr - Crop Water Requirement and irrigation scheduling (FAO-56)."""
from .climate import apply_scenario, climatology
from .crops import CROPS, Crop, kc_curve
from .et0 import (actual_vapour_pressure, et0_from_dataframe, et0_penman_monteith,
                  extraterrestrial_radiation)
from .pipeline import compute_daily, season_frame
from .scheduler import ScheduleResult, run_ensemble, run_schedule
from .soils import SOILS, Soil

__version__ = "1.0.0"
__all__ = [
    "CROPS", "Crop", "SOILS", "Soil", "ScheduleResult", "apply_scenario", "climatology",
    "compute_daily", "season_frame", "run_schedule", "run_ensemble", "kc_curve",
    "et0_penman_monteith", "et0_from_dataframe", "actual_vapour_pressure",
    "extraterrestrial_radiation",
]
