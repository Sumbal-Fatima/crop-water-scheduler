from datetime import date

import numpy as np
import pandas as pd
import pytest

from cwr.climate import apply_scenario, climatology
from cwr.crops import CROPS, kc_curve, root_depth_curve
from cwr.pipeline import compute_daily, season_frame
from cwr.scheduler import run_ensemble, run_schedule
from cwr.soils import SOILS
from cwr.weather import clean_weather, synthetic_demo_weather


def _flat_weather(start="2026-11-15", days=140, et0=4.0, rain=0.0):
    idx = pd.date_range(start, periods=days)
    return pd.DataFrame({"et0": et0, "rain": rain}, index=idx)


def test_kc_curve_shape_and_length():
    for crop in CROPS.values():
        kc = kc_curve(crop)
        assert len(kc) == crop.season_days
        assert kc[0] == pytest.approx(crop.kc_ini, abs=0.05) or crop.l_ini > 1
        assert kc.max() == pytest.approx(max(crop.kc_mid, crop.kc_ini, crop.kc_end), abs=1e-9)
        assert kc[-1] == pytest.approx(crop.kc_end, abs=1e-9)
        z = root_depth_curve(crop)
        assert z[0] >= crop.zr_ini and z[-1] == pytest.approx(crop.zr_max)
        assert np.all(np.diff(z) >= -1e-12)


def test_water_balance_closes():
    """Change in depletion must equal ETa - Peff - irrigation + deep percolation."""
    w = synthetic_demo_weather(30.3, date(2024, 1, 1), date(2025, 12, 31))
    daily = compute_daily(w, 30.3, 128.0)
    for crop_name in ["Wheat", "Cotton", "Maize"]:
        crop = CROPS[crop_name]
        res = run_schedule(daily, crop, SOILS["Loam"], date(2024, 11, 15)
                           if crop_name == "Wheat" else date(2024, 5, 1),
                           initial_depletion_fraction=0.3)
        d = res.daily
        start_dr = d["initial_depletion"].iloc[0]
        lhs = d["depletion"].iloc[-1] - start_dr
        rhs = (d["eta"] - d["eff_rain"] - d["irrigation_net"] + d["deep_percolation"]).sum()
        assert lhs == pytest.approx(rhs, abs=1e-6)


def test_irrigated_has_no_stress_and_depletion_bounded():
    res = run_schedule(_flat_weather(), CROPS["Wheat"], SOILS["Loam"], date(2026, 11, 15))
    d = res.daily
    assert (d["ks"] == 1.0).all()
    assert (d["depletion"] <= d["raw"] + 1e-9).all()
    assert res.summary["n_irrigations"] >= 4
    assert res.summary["eta_etc_ratio"] == pytest.approx(1.0)
    # with no rain the net irrigation equals ETc (profile starts and ends near FC)
    assert res.summary["net_irrigation_mm"] == pytest.approx(
        res.summary["etc_total_mm"], abs=d["raw"].max())


def test_rainfed_causes_stress_and_less_water_use():
    wet = run_schedule(_flat_weather(), CROPS["Wheat"], SOILS["Loam"], date(2026, 11, 15))
    dry = run_schedule(_flat_weather(), CROPS["Wheat"], SOILS["Loam"], date(2026, 11, 15),
                       irrigate=False)
    assert dry.summary["n_irrigations"] == 0
    assert dry.summary["stress_days"] > 0
    assert dry.summary["eta_total_mm"] < wet.summary["eta_total_mm"]
    assert (dry.daily["depletion"] <= dry.daily["taw"] + 1e-9).all()


def test_heavy_rain_goes_to_deep_percolation_and_delays_irrigation():
    w = _flat_weather()
    w.iloc[30, 1] = 120.0
    res = run_schedule(w, CROPS["Wheat"], SOILS["Loam"], date(2026, 11, 15))
    # 120 mm rain x 0.8 effectiveness = 96 mm; the root zone can only absorb about
    # one TAW worth of it, so a large part must drain below the root zone
    assert res.summary["deep_percolation_mm"] > 40
    assert res.daily["deep_percolation"].iloc[30] == pytest.approx(
        res.summary["deep_percolation_mm"], abs=0.2)
    base = run_schedule(_flat_weather(), CROPS["Wheat"], SOILS["Loam"], date(2026, 11, 15))
    # The storm refills the (still shallow) root zone, so the next irrigation is
    # pushed later than in the no-rain run. (Total net irrigation need not fall:
    # most of the storm drains away, and the schedule is only shifted.)
    nxt_base = base.events.loc[base.events["day_after_sowing"] >= 31, "day_after_sowing"].min()
    nxt_rain = res.events.loc[res.events["day_after_sowing"] >= 31, "day_after_sowing"].min()
    assert nxt_rain > nxt_base


def test_efficiency_scales_gross_not_net():
    a = run_schedule(_flat_weather(), CROPS["Wheat"], SOILS["Loam"], date(2026, 11, 15),
                     application_efficiency=0.5)
    b = run_schedule(_flat_weather(), CROPS["Wheat"], SOILS["Loam"], date(2026, 11, 15),
                     application_efficiency=1.0)
    assert a.summary["net_irrigation_mm"] == pytest.approx(b.summary["net_irrigation_mm"])
    assert a.summary["gross_irrigation_mm"] == pytest.approx(2 * b.summary["gross_irrigation_mm"])


def test_sandy_soil_needs_more_frequent_irrigation_than_clay():
    sand = run_schedule(_flat_weather(), CROPS["Wheat"], SOILS["Sandy loam"], date(2026, 11, 15))
    clay = run_schedule(_flat_weather(), CROPS["Wheat"], SOILS["Clay"], date(2026, 11, 15))
    assert sand.summary["n_irrigations"] > clay.summary["n_irrigations"]


def test_fixed_depth_option():
    res = run_schedule(_flat_weather(), CROPS["Wheat"], SOILS["Loam"], date(2026, 11, 15),
                       irrigation_depth_mm=40.0)
    assert set(res.events["net_mm"].round(1)) == {40.0}


def test_short_weather_raises():
    with pytest.raises(ValueError):
        run_schedule(_flat_weather(days=30), CROPS["Wheat"], SOILS["Loam"], date(2026, 11, 15))


def test_climatology_and_season_frame_fill():
    w = synthetic_demo_weather(30.3, date(2020, 1, 1), date(2025, 6, 30))
    daily = compute_daily(w, 30.3, 128.0)
    clim = climatology(daily)
    assert len(clim) == 366 and clim.notna().all().all()
    # the mean-based climatology preserves annual rain (within 2 %)
    raw_total = daily["rain"].groupby(daily.index.dayofyear).mean().sum()
    mean_clim = climatology(daily, stat="mean")
    assert mean_clim["rain"].sum() == pytest.approx(raw_total, rel=0.02)
    # the median-based default is never wetter than the mean
    assert clim["rain"].sum() <= mean_clim["rain"].sum() + 1e-6
    sf = season_frame(daily, clim, date(2025, 11, 15), 135)
    assert (sf["source"] == "climatology").all()
    assert sf[["et0", "rain"]].notna().all().all()
    mixed = season_frame(daily, clim, date(2025, 6, 1), 60)
    assert set(mixed["source"]) == {"observed", "climatology"}
    res = run_schedule(sf, CROPS["Wheat"], SOILS["Loam"], date(2025, 11, 15))
    assert res.summary["days_from_climatology"] == 135


def test_warming_scenario_raises_et0_and_irrigation():
    w = synthetic_demo_weather(30.3, date(2022, 1, 1), date(2024, 12, 31))
    base = compute_daily(w, 30.3, 128.0)
    warm = compute_daily(w, 30.3, 128.0, delta_t=2.0)
    assert warm["et0"].sum() > base["et0"].sum()
    r0 = run_schedule(base, CROPS["Wheat"], SOILS["Loam"], date(2023, 11, 15))
    r1 = run_schedule(warm, CROPS["Wheat"], SOILS["Loam"], date(2023, 11, 15))
    assert r1.summary["etc_total_mm"] > r0.summary["etc_total_mm"]


def test_ensemble_runs_each_complete_year():
    w = synthetic_demo_weather(30.3, date(2018, 1, 1), date(2025, 12, 31))
    daily = compute_daily(w, 30.3, 128.0)
    ens = run_ensemble(daily, CROPS["Wheat"], SOILS["Loam"], 11, 15, list(range(2018, 2026)))
    assert list(ens["sowing_year"]) == list(range(2018, 2025))   # 2025 season incomplete
    assert (ens["gross_irrigation_mm"] > 0).all()


def test_scenario_does_not_mutate_input():
    w = synthetic_demo_weather(30.3, date(2024, 1, 1), date(2024, 1, 10))
    before = w.copy()
    apply_scenario(w, 3.0, 0.5)
    pd.testing.assert_frame_equal(w, before)


def test_clean_weather_fills_short_gaps_and_drops_missing_tail():
    w = synthetic_demo_weather(30.3, date(2024, 1, 1), date(2024, 1, 20))
    w.loc["2024-01-05":"2024-01-06", ["tmax", "tmin", "rh", "wind", "rs"]] = np.nan
    w.loc["2024-01-19":"2024-01-20", :] = np.nan
    out = clean_weather(w)
    assert out.loc["2024-01-05", "tmax"] == pytest.approx(out.loc["2024-01-05", "tmax"])
    assert not out.loc["2024-01-01":"2024-01-18"].isna().any().any()
    assert out.index.max() == pd.Timestamp("2024-01-18")


def test_median_climatology_ignores_an_extreme_wet_year():
    from cwr.climate import rainfall_outlier_years

    idx = pd.date_range("2016-01-01", "2025-12-31", freq="D")
    rng = np.random.default_rng(1)
    daily = pd.DataFrame({"et0": 4.0, "rain": np.where(rng.random(len(idx)) < 0.05, 6.0, 0.0)}, index=idx)
    daily.loc["2019-11-20", "rain"] += 300.0                     # one absurd storm in one year
    med = climatology(daily)
    mean = climatology(daily, stat="mean")
    nov = slice(300, 340)                                         # window around 20 Nov
    assert med["rain"].iloc[nov].max() < 0.6                      # not distorted
    assert mean["rain"].iloc[nov].max() > 1.0                     # the mean is distorted (~300/10/31 mm/day)
    assert med["rain"].sum() < mean["rain"].sum()
    # outlier detector
    season = pd.Series({2016: 28.0, 2017: 22.0, 2018: 91.0, 2019: 404.0, 2020: 236.0,
                        2021: 48.0, 2022: 59.0, 2023: 21.0, 2024: 22.0, 2025: 27.0})
    assert rainfall_outlier_years(season) == [2019, 2020]
    assert rainfall_outlier_years(season.iloc[:3]) == []
