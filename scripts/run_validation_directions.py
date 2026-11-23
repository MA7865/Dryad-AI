"""
run_validation_directions.py -- is the problem the wind DATA, or the model?

Run from the repo root, after run_validation.py (it reuses the downloads that script saved):
    python scripts/run_validation_directions.py "data/raw/California_Historic_Fire_Perimeters_-4891938132824355098.geojson"
    (add --runs 5 for a quick try; --k 1 is the wind strength chosen on the tune fires)

For each selected fire it turns the wind direction all the way round (every 30 degrees) at fixed k and
finds the direction that scores best. Then it compares that best direction with
  (a) the direction the weather data gave (is the wind DATA wrong for this fire?), and
  (b) the fire's long axis (does the fire simply run along its own length, e.g. up a canyon?).
If the best direction usually sits near the long axis but far from the weather-data direction, something
the model lacks (slope, terrain, fuel) is steering the fire, which is what Version 2 (slope) is for.
Writes data/processed/validation_directions.csv.
"""
import argparse
import math
import sys
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
from fetch_goose_weather import compass  # noqa: E402
from modules.fire_monitoring.spread_v0 import (  # noqa: E402
    CRS_LL, CRS_M, iou, make_domain, rasterize, simulate, touches_edge)

OUT = Path("data/processed/validation_directions.csv")
SCAN = list(range(0, 360, 30))


def long_axis_bearing(geom_m) -> float:
    """Compass bearing (0 to 180) of the fire's long axis."""
    xs, ys = geom_m.minimum_rotated_rectangle.exterior.coords.xy
    sides = [(xs[i + 1] - xs[i], ys[i + 1] - ys[i]) for i in range(2)]
    dx, dy = max(sides, key=lambda s: math.hypot(*s))
    return math.degrees(math.atan2(dx, dy)) % 180


def angle_diff(a: float, b: float, period: float = 360.0) -> float:
    """Smallest difference between two bearings (period 360 for directions, 180 for axes)."""
    d = abs(a - b) % period
    return min(d, period - d)


def scan_fire(geom_m, ign_xy, data_toward: float, k: float, runs: int) -> dict:
    radius = math.sqrt(geom_m.area / math.pi)
    region = shapely.union_all([geom_m, Point(ign_xy)])
    domain = make_domain(region, (geom_m.centroid.x, geom_m.centroid.y), margin=2.5 * radius + 500)
    real = rasterize(geom_m, domain)
    target = int(real.sum())

    def score(toward):
        vals, edge = [], 0
        for seed in range(runs):
            sim = simulate(domain, ign_xy, target, seed=seed, wind_toward_deg=toward, wind_k=k)
            vals.append(iou(sim, real))
            edge += touches_edge(sim)
        return float(np.mean(vals)), edge

    by_dir = {d: score(d) for d in SCAN}
    best = max(by_dir, key=lambda d: by_dir[d][0])
    data_score, data_edge = score(data_toward)
    axis = long_axis_bearing(geom_m)
    return {"best_dir": best, "best_iou": by_dir[best][0], "data_iou": data_score,
            "data_vs_best_deg": angle_diff(data_toward, best),
            "best_vs_axis_deg": angle_diff(best, axis, 180.0),
            "data_vs_axis_deg": angle_diff(data_toward, axis, 180.0),
            "axis_bearing": axis, "edge_hits": data_edge + sum(e for _, e in by_dir.values())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("perimeters")
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--k", type=float, default=1.0)
    a = ap.parse_args()
    sel = pd.read_csv(rv.SELECTED)
    sel = sel[sel.selected].reset_index(drop=True)
    sel["split"] = rv.assign_split(sel)
    perims = load_perimeters(Path(a.perimeters))

    rows = []
    for i, f in sel.iterrows():
        geom = perims.loc[f.key].geometry
        on = count_on_fire(detections_for(f.key, geom, f.alarm_date), geom)
        ign, _ = rv.estimate_ignition(on, geom)
        centre = gpd.GeoSeries([geom.centroid], crs=CRS_M).to_crs(CRS_LL).iloc[0]
        first = on["time_utc"].min()
        d0 = (first - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        d1 = (first + pd.Timedelta(days=3)).strftime("%Y-%m-%d")
        wind = rv.wind_for(rv.fetch_weather(f.key, centre.y, centre.x, d0, d1), first)
        r = scan_fire(geom, ign, wind["toward"], a.k, a.runs)
        row = {"fire_name": f.fire_name, "year": int(f.year), "split": f.split, "shape_class": f.shape_class,
               "elongation": f.elongation, "data_dir": round(wind["toward"]), "data_compass": compass(wind["toward"]),
               "wind_steadiness": round(wind["steady"], 2), **{k: (round(v, 3) if isinstance(v, float) else v)
                                                              for k, v in r.items()}}
        rows.append(row)
        print(f"[{i + 1}/{len(sel)}] {f.key}: data {row['data_dir']} deg, best {r['best_dir']} deg, "
              f"axis {r['axis_bearing']:.0f}, IoU data {r['data_iou']:.2f} vs best {r['best_iou']:.2f}")

    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    show = df[["fire_name", "year", "split", "elongation", "data_dir", "best_dir", "axis_bearing",
               "data_iou", "best_iou", "data_vs_best_deg", "best_vs_axis_deg"]]
    print(f"\n=== Direction scan at k = {a.k:g} ===")
    print(show.round(2).to_string(index=False))
    close = int((df.data_vs_best_deg <= 30).sum())
    print(f"\nWeather-data direction within 30 deg of the best-scoring direction: {close} of {len(df)} fires")
    print(f"Mean IoU: weather-data direction {df.data_iou.mean():.3f}, best direction {df.best_iou.mean():.3f}")
    long_fires = df[df.elongation >= 1.5]
    print(f"Elongated fires (>= 1.5): best direction within 30 deg of the long axis: "
          f"{int((long_fires.best_vs_axis_deg <= 30).sum())} of {len(long_fires)}; "
          f"weather-data direction within 30 deg of the long axis: {int((long_fires.data_vs_axis_deg <= 30).sum())} of {len(long_fires)}")
    if int(df.edge_hits.sum()):
        print(f"Note: {int(df.edge_hits.sum())} runs touched the edge of the simulation area.")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
