import io
from datetime import date

import numpy as np
import pandas as pd
import pytest

from cwr import weather as W


def _fake_payload(days=3, missing_last=False):
    dates = [f"2024010{i + 1}" for i in range(days)]
    params = {}
    for api_name in W.PARAMS:
        vals = {d: float(10 + i) for i, d in enumerate(dates)}
        if missing_last:
            vals[dates[-1]] = -999.0
        params[api_name] = vals
    return {"geometry": {"type": "Point", "coordinates": [71.9, 30.3, 128.5]},
            "properties": {"parameter": params}}


def test_parse_power_json_basic_and_fill_values():
    df, elev = W.parse_power_json(_fake_payload(missing_last=True))
    assert elev == 128.5
    assert list(df.columns) == ["tmax", "tmin", "rh", "wind", "rs", "rain"]
    assert df.index[0] == pd.Timestamp("2024-01-01")
    assert np.isnan(df.iloc[-1]["tmax"]) and df.iloc[0]["tmax"] == 10.0


def test_parse_power_json_bad_payload():
    with pytest.raises(W.WeatherDataError):
        W.parse_power_json({"oops": 1})


def test_fetch_uses_one_request_per_year_and_caches(monkeypatch, tmp_path):
    calls = []

    class Resp:
        def __init__(self, year):
            self.year = year

        def raise_for_status(self):
            pass

        def json(self):
            return _fake_payload()

    def fake_get(url, params, timeout):
        calls.append(params["start"][:4])
        return Resp(params["start"][:4])

    monkeypatch.setattr(W.requests, "get", fake_get)
    monkeypatch.setattr(W, "CACHE_DIR", tmp_path)
    df, elev = W.fetch_nasa_power(30.3, 71.9, date(2020, 1, 1), date(2021, 12, 31))
    assert calls == ["2020", "2021"] and elev == 128.5
    W.fetch_nasa_power(30.3, 71.9, date(2020, 1, 1), date(2021, 12, 31))
    assert calls == ["2020", "2021"]                       # second call served from cache


def test_fetch_failure_raises_clear_error(monkeypatch):
    def boom(url, params, timeout):
        raise W.requests.ConnectionError("no network")

    monkeypatch.setattr(W.requests, "get", boom)
    monkeypatch.setattr(W.time, "sleep", lambda s: None)
    with pytest.raises(W.WeatherDataError, match="NASA POWER"):
        W.fetch_nasa_power(30.3, 71.9, date(2020, 1, 1), date(2020, 1, 5), use_cache=False)


def test_csv_loader_aliases_and_wind_height():
    csv = ("Date,Tmax,Tmin,RH,Wind,Rain\n"
           "2024-01-01,20,8,60,3.2,0\n2024-01-02,21,9,55,3.2,1.5\n")
    df = W.load_weather_csv(io.StringIO(csv), wind_height_m=10)
    assert df["wind"].iloc[0] == pytest.approx(2.4, abs=0.02)
    assert "rs" in df and df["rs"].isna().all()


def test_csv_loader_reports_missing_columns():
    with pytest.raises(W.WeatherDataError, match="tmin"):
        W.load_weather_csv(io.StringIO("date,tmax,rh,wind,rain\n2024-01-01,20,60,2,0\n"))
