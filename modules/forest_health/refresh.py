"""
refresh.py -- M1: builds the live layer from Earth Engine.

build_live(days)  -> (layer, meta); used by the API in the background
python -m modules.forest_health.refresh [--days 45]   builds it and saves a copy in data/cache
"""
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from . import live_gee
from .build_outputs import health_int, rnd
from .paths import CACHE, GRID, LIVE, LIVE_META
from .scoring import score_table

MIN_OBS = 3            # fewer clear observations per pixel than this = "limited"
MODEL_VERSION = "m1-index-v1-live"
SOURCE = "Sentinel-2 SR Harmonized (live window); ESA WorldCover v200; MODIS MCD64A1"


def build_live(days: int = 30):
    newest = live_gee.latest_scene_date()
    end = (date.fromisoformat(newest) + timedelta(days=1)).isoformat()
    start = (date.fromisoformat(newest) - timedelta(days=days - 1)).isoformat()

    df = live_gee.fetch_window_features(start, end)
    n_scenes = df.attrs["n_scenes"]

    # Scored against the unburned patches in THIS window (peer-relative), so the
    # seasonal shift common to the whole area cancels out.
    scored, _, bounds = score_table(df)
    low_obs = scored["obs_count"].fillna(0) < MIN_OBS
    scored.loc[(scored["data_quality"] == "good") & low_obs, "data_quality"] = "limited"

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live = scored.set_index("patch_id")
    features = []
    for f in json.loads(GRID.read_text())["features"]:
        gp = f["properties"]
        r = live.loc[gp["patch_id"]]
        props = {
            "patch_id": gp["patch_id"], "row": gp["row"], "col": gp["col"],
            "center_lon": gp["center_lon"], "center_lat": gp["center_lat"],
            "layer_type": "forest_health", "mode": "live",
            "window_start": start, "window_end": end,
            "observed_at": f"{newest}T00:00:00Z", "generated_at": generated_at,
            "model_version": MODEL_VERSION, "source": SOURCE,
            "data_kind": "derived_index", "n_scenes": int(n_scenes),
            "health_index": health_int(r["health_index"]),
            "health_band": r["health_band"],
            "ndvi": rnd(r["ndvi"], 3), "ndmi": rnd(r["ndmi"], 3),
            "burn_status": r["burn_status"], "burn_frac": rnd(r["burn_frac"], 2),
            "forest_frac": rnd(r["forest_frac"], 2),
            "obs_count": rnd(r["obs_count"], 1),
            "data_quality": r["data_quality"],
        }
        features.append({"type": "Feature", "geometry": f["geometry"], "properties": props})

    layer = {"type": "FeatureCollection", "features": features}
    meta = {
        "mode": "live", "window_start": start, "window_end": end,
        "newest_scene": newest, "n_scenes": int(n_scenes),
        "generated_at": generated_at,
        "scored_patches": int(scored["health_index"].notna().sum()),
        "reference": "unburned patches in the same window",
        "reference_bounds": {k: list(v) for k, v in bounds.items()},
    }
    return layer, meta


def main() -> None:
    days = 30
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    layer, meta = build_live(days)
    CACHE.mkdir(parents=True, exist_ok=True)
    LIVE.write_text(json.dumps(layer, separators=(",", ":"), allow_nan=False))
    LIVE_META.write_text(json.dumps(meta, indent=2))
    props = [f["properties"] for f in layer["features"]]
    print(f"Window {meta['window_start']} to {meta['window_end']} | scenes {meta['n_scenes']} "
          f"| scored {meta['scored_patches']}")
    print("Bands:", dict(Counter(p["health_band"] for p in props)))
    print("Quality:", dict(Counter(p["data_quality"] for p in props)))
    print("Wrote", LIVE.name, "and", LIVE_META.name, "in", CACHE)


if __name__ == "__main__":
    main()