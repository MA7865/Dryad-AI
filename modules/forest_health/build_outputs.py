"""
build_outputs.py -- M1: scores the feature table and writes the files the backend serves.

Run from the repo root:
    python -m modules.forest_health.build_outputs
    python -m modules.forest_health.build_outputs --refit   # recompute the 0-100 scale

Reads : data/processed/m1_features_2022_2026.csv, data/grid.geojson
Writes: data/processed/m1_reference_bounds.json        (the saved 0-100 scale)
        data/processed/m1_health_by_patch_year.csv     (full scored table)
        data/processed/m1_forest_health_latest.geojson (map layer, latest summer)
        data/processed/m1_patch_history.json           (per-patch history for the click panel)
        data/samples/forest_health_sample.geojson      (3 example patches)
"""
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .scoring import score_table
from .paths import BOUNDS_FILE, CACHE, FEATURES, GRID, HISTORY, LATEST, ROOT, SAMPLE

OUT_TABLE = CACHE / "m1_health_by_patch_year.csv"
OUT_LATEST = LATEST
OUT_HISTORY = HISTORY
OUT_SAMPLE = SAMPLE

MODEL_VERSION = "m1-index-v1"
SOURCE = "Sentinel-2 SR Harmonized; ESA WorldCover v200; MODIS MCD64A1"


def clean(v):
    """Python/JSON-safe value: NaN becomes None, numpy numbers become plain numbers."""
    if v is None:
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, float):          # np.float64 is a float too
        return None if math.isnan(v) else float(v)
    return v


def rnd(v, digits):
    v = clean(v)
    return None if v is None else round(v, digits)


def health_int(v):
    v = clean(v)
    return None if v is None else int(round(v))


def main() -> None:
    refit = "--refit" in sys.argv
    df = pd.read_csv(FEATURES)

    saved = None
    if BOUNDS_FILE.exists() and not refit:
        saved = {k: tuple(v) for k, v in json.loads(BOUNDS_FILE.read_text()).items()}
        print("Using saved scale:", BOUNDS_FILE.name)

    scored, trends, bounds = score_table(df, saved)
    if saved is None:
        BOUNDS_FILE.write_text(json.dumps({k: list(v) for k, v in bounds.items()}, indent=2))
        print("Saved new scale to", BOUNDS_FILE.name)

    latest_year = int(scored["year"].max())
    latest = scored[scored["year"] == latest_year].set_index("patch_id")
    trend_by_patch = trends.set_index("patch_id")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1) Full scored table
    cols = ["patch_id", "year", "ndvi", "ndmi", "nbr", "health_index", "health_band",
            "burn_frac", "burn_status", "forest_frac", "valid", "data_quality", "peer_rel"]
    scored[cols].round(4).to_csv(OUT_TABLE, index=False)

    # 2) Map layer: shared grid geometry + M1 properties for the latest summer
    grid = json.loads(GRID.read_text())
    features = []
    for f in grid["features"]:
        gp = f["properties"]
        pid = gp["patch_id"]
        r, t = latest.loc[pid], trend_by_patch.loc[pid]
        props = {
            "patch_id": pid, "row": gp["row"], "col": gp["col"],
            "center_lon": gp["center_lon"], "center_lat": gp["center_lat"],
            "layer_type": "forest_health",
            "year": latest_year,
            "period": f"{latest_year}-06-01/{latest_year}-09-30",
            "observed_at": f"{latest_year}-09-30T00:00:00Z",
            "generated_at": generated_at,
            "model_version": MODEL_VERSION,
            "source": SOURCE,
            "data_kind": "derived_index",
            "health_index": health_int(r["health_index"]),
            "health_band": r["health_band"],
            "ndvi": rnd(r["ndvi"], 3),
            "ndmi": rnd(r["ndmi"], 3),
            "trend_slope": rnd(t["trend_slope"], 2),
            "trend_label": t["trend_label"],
            "years_used": int(t["years_used"]),
            "burn_status": r["burn_status"],
            "burn_frac": rnd(r["burn_frac"], 2),
            "forest_frac": rnd(r["forest_frac"], 2),
            "data_quality": r["data_quality"],
        }
        features.append({"type": "Feature", "geometry": f["geometry"], "properties": props})

    collection = {"type": "FeatureCollection", "features": features}
    OUT_LATEST.write_text(json.dumps(collection, separators=(",", ":"), allow_nan=False))

    # 3) Per-patch history for the click panel
    history = {}
    for pid, g in scored.sort_values("year").groupby("patch_id"):
        history[pid] = [
            {"year": int(y), "health_index": health_int(h), "health_band": b,
             "ndvi": rnd(n, 3), "ndmi": rnd(m, 3)}
            for y, h, b, n, m in zip(g["year"], g["health_index"], g["health_band"],
                                     g["ndvi"], g["ndmi"])
        ]
    OUT_HISTORY.write_text(json.dumps(history, separators=(",", ":"), allow_nan=False))

    # 4) Tiny sample for tests and the frontend: one patch from each of three bands
    sample = []
    for band in ("Healthy", "High stress", "Post-fire recovery"):
        hit = [x for x in features if x["properties"]["health_band"] == band]
        if hit:
            sample.append(hit[0])
    OUT_SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    OUT_SAMPLE.write_text(json.dumps({"type": "FeatureCollection", "features": sample},
                                     indent=2, allow_nan=False))

    # Summary (copy this into your docs later)
    print(f"\nLatest summer: {latest_year}   patches: {len(features)}")
    print("\nBands:")
    print(latest["health_band"].value_counts().to_string())
    print("\nTrend label by burn status:")
    print(pd.crosstab(trends["burn_status"], trends["trend_label"]).to_string())
    print("\nWrote:")
    for p in (BOUNDS_FILE, OUT_TABLE, OUT_LATEST, OUT_HISTORY, OUT_SAMPLE):
        print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()