"""
run_start_sensitivity.py -- how much does the Goose score depend on where the fire starts?

Run from the repo root:
    python scripts/run_start_sensitivity.py --max-rh 25
Needs the same two files as run_spread_wind.py (goose perimeter + goose weather).

What it does
  1. Takes the snapped-inside start point (the western tip) as the centre.
  2. Moves the start on a 5 x 5 grid of offsets (default step 300 m, so up to 600 m each way).
  3. For each start, runs the wind simulation (wind from the weather data, k = 2) and prints
     the mean IoU, plus whether that start lies inside the real perimeter.
  4. Reports the run-to-run noise (spread across seeds at the centre start), so you can tell a
     real change from chance.
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

from modules.fire_monitoring.spread_v0 import (
    CELL_M, CRS_M, iou, make_domain, rasterize, simulate, snap_into_perimeter, touches_edge,
)
from run_spread_wind import CAL_FIRE_POINT, average_wind, compass, to_utm

K = 2.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--perimeter", default="data/processed/goose_2016_perimeter.geojson")
    ap.add_argument("--weather", default="data/samples/goose_weather_2016.csv")
    ap.add_argument("--runs", type=int, default=10, help="simulations per start point")
    ap.add_argument("--step", type=float, default=300.0, help="offset spacing in metres")
    ap.add_argument("--max-rh", type=float, default=25.0)
    ap.add_argument("--png", default="data/processed/start_sensitivity_goose.png")
    a = ap.parse_args()

    geom = gpd.read_file(a.perimeter).to_crs(CRS_M).geometry.union_all()
    tip = snap_into_perimeter(geom, to_utm(*CAL_FIRE_POINT))

    wx = pd.read_csv(a.weather, parse_dates=["time_utc"])
    win = wx[(wx.time_utc >= "2016-07-31 00:00") & (wx.time_utc <= "2016-08-01 23:00")].dropna(
        subset=["wind_ms", "wind_from_deg"])
    win = win[win.rh_pct < a.max_rh]
    if win.empty:
        sys.exit(f"No hours with humidity below {a.max_rh}%")
    toward, speed, _ = average_wind(win)
    print(f"Wind: toward {toward:.0f} deg ({compass(toward)}), k = {K}, {a.runs} runs per start point")

    offsets = [-2, -1, 0, 1, 2]
    starts = {(i, j): (tip[0] + i * a.step, tip[1] + j * a.step) for i in offsets for j in offsets}
    region = shapely.union_all([geom] + [Point(xy) for xy in starts.values()])
    radius = math.sqrt(geom.area / math.pi)
    domain = make_domain(region, (geom.centroid.x, geom.centroid.y), margin=2.5 * radius + 500)
    real = rasterize(geom, domain)
    target = int(real.sum())

    scores = {}
    edge_hits = 0
    for key, xy in starts.items():
        vals = []
        for seed in range(a.runs):
            sim = simulate(domain, xy, target, seed=seed, wind_toward_deg=toward, wind_k=K)
            vals.append(iou(sim, real))
            edge_hits += touches_edge(sim)
        scores[key] = float(np.mean(vals))

    # table: rows = north offset (top = north), columns = east offset
    print(f"\nMean IoU by start point. Centre = snapped western tip. Step = {a.step:.0f} m. "
          f"Rows: north (top) to south; columns: west to east. '*' = start outside the real perimeter.")
    header = "        " + "".join(f"{i * a.step:+7.0f}" for i in offsets)
    print(header + "   (east offset, m)")
    for j in reversed(offsets):
        cells = []
        for i in offsets:
            mark = "" if geom.contains(Point(starts[(i, j)])) else "*"
            cells.append(f"{scores[(i, j)]:6.3f}{mark or ' '}")
        print(f"{j * a.step:+6.0f}  " + "".join(cells))

    base = scores[(0, 0)]
    noise = []
    for chunk in range(3):                       # 3 independent batches of runs at the centre
        vals = [iou(simulate(domain, starts[(0, 0)], target, seed=1000 + chunk * a.runs + s,
                             wind_toward_deg=toward, wind_k=K), real) for s in range(a.runs)]
        noise.append(float(np.mean(vals)))
    inside = [k for k in starts if geom.contains(Point(starts[k]))]
    print(f"\nCentre start: {base:.3f}. Batch-to-batch noise at the centre: "
          f"{min(noise):.3f} to {max(noise):.3f} (3 batches of {a.runs} runs).")
    print(f"Starts inside the perimeter: {len(inside)} of {len(starts)}.")
    for r, label in [(1, "within 300 m"), (2, "within 600 m")]:
        near = [scores[k] for k in starts if max(abs(k[0]), abs(k[1])) <= r and k in inside]
        if near:
            print(f"  {label} (inside only): IoU {min(near):.3f} to {max(near):.3f}, mean {np.mean(near):.3f}")
    best = max(starts, key=lambda k: scores[k])
    print(f"Best start: offset {best[0] * a.step:+.0f} m east, {best[1] * a.step:+.0f} m north -> {scores[best]:.3f}")
    if edge_hits:
        print(f"WARNING: {edge_hits} runs touched the domain edge.")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        grid = np.array([[scores[(i, j)] for i in offsets] for j in reversed(offsets)])
        fig, ax = plt.subplots(figsize=(5.5, 4.5))
        im = ax.imshow(grid, cmap="viridis", vmin=0, extent=[-2.5, 2.5, -2.5, 2.5])
        for r_i, j in enumerate(reversed(offsets)):
            for c_i, i in enumerate(offsets):
                ax.text(i, j, f"{grid[r_i, c_i]:.2f}", ha="center", va="center", color="white", fontsize=8)
        ax.set_xticks(offsets, [f"{o * a.step:+.0f}" for o in offsets])
        ax.set_yticks(offsets, [f"{o * a.step:+.0f}" for o in offsets])
        ax.set_xlabel("start moved east (m)")
        ax.set_ylabel("start moved north (m)")
        ax.set_title("Goose: IoU vs start point (wind, k = 2)")
        fig.colorbar(im, label="mean IoU")
        fig.tight_layout()
        Path(a.png).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(a.png, dpi=150)
        print(f"Saved {a.png}")
    except ImportError:
        print("matplotlib not installed, skipping the picture")


if __name__ == "__main__":
    main()
