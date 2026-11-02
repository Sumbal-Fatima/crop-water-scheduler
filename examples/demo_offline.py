"""Run the whole pipeline without the app or internet, using SYNTHETIC weather.

    python examples/demo_offline.py

For real results replace `synthetic_demo_weather` with `fetch_nasa_power`
(see README) - one line changes, everything else stays the same.
"""
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cwr import CROPS, SOILS, climatology, compute_daily, run_schedule, season_frame
from cwr.report import build_pdf
from cwr.weather import clean_weather, synthetic_demo_weather

LAT, LON, ELEV = 30.30, 71.93, 128.0          # Khanewal, Punjab (approximate)

raw = clean_weather(synthetic_demo_weather(LAT, date(2016, 1, 1), date(2026, 10, 27)))
daily = compute_daily(raw, LAT, ELEV)
clim = climatology(daily)

crop, soil, sowing = CROPS["Wheat"], SOILS["Loam"], date(2026, 11, 15)
season = season_frame(daily, clim, sowing, crop.season_days)
res = run_schedule(season, crop, soil, sowing, application_efficiency=0.6)

print("SYNTHETIC DEMO DATA - not real weather\n")
for k, v in res.summary.items():
    print(f"{k:>24}: {v}")
print("\nIrrigation schedule")
print(res.events.to_string(index=False))

out = Path(__file__).parent / "demo_report.pdf"
out.write_bytes(build_pdf(res.summary, res.events, res.daily,
                          {"Location": "Khanewal (synthetic demo weather)", "Crop": "Wheat"}))
print(f"\nPDF written to {out}")
