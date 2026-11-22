from datetime import date

import numpy as np
import pandas as pd
import pytest

from modules.forest_health import model_service


class StubModel:
    def predict_proba(self, X):
        p = np.linspace(0.05, 0.95, len(X))
        return np.column_stack([1 - p, p])


CARD = {"features": ["a", "b"], "bands": {"elevated": 0.4, "high": 0.7}, "model_version": "stub"}


@pytest.fixture(autouse=True)
def stub(monkeypatch):
    monkeypatch.setattr(model_service, "load", lambda: (StubModel(), CARD))


def _df():
    return pd.DataFrame({
        "cell_id": ["P1", "P2", "P3", "P4", "P5", "P6"],
        "a": [1, 2, 3, 4, 5, 6], "b": [0] * 6,
        "burn_frac": [0, 0, 0.9, 0, 0, 0],
        "forest_frac": [0.9, 0.9, 0.9, 0.05, 0.9, 0.9],
        "NDVI": [0.5, 0.5, 0.5, 0.5, np.nan, 0.5],
        "dNDVI": [0.0] * 6, "def_wy_prev": [1.0] * 6,
        "obs_count": [10, 10, 10, 10, 10, 1],
    })


def test_status_rules_and_bands():
    out = model_service.score(_df()).set_index("patch_id")
    assert out.loc["P3", "model_status"] == "burned_not_scored"
    assert out.loc["P4", "model_status"] == "too_little_forest"
    assert out.loc["P5", "model_status"] == "missing_data"
    assert out.loc["P6", "model_status"] == "too_few_observations"
    assert out.loc["P1", "model_status"] == "scored" and out.loc["P1", "mortality_band"] == "Lower"
    assert out.loc["P2", "mortality_band"] == "High"
    assert out.loc["P3", "mortality_likelihood"] != out.loc["P3", "mortality_likelihood"]   # NaN


def test_model_year_is_latest_complete_summer():
    assert model_service.model_year(date(2026, 11, 21)) == 2026
    assert model_service.model_year(date(2026, 7, 1)) == 2025

def test_climate_years_fall_back(monkeypatch):
    from modules.forest_health import features_gee
    monkeypatch.setattr(features_gee, "latest_climate_year", lambda: 2025)
    assert features_gee.climate_years(2026) == (2025, 2024)
    assert features_gee.climate_years(2024) == (2024, 2023)

def test_percentile_among_scored_patches():
    out = model_service.score(_df()).set_index("patch_id")
    assert out.loc["P1", "mortality_percentile"] == 50
    assert out.loc["P2", "mortality_percentile"] == 100