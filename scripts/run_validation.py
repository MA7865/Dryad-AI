"""
run_validation.py -- does the wind model work on fires other than Goose?

Run from the repo root (after count_candidate_detections.py):
    python scripts/run_validation.py "data/raw/California_Historic_Fire_Perimeters_-4891938132824355098.geojson"
    (add --runs 5 for a quick first try; the default is 10 runs per setting)

Protocol, fixed before any model score was looked at:
  1. Fires: the SELECTED rows of data/processed/validation_detections.csv (12 fires).
  2. Split: within each shape class (round / medium / long), fires sorted by year then name are
     alternately assigned TUNE, TEST, TUNE, ... so both sets contain every shape class.
  3. Ignition point (estimated): the average position of the satellite detections in the first 6 hours
     after the first detection, moved just inside the perimeter if it falls outside.
  4. Wind: Open-Meteo hourly wind at the fire's centre for the 48 hours starting at the first detection.
     Only hours with relative humidity below 25 % are averaged (as vectors); if fewer than 6 such hours
     exist, all 48 hours are used. This rule is applied the same way to every fire.
  5. Model: the wind model of Version 1a, wind strength k in {0, 0.5, 1, 2, 3, 4}, area given to the
     model (as for Goose). Score = IoU with the real perimeter, averaged over --runs random seeds.
  6. k is chosen on the TUNE fires only (best mean IoU). The TEST fires are then reported at that k,
     next to k = 0 (no wind) and the round-fire baseline from the same start point.
Results are saved per fire in data/samples/validation/results/, so a re-run after an interruption
carries on where it stopped. Final table: data/processed/validation_results.csv.
Install once:  pip install geopandas pyogrio shapely pandas pyproj requests numpy
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
import requests
import shapely
from shapely.geometry import Point

from count_candidate_detections import CACHE_DIR, count_on_fire, detections_for, load_perimeters  # noqa: E402
from fetch_goose_weather import HOURLY, URLS, compass, mean_wind, to_frame  # noqa: E402
from modules.fire_monitoring.firms_client import FirmsError  # noqa: E402
from modules.fire_monitoring.spread_v0 import (  # noqa: E402
    CRS_LL, CRS_M, circle_baseline, iou, make_domain, rasterize, simulate, snap_into_perimeter, touches_edge)

SELECTED = Path("data/processed/validation_detections.csv")
OUT = Path("data/processed/validation_results.csv")
WEATHER_DIR = CACHE_DIR / "weather"
RESULT_DIR = CACHE_DIR / "results"
K_VALUES = [0, 0.5, 1, 2, 3, 4]
FIRST_PASS_HOURS = 6
WIND_WINDOW_HOURS = 48
DRY_RH, MIN_DRY_HOURS = 25.0, 6


def assign_split(sel: pd.DataFrame) -> pd.Series:
    """TUNE / TEST alternately within each shape class (sorted by year, then name)."""
    split = pd.Series("", index=sel.index)
    for _, grp in sel.groupby("shape_class"):
        order = grp.sort_values(["year", "fire_name"]).index
        for i, idx in enumerate(order):
            split[idx] = "tune" if i % 2 == 0 else "test"
    return split


def estimate_ignition(on: pd.DataFrame, geom_m):
    """Average position of detections in the first FIRST_PASS_HOURS hours, snapped inside the perimeter."""
    first = on["time_utc"].min()
    early = on[on["time_utc"] <= first + pd.Timedelta(hours=FIRST_PASS_HOURS)]
    xy = (float(early["x_m"].mean()), float(early["y_m"].mean()))
    return snap_into_perimeter(geom_m, xy), len(early)


def fetch_weather(key: str, lat: float, lon: float, start: str, end: str, retries: int = 2) -> pd.DataFrame:
    """Hourly Open-Meteo archive data (UTC), cached per fire."""
    WEATHER_DIR.mkdir(parents=True, exist_ok=True)
    cache = WEATHER_DIR / f"{key}.csv"
    if cache.exists():
        return pd.read_csv(cache, parse_dates=["time_utc"])
    params = {"latitude": round(lat, 4), "longitude": round(lon, 4), "start_date": start, "end_date": end,
              "hourly": ",".join(HOURLY), "wind_speed_unit": "ms", "timezone": "UTC"}
    problem = "unknown problem"
    for url in URLS:
        for attempt in range(retries + 1):
            try:
                resp = requests.get(url, params=params, timeout=60)
            except requests.RequestException as exc:
                problem = f"network problem ({type(exc).__name__})"
            else:
                if resp.status_code == 200 and not resp.json().get("error"):
                    df = to_frame(resp.json())
                    df.to_csv(cache, index=False)
                    time.sleep(0.3)
                    return df
                problem = f"HTTP {resp.status_code}: {resp.text[:150]}"
                if resp.status_code < 500 and resp.status_code != 429:
                    break
            time.sleep(1.5 * 2 ** attempt)
    raise RuntimeError(f"Open-Meteo failed ({problem})")


def wind_for(weather: pd.DataFrame, first_detection: pd.Timestamp):
    """Vector-average wind for the 48 h from the first detection: dry hours if there are enough."""
    t0 = first_detection.floor("h").tz_localize(None) if first_detection.tzinfo else first_detection.floor("h")
    win = weather[(weather.time_utc >= t0) & (weather.time_utc < t0 + pd.Timedelta(hours=WIND_WINDOW_HOURS))]
    win = win.dropna(subset=["wind_ms", "wind_from_deg"])
    dry = win[win.rh_pct < DRY_RH]
    mode, used = ("dry", dry) if len(dry) >= MIN_DRY_HOURS else ("all", win)
    if used.empty:
        raise ValueError("no wind data in the window")
    toward, speed, steady = mean_wind(list(used.wind_ms), list(used.wind_from_deg))
    return {"toward": toward, "from": (toward + 180) % 360, "speed": speed, "steady": steady,
            "hours": len(used), "mode": mode}


def evaluate_fire(geom_m, ign_xy, toward, runs: int) -> dict:
    """Mean IoU for each k, the round-fire baseline from the same start, and edge-touching counts."""
    radius = math.sqrt(geom_m.area / math.pi)
    region = shapely.union_all([geom_m, Point(ign_xy)])
    domain = make_domain(region, (geom_m.centroid.x, geom_m.centroid.y), margin=2.5 * radius + 500)
    real = rasterize(geom_m, domain)
    target = int(real.sum())
    res = {"target_cells": target, "baseline": iou(circle_baseline(domain, ign_xy, target), real)}
    edge = 0
    for k in K_VALUES:
        vals = []
        for seed in range(runs):
            sim = simulate(domain, ign_xy, target, seed=seed, wind_toward_deg=toward, wind_k=k)
            vals.append(iou(sim, real))
            edge += touches_edge(sim)
        res[f"k{k:g}"] = float(np.mean(vals))
    res["edge_hits"] = edge
    return res


def summarise(df: pd.DataFrame) -> None:
    cols = [f"k{k:g}" for k in K_VALUES]
    tune, test = df[df.split == "tune"], df[df.split == "test"]
    print("\n=== Step 1: choose k on the TUNE fires only (mean IoU over the tune fires) ===")
    means = tune[cols].mean()
    for c in cols:
        print(f"  {c:>6}: {means[c]:.3f}")
    print(f"  round-fire baseline (same start): {tune.baseline.mean():.3f}")
    best = means.idxmax()
    print(f"  -> chosen k = {best[1:]}")
    print("\n=== Step 2: the TEST fires, scored at the chosen k ===")
    show = test[["fire_name", "year", "shape_class", "area_km2", "baseline", "k0", best]].copy()
    show.columns = ["fire", "year", "shape", "km2", "round baseline", "no wind (k=0)", f"wind ({best})"]
    print(show.round(3).to_string(index=False))
    wins_base = int((test[best] > test.baseline).sum())
    wins_k0 = int((test[best] > test.k0).sum())
    print(f"\nTest fires: {len(test)} | wind beats round baseline on {wins_base} | wind beats no wind on {wins_k0}")
    print(f"Mean IoU on test fires: wind {test[best].mean():.3f}, no wind {test.k0.mean():.3f}, "
          f"round baseline {test.baseline.mean():.3f}")
    print("\nBy shape class (test fires, mean IoU):")
    print(test.groupby("shape_class")[[best, "k0", "baseline"]].mean().round(3).to_string())
    if int(df.edge_hits.sum()):
        print(f"\nNote: {int(df.edge_hits.sum())} runs touched the edge of the simulation area; "
              "scores for those fires may be cut short.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("perimeters")
    ap.add_argument("--runs", type=int, default=10)
    a = ap.parse_args()
    if not SELECTED.exists():
        sys.exit("Run scripts/count_candidate_detections.py first.")
    sel = pd.read_csv(SELECTED)
    sel = sel[sel.selected].reset_index(drop=True)
    sel["split"] = assign_split(sel)
    perims = load_perimeters(Path(a.perimeters))
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for i, f in sel.iterrows():
        cache = RESULT_DIR / f"{f.key}_runs{a.runs}.json"
        if cache.exists():
            rows.append(json.loads(cache.read_text()))
            print(f"[{i + 1}/{len(sel)}] {f.key}: cached")
            continue
        geom = perims.loc[f.key].geometry
        try:
            on = count_on_fire(detections_for(f.key, geom, f.alarm_date), geom)
            ign, n_early = estimate_ignition(on, geom)
            centre = gpd.GeoSeries([geom.centroid], crs=CRS_M).to_crs(CRS_LL).iloc[0]
            first = on["time_utc"].min()
            d0 = (first - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            d1 = (first + pd.Timedelta(days=3)).strftime("%Y-%m-%d")
            wind = wind_for(fetch_weather(f.key, centre.y, centre.x, d0, d1), first)
        except (RuntimeError, FirmsError, ValueError) as e:
            print(f"[{i + 1}/{len(sel)}] {f.key}: stopped ({e}). Run again to resume.")
            break
        t = time.time()
        res = evaluate_fire(geom, ign, wind["toward"], a.runs)
        row = {"key": f.key, "fire_name": f.fire_name, "year": int(f.year), "shape_class": f.shape_class,
               "split": f.split, "area_km2": f.area_km2, "elongation": f.elongation,
               "ignition_from_first_n_detections": n_early,
               "ignition_to_centroid_m": round(math.hypot(ign[0] - geom.centroid.x, ign[1] - geom.centroid.y)),
               "wind_toward_deg": round(wind["toward"]), "wind_speed_ms": round(wind["speed"], 1),
               "wind_steadiness": round(wind["steady"], 2), "wind_hours": wind["hours"], "wind_mode": wind["mode"],
               **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in res.items()}}
        cache.write_text(json.dumps(row))
        rows.append(row)
        print(f"[{i + 1}/{len(sel)}] {f.key} ({f.split}): wind toward {row['wind_toward_deg']} deg "
              f"({compass(wind['toward'])}, {wind['mode']} hours), start {row['ignition_to_centroid_m']} m from centre, "
              f"round baseline {res['baseline']:.2f}, k=2 {res['k2']:.2f}  [{time.time() - t:.0f} s]")

    df = pd.DataFrame(rows)
    if len(df) < len(sel):
        print(f"\nOnly {len(df)} of {len(sel)} fires done. Run the same command again to finish.")
        return
    df.to_csv(OUT, index=False)
    summarise(df)
    print(f"\nSaved {OUT}")


if __name__ == "__main__":
    main()
