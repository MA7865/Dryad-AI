"""
run_spread_v0.py -- scores the Version 0 spread prototype against the real Goose perimeter.

Run from the repo root:
    python scripts/run_spread_v0.py
Needs:  data/processed/goose_2016_perimeter.geojson   (made by fetch_goose_firms.py)
Optional: data/samples/goose_2016_firms_snpp.csv      (used for a direction hint)
Install: pip install geopandas shapely numpy pandas matplotlib

Compares, by IoU on a 90 m grid:
  * the simulated fire (30 random seeds), started at each candidate ignition point
  * a round "fire" of the same area at the same point (the baseline the simulation must beat)
"""
import argparse
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # so `modules` is found from scripts/

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Point

from modules.fire_monitoring.spread_v0 import (
    CELL_M, CRS_LL, CRS_M, circle_baseline, iou, make_domain, rasterize, simulate,
    snap_into_perimeter, touches_edge,
)

# Published points (lat, lon)
CAL_FIRE_POINT = (37.01591, -119.50507)    # fire.ca.gov Goose Fire page ("off Gooseberry Ln & Morgan Canyon")
FIRE_AI_POINT = (37.01355, -119.46717)     # fire.ai Goose 2016 page


def to_utm(lat, lon):
    p = gpd.GeoSeries([Point(lon, lat)], crs=CRS_LL).to_crs(CRS_M).iloc[0]
    return p.x, p.y


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--perimeter", default="data/processed/goose_2016_perimeter.geojson")
    ap.add_argument("--detections", default="data/samples/goose_2016_firms_snpp.csv")
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--png", default="data/processed/spread_v0_goose.png")
    a = ap.parse_args()

    geom = gpd.read_file(a.perimeter).to_crs(CRS_M).geometry.union_all()
    centroid = (geom.centroid.x, geom.centroid.y)
    cal = to_utm(*CAL_FIRE_POINT)
    # A fire cannot start outside the land it burned, so if the published point is outside the
    # perimeter we also try the nearest point inside it.
    points = {
        "CAL FIRE point, snapped inside": snap_into_perimeter(geom, cal),
        "CAL FIRE point, as published": cal,
        "perimeter centroid (reference)": centroid,
    }
    fa = to_utm(*FIRE_AI_POINT)
    print(f"fire.ai point is {np.hypot(fa[0] - centroid[0], fa[1] - centroid[1]):.0f} m from the "
          f"perimeter centroid (if ~0, it is the centre of the outline, not an ignition point)")

    # one shared domain that holds the real fire and every candidate start point
    region = shapely.union_all([geom] + [Point(xy) for xy in points.values()])
    # margin >= radius of a round fire of the same area, so a blob started at any candidate fits
    radius = math.sqrt(geom.area / math.pi)
    domain = make_domain(region, centroid, margin=radius + 500)
    real = rasterize(geom, domain)
    target = int(real.sum())
    print(f"Real Goose fire: {geom.area / 1e6:.2f} km2 -> {target} cells of {CELL_M} m "
          f"(domain {domain.n_rows} x {domain.n_cols} cells)")

    print("\n=== Where does the fire start? ===")
    for name, xy in points.items():
        d_edge = Point(xy).distance(geom)
        d_cent = np.hypot(xy[0] - centroid[0], xy[1] - centroid[1])
        print(f"{name:34s} distance to perimeter: {d_edge:7.0f} m "
              f"({'inside' if geom.contains(Point(xy)) else 'outside'}),  to centroid: {d_cent:6.0f} m")

    if Path(a.detections).exists():
        det = pd.read_csv(a.detections)
        g = gpd.GeoDataFrame(det, geometry=gpd.points_from_xy(det.longitude, det.latitude), crs=CRS_LL).to_crs(CRS_M)
        g["x"], g["y"] = g.geometry.x, g.geometry.y
        by_day = g.groupby("acq_date")[["x", "y"]].mean()
        if len(by_day) >= 2:
            first, last = by_day.iloc[0], by_day.iloc[-1]
            print(f"\nDetection centre moved from {by_day.index[0]} to {by_day.index[-1]}: "
                  f"{last.x - first.x:+.0f} m east, {last.y - first.y:+.0f} m north")

    print(f"\n=== Version 0 vs round baseline (IoU, {a.runs} runs) ===")
    rows, best = [], None
    t0 = time.time()
    for name, xy in points.items():
        scores, clipped = [], 0
        for seed in range(a.runs):
            sim = simulate(domain, xy, target, seed=seed)
            scores.append(iou(sim, real))
            clipped += touches_edge(sim)
            if best is None and name == list(points)[0] and seed == 0:
                best = sim
        base = iou(circle_baseline(domain, xy, target), real)
        rows.append({"start point": name, "sim mean": round(np.mean(scores), 3),
                     "sim min": round(min(scores), 3), "sim max": round(max(scores), 3),
                     "round baseline": round(base, 3)})
        if clipped:
            print(f"WARNING: {clipped} of {a.runs} runs from '{name}' hit the domain edge (scores may be unreliable)")
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"\nRun time: {time.time() - t0:.1f} s for {a.runs * len(points)} simulations")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 6))
        ext = (domain.x0, domain.x0 + domain.n_cols * CELL_M, domain.y0, domain.y0 + domain.n_rows * CELL_M)
        ax.imshow(np.ma.masked_where(~best, best), origin="lower", extent=ext, cmap="autumn", alpha=0.7)
        gpd.GeoSeries([geom], crs=CRS_M).boundary.plot(ax=ax, color="black", linewidth=1.5)
        for name, xy in points.items():
            ax.plot(*xy, marker="*", markersize=12, label=name)
        ax.legend(loc="upper right", fontsize=8)
        ax.set_title("Version 0 (orange) vs real Goose perimeter (black outline)")
        ax.set_aspect("equal")
        Path(a.png).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(a.png, dpi=150, bbox_inches="tight")
        print(f"Picture saved: {a.png}")
    except ImportError:
        print("matplotlib not installed: skipped the picture (pip install matplotlib)")


if __name__ == "__main__":
    main()
