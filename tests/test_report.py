from datetime import date

from cwr import CROPS, SOILS, compute_daily, run_schedule
from cwr.report import build_pdf
from cwr.weather import synthetic_demo_weather


def test_pdf_report_builds_and_is_valid():
    w = synthetic_demo_weather(30.3, date(2023, 1, 1), date(2024, 12, 31))
    daily = compute_daily(w, 30.3, 128.0)
    res = run_schedule(daily, CROPS["Wheat"], SOILS["Loam"], date(2023, 11, 15))
    pdf = build_pdf(res.summary, res.events, res.daily, {"Location": "test", "Crop": "Wheat"})
    assert pdf[:5] == b"%PDF-" and len(pdf) > 20_000


def test_pdf_report_without_irrigation_events():
    w = synthetic_demo_weather(30.3, date(2023, 1, 1), date(2024, 12, 31))
    daily = compute_daily(w, 30.3, 128.0)
    daily["rain"] = 20.0                                   # constant heavy rain -> no irrigation
    res = run_schedule(daily, CROPS["Wheat"], SOILS["Loam"], date(2023, 11, 15))
    assert res.summary["n_irrigations"] == 0
    pdf = build_pdf(res.summary, res.events, res.daily, {"Location": "test"})
    assert pdf[:5] == b"%PDF-"
