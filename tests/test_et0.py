"""Validation of the ET0 engine against worked examples in FAO-56 (Allen et al., 1998)."""
import numpy as np
import pandas as pd
import pytest

from cwr import et0 as E


def test_pressure_and_gamma_example_2():
    # FAO-56 Example 2: z = 1800 m -> P = 81.8 kPa, gamma = 0.054 kPa/C
    p = E.atmospheric_pressure(1800)
    assert p == pytest.approx(81.8, abs=0.1)
    assert E.psychrometric_constant(p) == pytest.approx(0.054, abs=0.001)


def test_saturation_vapour_pressure_example_3():
    # Example 3: e0(24.5) = 3.075 kPa, e0(15) = 1.705 kPa
    assert E.saturation_vapour_pressure(24.5) == pytest.approx(3.075, abs=0.005)
    assert E.saturation_vapour_pressure(15.0) == pytest.approx(1.705, abs=0.005)


def test_slope_example_4():
    # Example 4: Delta(24.5 C) = 0.183 kPa/C
    assert E.slope_vapour_pressure_curve(24.5) == pytest.approx(0.183, abs=0.001)


def test_extraterrestrial_radiation_example_8():
    # Example 8: 3 September (doy 246), latitude 20 S -> Ra = 32.2 MJ/m2/day
    assert E.extraterrestrial_radiation(-20.0, 246) == pytest.approx(32.2, abs=0.2)


def test_daylight_hours_example_9():
    # Example 9: same place/date -> N = 11.7 h
    assert E.daylight_hours(-20.0, 246) == pytest.approx(11.7, abs=0.1)


def test_wind_height_conversion_example_14():
    # Example 14: 3.2 m/s at 10 m -> 2.4 m/s at 2 m
    assert E.wind_at_2m(3.2, 10) == pytest.approx(2.4, abs=0.02)


def test_et0_example_18_uccle_belgium():
    """FAO-56 Example 18: Uccle (Brussels), 6 July. Published ET0 = 3.9 mm/day."""
    tmax, tmin = 21.5, 12.3
    rh_max, rh_min = 84.0, 63.0
    u2 = E.wind_at_2m(10.0 / 3.6, 10.0)          # 10 km/h measured at 10 m
    lat, doy, z = 50.8, 187, 100.0
    rs = E.solar_from_sunshine(9.25, lat, doy)
    ea = E.actual_vapour_pressure(tmax=tmax, tmin=tmin, rh_max=rh_max, rh_min=rh_min)
    assert ea == pytest.approx(1.409, abs=0.005)
    assert u2 == pytest.approx(2.078, abs=0.01)
    assert rs == pytest.approx(22.07, abs=0.15)
    et0 = float(E.et0_penman_monteith(tmax, tmin, rs, u2, ea, lat, doy, z))
    assert et0 == pytest.approx(3.88, abs=0.08)


def test_et0_vectorised_matches_scalar():
    idx = pd.date_range("2024-06-01", periods=5)
    df = pd.DataFrame({"tmax": [38, 39, 40, 37, 36], "tmin": [25, 26, 27, 25, 24],
                       "rh": [40, 38, 35, 50, 55], "wind": [2, 2.2, 1.8, 2.5, 2.0],
                       "rs": [26, 27, 27, 24, 23]}, index=idx)
    series = E.et0_from_dataframe(df, 30.3, 128.0)
    for i, d in enumerate(idx):
        r = df.iloc[i]
        ea = E.actual_vapour_pressure(tmax=r.tmax, tmin=r.tmin, rh_mean=r.rh)
        one = E.et0_penman_monteith(r.tmax, r.tmin, r.rs, r.wind, ea,
                                    30.3, d.dayofyear, 128.0)
        assert series.iloc[i] == pytest.approx(float(one))
    # hot, dry, sunny summer in Punjab should give a high ET0
    assert 7.0 < series.mean() < 13.0


def test_missing_radiation_falls_back_to_hargreaves():
    idx = pd.date_range("2024-03-01", periods=3)
    df = pd.DataFrame({"tmax": [28, 29, 30], "tmin": [14, 15, 15], "rh": [50, 50, 50],
                       "wind": [2, 2, 2], "rs": [np.nan, np.nan, np.nan]}, index=idx)
    out = E.et0_from_dataframe(df, 30.0, 100.0)
    assert out.notna().all() and (out > 2).all() and (out < 8).all()


def test_et0_never_negative():
    et0 = E.et0_penman_monteith(-15, -25, 2.0, 1.0, 0.1, 60.0, 355, 10.0)
    assert float(et0) >= 0.0
