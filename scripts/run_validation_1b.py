"""
run_validation_1b.py -- Version 1b: does wind that CHANGES hour by hour beat one average direction?

Run from the repo root, after run_validation.py (it reuses its downloads and results):
    python scripts/run_validation_1b.py "data/raw/California_Historic_Fire_Perimeters_-4891938132824355098.geojson"
    (add --runs 5 for a quick try; the default is 10 runs per setting, like run_validation.py)

Rules, fixed before any 1b score was looked at (same fires and same tune/test split as run_validation.py):
  * Wind sequence: the hourly Open-Meteo winds, in time order, for the 48 hours after the first detection.
  * PRIMARY (arm "dry"): only hours with humidity below 25 % are used, in order (the fire is assumed to
    spread only when the air is dry); if fewer than 6 such hours exist, all 48 hours are used.
    This is the same hour selection as Version 1a, so the only change is "sequence" instead of "average".
  * SECONDARY (arm "all", exploratory): all 48 hours in order.
  * Strength in hour h = k * (speed in hour h / mean speed over the used hours), so calm hours push the
    fire less and windy hours more, and the average strength over the sequence is k.
  * The model has no clock, so time is taken to be proportional to the area burned.
  * k is chosen on the TUNE fires (best mean IoU), for each arm separately; the TEST fires are reported
    at that k next to Version 1a (static average wind, k = 1) and the round-fire baseline.
Results are saved per fire in data/samples/validation/results/, so a re-run carries on where it stopped.
Writes data/processed/validation_results_1b.csv.
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

OUT = Path("data/processed/validation_results_1b.csv")
K_VALUES = rv.K_VALUES


def hour_sequences(weather: pd.DataFrame, first_detection: pd.Timestamp) -> dict:
    """The two pre-registered hour selections, each as a list of (toward_deg, speed_ms) in time order."""
    t0 = first_detection.floor("h")
    t0 = t0.tz_localize(None) if t0.tzinfo else t0
    win = weather[(weather.time_utc >= t0) & (weather.time_utc < t0 + pd.Timedelta(hours=rv.WIND_WINDOW_HOURS))]
    win = win.dropna(subset=["wind_ms", "wind_from_deg"])
    if win.empty:
        raise ValueError("no wind data in the window")
    dry = win[win.rh_pct < rv.DRY_RH]
    primary = dry if len(dry) >= rv.MIN_DRY_HOURS else win

    def seq(df):
        return [((float(f) + 180.0) % 360.0, float(s)) for f, s in zip(df.wind_from_deg, df.wind_ms)]
    return {"dry": seq(primary), "all": seq(win), "dry_mode": "dry" if primary is dry else "all"}


def schedule(hours: list, k: float) -> list:
    """(toward, speed) per hour -> (toward, k_h) with average strength k."""
    mean_speed = float(np.mean([s for _, s in hours])) or 1.0
    return [(toward, k * speed / mean_speed) for toward, speed in hours]


def evaluate_fire(geom_m, ign_xy, hours_by_arm: dict, runs: int) -> dict:
    radius = math.sqrt(geom_m.area / math.pi)
    region = shapely.union_all([geom_m, Point(ign_xy)])
    domain = make_domain(region, (geom_m.centroid.x, geom_m.centroid.y), margin=2.5 * radius + 500)
    real = rasterize(geom_m, domain)
    target = int(real.sum())
    res = {"baseline": iou(circle_baseline(domain, ign_xy, target), real)}
    edge = 0
    for arm in ("dry", "all"):
        for k in K_VALUES:
            vals = []
            for seed in range(runs):
                sim = simulate(domain, ign_xy, target, seed=seed, wind_schedule=schedule(hours_by_arm[arm], k))
                vals.append(iou(sim, real))
                edge += touches_edge(sim)
            res[f"{arm}_k{k:g}"] = float(np.mean(vals))
    res["edge_hits"] = edge
    return res


def summarise(df: pd.DataFrame, old: pd.DataFrame) -> None:
    tune, test = df[df.split == "tune"], df[df.split == "test"]
    for arm, label in (("dry", "PRIMARY: dry hours in order"), ("all", "SECONDARY (exploratory): all 48 hours in order")):
        cols = [f"{arm}_k{k:g}" for k in K_VALUES]
        means = tune[cols].mean()
        best = means.idxmax()
        print(f"\n=== {label} ===")
        print("Tune fires, mean IoU by k: " + "  ".join(f"k={c.split('_k')[1]}: {means[c]:.3f}" for c in cols))
        print(f"-> chosen k = {best.split('_k')[1]}   (tune round-fire baseline {tune.baseline.mean():.3f}, "
              f"Version 1a at its k=1: {tune.v1a_k1.mean():.3f})")
        show = test[["fire_name", "year", "shape_class", "baseline", "v1a_k1", best]].copy()
        show.columns = ["fire", "year", "shape", "round baseline", "1a (avg wind, k=1)", f"1b ({best.split('_')[0]} k={best.split('_k')[1]})"]
        print(show.round(3).to_string(index=False))
        m = test[best].mean()
        print(f"Test fires: mean IoU 1b {m:.3f} | 1a {test.v1a_k1.mean():.3f} | round baseline {test.baseline.mean():.3f}")
        print(f"1b beats 1a on {int((test[best] > test.v1a_k1).sum())} of {len(test)} test fires; "
              f"beats the round baseline on {int((test[best] > test.baseline).sum())} of {len(test)}")
    if int(df.edge_hits.sum()):
        print(f"\nNote: {int(df.edge_hits.sum())} runs touched the edge of the simulation area (mostly high k).")


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
        cache = rv.RESULT_DIR / f"{f.key}_1b_runs{a.runs}.json"
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
            seqs = hour_sequences(rv.fetch_weather(f.key, centre.y, centre.x, d0, d1), first)
        except (RuntimeError, FirmsError, ValueError) as e:
            print(f"[{i + 1}/{len(sel)}] {f.key}: stopped ({e}). Run again to resume.")
            break
        t = time.time()
        res = evaluate_fire(geom, ign, seqs, a.runs)
        row = {"key": f.key, "fire_name": f.fire_name, "year": int(f.year), "shape_class": f.shape_class,
               "split": f.split, "elongation": f.elongation, "area_km2": f.area_km2,
               "hours_dry_arm": len(seqs["dry"]), "dry_arm_mode": seqs["dry_mode"],
               "v1a_k1": float(old.loc[f.key, "k1"]),
               **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in res.items()}}
        cache.write_text(json.dumps(row))
        rows.append(row)
        print(f"[{i + 1}/{len(sel)}] {f.key} ({f.split}): {len(seqs['dry'])} h in the dry arm ({seqs['dry_mode']}), "
              f"baseline {res['baseline']:.2f}, 1a k=1 {row['v1a_k1']:.2f}, 1b dry k=1 {res['dry_k1']:.2f}  [{time.time() - t:.0f} s]")

    df = pd.DataFrame(rows)
    if len(df) < len(sel):
        print(f"\nOnly {len(df)} of {len(sel)} fires done. Run the same command again to finish.")
        return
    df.to_csv(OUT, index=False)
    summarise(df, old)
    print(f"\nSaved {OUT}")


if __name__ == "__main__":
    main()
