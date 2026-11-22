"""M3 public interface: stub risk, real weather, and what-if scenario structure."""
from datetime import datetime, timezone
from functools import lru_cache

from modules.shared.grid import load_grid, reload_data as reload_grid
from modules.shared.weather import get_forecast as fetch_forecast

STUDY_POINTS = [(37.08, -119.38), (37.12, -119.30)]
MODEL_NOTE = "The ignition-risk model is not yet trained. This stub is not a prediction or warning."


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _common_feature(patch, valid_at: str, data_kind: str) -> dict:
    return {
        "type": "Feature",
        "geometry": patch["geometry"].__geo_interface__,
        "properties": {
            "feature_id": f"ignition_risk:{patch['patch_id']}",
            "patch_id": patch["patch_id"],
            "row": int(patch["row"]),
            "col": int(patch["col"]),
            "center_lon": round(float(patch["center_lon"]), 6),
            "center_lat": round(float(patch["center_lat"]), 6),
            "layer_type": "ignition_risk",
            "valid_at": valid_at,
            "window_hours": 24,
            "observed_at": None,
            "generated_at": _utc_now(),
            "risk_score": None,
            "risk_percentile": None,
            "risk_band": "not_scored",
            "top_drivers": None,
            "model_status": "not_trained",
            "model_note": MODEL_NOTE,
            "model_version": "m3-stub",
            "source": "m3 stub; no trained model",
            "data_kind": data_kind,
            "data_quality": "stub",
        },
    }


def _valid_at(valid_at: datetime | str | None) -> str:
    if valid_at is None:
        return _utc_now()
    if isinstance(valid_at, datetime):
        value = valid_at
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(valid_at)


@lru_cache(maxsize=1)
def get_risk_layer(valid_at: datetime | str | None = None) -> dict:
    valid = _valid_at(valid_at)
    grid = load_grid()
    return {
        "type": "FeatureCollection",
        "features": [_common_feature(row, valid, "predicted") for _, row in grid.sort_values("patch_id").iterrows()],
    }


@lru_cache(maxsize=1)
def get_patch_risk(patch_id: str) -> dict | None:
    grid = load_grid()
    matches = grid[grid["patch_id"] == patch_id]
    if matches.empty:
        return None
    return _common_feature(matches.iloc[0], _utc_now(), "predicted")["properties"]


def run_scenario(delta_temp_c: float, delta_wind_pct: float, delta_precip_pct: float,
                 valid_at: datetime | str | None = None, patch_ids: list[str] | None = None) -> dict:
    valid = _valid_at(valid_at)
    grid = load_grid()
    if patch_ids is not None:
        selected = grid[grid["patch_id"].isin(patch_ids)].sort_values("patch_id")
    else:
        selected = grid.sort_values("patch_id")
    features = []
    for _, patch in selected.iterrows():
        feature = _common_feature(patch, valid, "scenario")
        props = feature["properties"]
        props["baseline_risk_score"] = None
        props["risk_change"] = None
        props["scenario"] = {
            "delta_temp_c": delta_temp_c,
            "delta_wind_pct": delta_wind_pct,
            "delta_precip_pct": delta_precip_pct,
        }
        features.append(feature)
    return {"type": "FeatureCollection", "features": features}


def get_forecast(hours: int = 48) -> dict:
    return {
        "data_kind": "observed",
        "source": "Open-Meteo",
        "generated_at": _utc_now(),
        "timezone": "UTC",
        "hourly": get_forecast_rows(STUDY_POINTS, hours),
    }


def get_forecast_rows(points, hours: int) -> list:
    return fetch_forecast(points, hours)


def get_status() -> dict:
    return {
        "valid_at": _utc_now(),
        "weather_used_at": None,
        "generated_at": _utc_now(),
        "model_version": "m3-stub",
        "model_status": "not_trained",
        "error": None,
    }


def reload_data() -> None:
    get_risk_layer.cache_clear()
    get_patch_risk.cache_clear()
    reload_grid()
