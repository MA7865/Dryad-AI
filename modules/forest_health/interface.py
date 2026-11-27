"""
interface.py -- M1's public functions. The backend calls ONLY these.

get_layer(period, frame)  -> GeoJSON. period "summer" (frame e.g. "2023-summer"; default latest summer) or "live"
get_timeline()            -> frames + per-patch series for animations (one call)
get_patch(patch_id)       -> click-panel dict (summer values, history, live block), or None
get_patch_timeline(pid)   -> that patch's series over all frames, or None
get_status(), get_model_card(), reload_data()
Raises FileNotFoundError if the summer layer is not built, KeyError for an unknown frame,
LiveNotReady while the live layer is being computed.
"""
import json
from functools import lru_cache

from . import live_service
from .paths import HISTORY, LATEST, MODEL_CARD, MORTALITY_HISTORY, SEASONAL_HISTORY

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
SERIES_KEYS = ("health_index", "health_band", "ndvi", "ndmi")


class LiveNotReady(Exception):
    def __init__(self, status: dict):
        super().__init__("live layer not ready")
        self.status = status


def _need(path) -> None:
    if not path.exists():
        raise FileNotFoundError(path.name)


def _read(path):
    return json.loads(path.read_text()) if path.exists() else None


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


@lru_cache(maxsize=1)
def _mortality():
    return _read(MORTALITY_HISTORY)


@lru_cache(maxsize=1)
def _seasonal():
    return _read(SEASONAL_HISTORY)


@lru_cache(maxsize=1)
def _timeline() -> dict:
    hist, seasonal, mort, props = _history(), _seasonal(), _mortality(), _props_by_patch()
    years = sorted({r["year"] for rows in hist.values() for r in rows})
    frames = [{"id": f"{y}-summer", "season": "summer", "year": y,
               "label": f"Summer {y} (Jun-Sep)", "window": [f"{y}-06-01", f"{y}-10-01"]}
              for y in years]
    seasonal_ids = []
    if seasonal:
        frames += seasonal["frames"]
        seasonal_ids = [f["id"] for f in seasonal["frames"]]
    frames.sort(key=lambda f: f["window"][1])
    pos = {f["id"]: i for i, f in enumerate(frames)}
    n = len(frames)
    mort_years = mort["years"] if mort else []

    patches = {}
    for pid, rows in hist.items():
        s = {k: [None] * n for k in SERIES_KEYS + ("data_quality", "mortality_likelihood",
                                                    "mortality_percentile")}
        for r in rows:
            i = pos[f"{r['year']}-summer"]
            for k in SERIES_KEYS:
                s[k][i] = r[k]
        sp = seasonal["patches"].get(pid) if seasonal else None
        if sp:
            for j, fid in enumerate(seasonal_ids):
                for k in SERIES_KEYS + ("data_quality",):
                    s[k][pos[fid]] = sp[k][j]
        mp = mort["patches"].get(pid) if mort else None
        if mp:
            for j, y in enumerate(mort_years):
                i = pos.get(f"{y}-summer")
                if i is not None:
                    s["mortality_likelihood"][i] = mp["likelihood"][j]
                    s["mortality_percentile"][i] = mp["percentile"][j]
        p = props.get(pid, {})
        s["burn_status"], s["trend_label"] = p.get("burn_status"), p.get("trend_label")
        patches[pid] = s

    notes = ["Summer frames share one fixed scale (unburned patches, all summers), so colours are comparable across years."]
    if seasonal:
        notes.append("Autumn, winter and spring frames are scored against unburned patches of the same season: "
                     "compare the same season across years, not different seasons.")
    if mort:
        notes.append("Mortality likelihood exists for summer frames only. Climate inputs per year: "
                     + json.dumps(mort.get("climate_year", {})))
    return {"frames": frames, "patches": patches, "notes": notes}


def latest_summer_id() -> str:
    years = [f["year"] for f in _timeline()["frames"] if f["season"] == "summer"]
    return f"{max(years)}-summer"


@lru_cache(maxsize=32)
def _layer_for_frame(frame_id: str) -> dict:
    tl = _timeline()
    ids = [f["id"] for f in tl["frames"]]
    if frame_id not in ids:
        raise KeyError(frame_id)
    i = ids.index(frame_id)
    fr = tl["frames"][i]
    feats = []
    cut = (_read(MODEL_CARD) or {}).get("bands")
    for f in _layer()["features"]:
        p = dict(f["properties"])
        p.update({"frame": frame_id, "season": fr["season"], "year": fr["year"],
                  "period": f"{fr['window'][0]}/{fr['window'][1]}",
                  "observed_at": fr["window"][1] + "T00:00:00Z"})
        s = tl["patches"].get(p["patch_id"])
        if s:
            for k in SERIES_KEYS + ("mortality_likelihood", "mortality_percentile"):
                p[k] = s[k][i]
            if p["health_band"] is None:
                p["health_band"] = "Not scored"
            lk = p.get("mortality_likelihood")
            p["mortality_band"] = (None if lk is None or not cut else
                                   "High" if lk >= cut["high"] else
                                   "Elevated" if lk >= cut["elevated"] else "Lower")
        feats.append({"type": "Feature", "geometry": f["geometry"], "properties": p})
    return {"type": "FeatureCollection", "features": feats}


_SEEN = {}


def _refresh_if_changed() -> None:
    """Reload cached files when they have been rebuilt on disk."""
    sig = tuple(p.stat().st_mtime if p.exists() else None
                for p in (LATEST, HISTORY, MORTALITY_HISTORY, SEASONAL_HISTORY))
    if _SEEN.get("sig") != sig:
        reload_data()
        _SEEN["sig"] = sig


def get_layer(period: str = "summer", frame: str | None = None) -> dict:
    _refresh_if_changed()
    if period == "live":
        layer, _, _, status = live_service.get_live()
        if layer is None:
            raise LiveNotReady(status)
        return layer
    return _layer_for_frame(frame or latest_summer_id())


def get_timeline() -> dict:
    _refresh_if_changed()
    return _timeline()


def get_patch_timeline(patch_id: str) -> dict | None:
    _refresh_if_changed()
    tl = _timeline()
    s = tl["patches"].get(patch_id)
    if s is None:
        return None
    return {"patch_id": patch_id, "frames": tl["frames"], "series": s, "notes": tl["notes"]}


def get_status() -> dict:
    _refresh_if_changed()
    summer = None
    if LATEST.exists():
        first = _layer()["features"][0]["properties"]
        summer = {"year": first["year"], "period": first["period"],
                  "generated_at": first["generated_at"], "model_version": first["model_version"],
                  "frames": [f["id"] for f in _timeline()["frames"]]}
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
        for k in ("mortality_likelihood", "mortality_percentile", "mortality_band", "model_status",
                  "mortality_model_version", "mortality_model_window", "mortality_climate_year"):
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
    for fn in (_layer, _history, _props_by_patch, _mortality, _seasonal, _timeline, _layer_for_frame):
        fn.cache_clear()