"""
interface.py -- M1's public functions. The backend calls ONLY these.

get_layer()          -> GeoJSON FeatureCollection, all patches, latest summer
get_patch(patch_id)  -> dict for the click panel, or None if the patch is unknown
reload_data()        -> clear caches after rebuilding the files
"""
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LATEST = ROOT / "data" / "processed" / "m1_forest_health_latest.geojson"
HISTORY = ROOT / "data" / "processed" / "m1_patch_history.json"

SCALE_NOTE = " The score is relative to unburned forest in the Shaver Lake area, not an absolute measure of tree health."
EXPLAIN = {
    "Healthy": "Greenness and moisture are within the normal range of unburned forest in this area (not among the lowest 30%).",
    "Moderate stress": "Greenness and moisture are lower than roughly 70-90% of unburned forest in this area.",
    "High stress": "Among the lowest 10% of unburned forest in this area for greenness and moisture. This is a satellite signal, not a diagnosis of cause.",
    "Post-fire recovery": "More than half of this patch burned since 2015. The score shows regrowth, not disease or insect damage.",
    "Not scored": "Too little forest in this patch to give a score.",
}


@lru_cache(maxsize=1)
def _layer() -> dict:
    return json.loads(LATEST.read_text())


@lru_cache(maxsize=1)
def _history() -> dict:
    return json.loads(HISTORY.read_text())


@lru_cache(maxsize=1)
def _props_by_patch() -> dict:
    return {f["properties"]["patch_id"]: f["properties"] for f in _layer()["features"]}


def get_layer() -> dict:
    return _layer()


def get_patch(patch_id: str) -> dict | None:
    p = _props_by_patch().get(patch_id)
    if p is None:
        return None
    explanation = EXPLAIN.get(p["health_band"], "")
    if p["health_band"] not in ("Post-fire recovery", "Not scored"):
        explanation += SCALE_NOTE
    return {
        "patch_id": patch_id,
        "year": p["year"],
        "period": p["period"],
        "health_index": p["health_index"],
        "health_band": p["health_band"],
        "ndvi": p["ndvi"],
        "ndmi": p["ndmi"],
        "trend_label": p["trend_label"],
        "trend_slope": p["trend_slope"],
        "burn_status": p["burn_status"],
        "data_quality": p["data_quality"],
        "explanation": explanation,
        "model_version": p["model_version"],
        "source": p["source"],
        "data_kind": p["data_kind"],
        "history": _history().get(patch_id, []),
    }


def reload_data() -> None:
    _layer.cache_clear()
    _history.cache_clear()
    _props_by_patch.cache_clear()