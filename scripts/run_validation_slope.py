"""
run_validation_slope.py -- Version 2: does adding SLOPE improve the wind model on the 12 validation fires?

Run from the repo root, after run_validation.py (it reuses its downloads and results). Needs internet the
first time: it downloads elevation tiles (about 30 to 60 MB in total, cached in data/raw/terrain/).
    python scripts/run_validation_slope.py "data/raw/California_Historic_Fire_Perimeters_-4891938132824355098.geojson"
    (add --runs 5 for a quick try; the default is 10 runs per setting, like the other validation scripts)

Rules, fixed before any slope score was looked at (same 12 fires and same tune/test split as run_validation.py):
  * Elevation: AWS terrain tiles (Terrarium, zoom 12, about 30 m), averaged onto the 90 m grid.
  * Slope effect: fire moving from a cell to a neighbour is multiplied by exp(b * rise / run), with
    rise / run capped at +-1. Uphill faster, downhill slower. b = 0 is exactly Version 1a.
  * PRIMARY arm "wind+slope": Version 1a wind (average of the dry hours, as before) with k fixed at 1,
    the value chosen on the tune fires in run_validation.py. b in {0, 1, 2, 3, 4}.
  * SECONDARY arm "slope only" (exploratory): no wind (k = 0), same b values. Shows what slope does alone.
  * b is chosen on the TUNE fires only (best mean IoU), separately for each arm. The TEST fires are reported
    at that b next to b = 0 (Version 1a) and the round-fire baseline.
Results are saved per fire in data/samples/validation/results/, so a re-run carries on where it stopped.
Writes data/processed/validation_results_slope.csv.
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Point

import run_validation as rv  # noqa: E402
from count_candidate_detections import count_on_fire, detections_for, load_perimeters  # noqa: E402
from modules.fire_monitoring.firms_client import FirmsError  # noqa: E402
from modules.fire_monitoring.spread_v0 import (  # noqa: E402
    CRS_LL, CRS_M, circle_baseline, iou, make_domain, rasterize, simulate, touches_edge)
from modules.fire_monitoring.terrain import TerrainError, get_elevation  # noqa: E402

OUT = Path("data/processed/validation_results_slope.csv")
ELEV_DIR = rv.CACHE_DIR / "elevation"
B_VALUES = [0, 1, 2, 3, 4]
K_FIXED = 1.0
ARMS = (("ws", K_FIXED, "wind + slope (k = 1)"), ("so", 0.0, "slope only (k = 0)"))


def build_domain(geom_m, ign_xy):
    """Identical to run_validation.evaluate_fire, so the results line up with the earlier tables."""
    radius = math.sqrt(geom_m.area / math.pi)
    region = shapely.union_all([geom_m, Point(ign_xy)])
    return make_domain(region, (geom_m.centroid.x, geom_m.centroid.y), margin=2.5 * radius + 500)


def cached_elevation(key: str, domain) -> np.ndarray:
    ELEV_DIR.mkdir(parents=True, exist_ok=True)
    path = ELEV_DIR / f"{key}.npy"
    if path.exists():
        elev = np.load(path)
        if elev.shape == domain.shape:
            return elev
    elev = get_elevation(domain)
    np.save(path, elev)
    return elev


def terrain_summary(elev: np.ndarray, real: np.ndarray, cell: int) -> dict:
    gy, gx = np.gradient(elev, cell)
    slope_deg = np.degrees(np.arctan(np.hypot(gx, gy)))
    return {"relief_m": round(float(elev[real].max() - elev[real].min())),
            "mean_slope_deg": round(float(slope_deg[real].mean()), 1)}


def evaluate_fire(key, geom_m, ign_xy, toward, runs: int) -> dict:
    domain = build_domain(geom_m, ign_xy)
    real = rasterize(geom_m, domain)
    target = int(real.sum())
    elev = cached_elevation(key, domain)
    res = {"baseline": iou(circle_baseline(domain, ign_xy, target), real), **terrain_summary(elev, real, domain.cell)}
    edge = 0
    for arm, k, _ in ARMS:
        for b in B_VALUES:
            vals = []
            for seed in range(runs):
                sim = simulate(domain, ign_xy, target, seed=seed, wind_toward_deg=toward, wind_k=k,
                               elevation=elev, slope_b=b)
                vals.append(iou(sim, real))
                edge += touches_edge(sim)
            res[f"{arm}_b{b:g}"] = float(np.mean(vals))
    res["edge_hits"] = edge
    return res


def summarise(df: pd.DataFrame, old: pd.DataFrame) -> None:
    tune, test = df[df.split == "tune"], df[df.split == "test"]
    check = (df.set_index("key")["ws_b0"] - old.loc[df.key, "k1"]).abs().max()
    print(f"\nCheck: with b = 0 the wind+slope arm reproduces the earlier k = 1 scores (largest difference {check:.4f}; should be about 0).")
    for arm, k, label in ARMS:
        cols = [f"{arm}_b{b:g}" for b in B_VALUES]
        means = tune[cols].mean()
        best = means.idxmax()
        print(f"\n=== {label.upper()} ===")
        print("Tune fires, mean IoU by b: " + "  ".join(f"b={c.split('_b')[1]}: {means[c]:.3f}" for c in cols))
        print(f"-> chosen b = {best.split('_b')[1]}   (tune round-fire baseline {tune.baseline.mean():.3f})")
        show = test[["fire_name", "year", "shape_class", "mean_slope_deg", "baseline", f"{arm}_b0", best]].copy()
        show.columns = ["fire", "year", "shape", "mean slope (deg)", "round baseline", "b = 0", f"slope ({best.split('_')[1]})"]
        print(show.round(3).to_string(index=False))
        m = test[best].mean()
        print(f"Test fires: mean IoU with slope {m:.3f} | b = 0 {test[f'{arm}_b0'].mean():.3f} | round baseline {test.baseline.mean():.3f}")
        print(f"Slope beats b = 0 on {int((test[best] > test[f'{arm}_b0']).sum())} of {len(test)} test fires; "
              f"beats the round baseline on {int((test[best] > test.baseline).sum())} of {len(test)}")
        print(f"All 12 fires: with slope {df[best].mean():.3f} | b = 0 {df[f'{arm}_b0'].mean():.3f} | round baseline {df.baseline.mean():.3f}; "
              f"slope beats b = 0 on {int((df[best] > df[f'{arm}_b0']).sum())} of {len(df)}")
    # per-fire table: every fire, b = 0 / 2 / 4, both arms (b is chosen on the tune fires; this is for reading only)
    full = df[["fire_name", "year", "split", "relief_m", "mean_slope_deg", "baseline",
               "ws_b0", "ws_b2", "ws_b4", "so_b0", "so_b2", "so_b4"]].copy()
    full.columns = ["fire", "year", "split", "relief (m)", "slope (deg)", "baseline",
                    "wind b0", "wind b2", "wind b4", "slope-only b0", "slope-only b2", "slope-only b4"]
    print("\nAll 12 fires (wind + slope arm: 'wind'; slope-only arm: 'slope-only'):")
    print(full.round(3).to_string(index=False))
    if int(df.edge_hits.sum()):
        print(f"\nNote: {int(df.edge_hits.sum())} runs touched the edge of the simulation area (mostly high b).")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("perimeters")
    ap.add_argument("--runs", type=int, default=10)
    a = ap.parse_args()
    if not rv.SELECTED.exists() or not rv.OUT.exists():
        sys.exit("Run scripts/run_validation.py first.")
    sel = pd.read_csv(rv.SELECTED)
    sel = sel[sel.selected].reset_index(drop=True)
    sel["split"] = rv.assign_split(sel)
    old = pd.read_csv(rv.OUT).set_index("key")
    perims = load_perimeters(Path(a.perimeters))

    rows = []
    for i, f in sel.iterrows():
        cache = rv.RESULT_DIR / f"{f.key}_slope_runs{a.runs}.json"
        if cache.exists():
            rows.append(json.loads(cache.read_text()))
            print(f"[{i + 1}/{len(sel)}] {f.key}: cached")
            continue
        geom = perims.loc[f.key].geometry
        try:
            on = count_on_fire(detections_for(f.key, geom, f.alarm_date), geom)
            ign, _ = rv.estimate_ignition(on, geom)
            centre = gpd.GeoSeries([geom.centroid], crs=CRS_M).to_crs(CRS_LL).iloc[0]
            first = on["time_utc"].min()
            d0 = (first - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            d1 = (first + pd.Timedelta(days=3)).strftime("%Y-%m-%d")
            wind = rv.wind_for(rv.fetch_weather(f.key, centre.y, centre.x, d0, d1), first)
            t = time.time()
            res = evaluate_fire(f.key, geom, ign, wind["toward"], a.runs)
        except (RuntimeError, FirmsError, ValueError, TerrainError) as e:
            print(f"[{i + 1}/{len(sel)}] {f.key}: stopped ({e}). Run again to resume.")
            break
        row = {"key": f.key, "fire_name": f.fire_name, "year": int(f.year), "shape_class": f.shape_class,
               "split": f.split, "elongation": f.elongation, "area_km2": f.area_km2,
               **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in res.items()}}
        cache.write_text(json.dumps(row))
        rows.append(row)
        print(f"[{i + 1}/{len(sel)}] {f.key} ({f.split}): relief {res['relief_m']} m, mean slope {res['mean_slope_deg']} deg, "
              f"baseline {res['baseline']:.2f}, b=0 {res['ws_b0']:.2f}, b=2 {res['ws_b2']:.2f}  [{time.time() - t:.0f} s]")

    df = pd.DataFrame(rows)
    if len(df) < len(sel):
        print(f"\nOnly {len(df)} of {len(sel)} fires done. Run the same command again to finish.")
        return
    df.to_csv(OUT, index=False)
    summarise(df, old)
    print(f"\nSaved {OUT}")


if __name__ == "__main__":
    main()
