"""
interface.py -- M1's public functions. The backend calls ONLY these.

get_layer(period)    -> GeoJSON ("summer" = latest full summer from the cache, "live" = in-memory live layer)
get_patch(patch_id)  -> dict for the click panel (includes a "live" block when available), or None
get_status()         -> build times for both layers
reload_data()        -> clear caches
Raises FileNotFoundError if the summer layer has not been built, LiveNotReady if the live layer is still computing.
"""
import json
from functools import lru_cache

from . import live_service
from .paths import HISTORY, LATEST, MODEL_CARD

SCALE_NOTE = " The score is relative to unburned forest in the Shaver Lake area, not an absolute measure of tree health."
LIVE_NOTE = ("Latest satellite window. The score is relative to unburned patches in the same window, "
             "so it is not directly comparable with the summer score. Fewer clear observations means lower reliability.")
MODEL_NOTE = ("Relative likelihood that USFS aerial surveys would map tree mortality in this patch, from a model trained "
              "on Sierra-wide survey polygons. It is driven mostly by terrain and climate; satellite data adds a small gain. "
              "It is not a real-world probability and not a diagnosis.")
EXPLAIN = {
    "Healthy": "Greenness and moisture are within the normal range of unburned forest in this area (not among the lowest 30%).",
    "Moderate stress": "Greenness and moisture are lower than roughly 70-90% of unburned forest in this area.",
    "High stress": "Among the lowest 10% of unburned forest in this area for greenness and moisture. This is a satellite signal, not a diagnosis of cause.",
    "Post-fire recovery": "More than half of this patch burned since 2015. The score shows regrowth, not disease or insect damage.",
    "Not scored": "Too little forest in this patch to give a score.",
}


class LiveNotReady(Exception):
    def __init__(self, status: dict):
        super().__init__("live layer not ready")
        self.status = status


def _need(path) -> None:
    if not path.exists():
        raise FileNotFoundError(path.name)


@lru_cache(maxsize=1)
def _layer() -> dict:
    _need(LATEST)
    return json.loads(LATEST.read_text())


@lru_cache(maxsize=1)
def _history() -> dict:
    _need(HISTORY)
    return json.loads(HISTORY.read_text())


@lru_cache(maxsize=1)
def _props_by_patch() -> dict:
    return {f["properties"]["patch_id"]: f["properties"] for f in _layer()["features"]}


_SEEN = {}


def _refresh_if_changed() -> None:
    """Reload cached summer files when they have been rebuilt on disk."""
    sig = tuple(p.stat().st_mtime if p.exists() else None for p in (LATEST, HISTORY))
    if _SEEN.get("sig") != sig:
        reload_data()
        _SEEN["sig"] = sig


def get_layer(period: str = "summer") -> dict:
    _refresh_if_changed()
    if period == "live":
        layer, _, _, status = live_service.get_live()
        if layer is None:
            raise LiveNotReady(status)
        return layer
    return _layer()


def get_status() -> dict:
    _refresh_if_changed()
    summer = None
    if LATEST.exists():
        first = _layer()["features"][0]["properties"]
        summer = {"year": first["year"], "period": first["period"],
                  "generated_at": first["generated_at"], "model_version": first["model_version"]}
    _, meta, _, status = live_service.get_live()
    return {"summer": summer, "live": meta, "live_status": status}


def get_patch(patch_id: str) -> dict | None:
    _refresh_if_changed()
    p = _props_by_patch().get(patch_id)
    if p is None:
        return None
    explanation = EXPLAIN.get(p["health_band"], "")
    if p["health_band"] not in ("Post-fire recovery", "Not scored"):
        explanation += SCALE_NOTE

    live = None
    _, _, live_props, _ = live_service.get_live()
    lp = live_props.get(patch_id)
    if lp is not None:
        live = {k: lp[k] for k in ("window_start", "window_end", "observed_at", "health_index",
                                   "health_band", "ndvi", "ndmi", "obs_count", "data_quality")}
        for k in ("mortality_likelihood", "mortality_band", "mortality_percentile","model_status",
                  "mortality_model_version", "mortality_model_window","mortality_climate_year"):
            live[k] = lp.get(k)
        live["note"] = LIVE_NOTE
        live["model_note"] = MODEL_NOTE
    return {
        "patch_id": patch_id, "year": p["year"], "period": p["period"],
        "health_index": p["health_index"], "health_band": p["health_band"],
        "ndvi": p["ndvi"], "ndmi": p["ndmi"],
        "trend_label": p["trend_label"], "trend_slope": p["trend_slope"],
        "burn_status": p["burn_status"], "data_quality": p["data_quality"],
        "explanation": explanation, "model_version": p["model_version"],
        "source": p["source"], "data_kind": p["data_kind"],
        "history": _history().get(patch_id, []),
        "live": live,
    }

def get_model_card() -> dict:
    if not MODEL_CARD.exists():
        raise FileNotFoundError(MODEL_CARD.name)
    return json.loads(MODEL_CARD.read_text())

def reload_data() -> None:
    for fn in (_layer, _history, _props_by_patch):
        fn.cache_clear()