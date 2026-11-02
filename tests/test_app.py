"""Smoke tests for the Streamlit UI (offline: uses the synthetic demo data source)."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _run(crop="Wheat", source="Demo data (synthetic, offline)", **widgets):
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception
    at.radio(key="source").set_value(source)
    at.selectbox(key="crop").set_value(crop)
    for k, v in widgets.items():
        getattr(at, v[0])(key=k).set_value(v[1])
    at.button[0].click()
    at.run()
    return at


def test_landing_page_has_no_error():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception and not at.error


@pytest.mark.parametrize("crop", ["Wheat", "Cotton", "Rice (see note)", "Sugarcane"])
def test_demo_run_for_each_crop(crop):
    at = _run(crop)
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
    labels = [m.label for m in at.metric]
    assert "Crop water requirement (ETc)" in labels
    assert any("synthetic demo weather" in w.value for w in at.warning)


def test_csv_source_without_file_warns():
    at = _run(source="Upload CSV")
    assert not at.exception
    assert any("Upload a CSV" in w.value for w in at.warning)
