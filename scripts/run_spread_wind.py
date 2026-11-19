"""
run_spread_wind.py -- Version 1a: does adding the real Goose wind beat a round fire?

Run from the repo root:
    python scripts/run_spread_wind.py                 # average of all hours
    python scripts/run_spread_wind.py --max-rh 25     # only the dry hours (humidity below 25 %)
Needs:  data/processed/goose_2016_perimeter.geojson   (fetch_goose_firms.py)
        data/samples/goose_weather_2016.csv           (fetch_goose_weather.py)
Install: pip install geopandas shapely numpy pandas matplotlib

What it does
  1. Averages the hourly wind from 31 July 00:00 to 1 August 23:00 UTC into one direction.
  2. Starts the fire at the western tip (CAL FIRE point snapped inside) and at the centroid, and
     tries wind strengths k = 0 ... 4 (k = 0 is Version 0, no wind). Prints the mean IoU.
  3. Keeps the wind strength fixed and turns the wind direction all the way round, to see whether
     the direction from the weather data is also the best-scoring one.
Honest reading: the wind DIRECTION comes from data, so it is a real test. The wind STRENGTH k is
tuned on Goose itself, so a good score shows the idea can reproduce this fire, not that it
generalises. Everything here is on one fire.
"""
import argparse
import math
import sys
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

CAL_FIRE_POINT = (37.01591, -119.50507)       # lat, lon (fire.ca.gov)
K_VALUES = [0, 0.5, 1, 2, 3, 4]
DIRECTION_SCAN_K = 2


def to_utm(lat, lon):
    p = gpd.GeoSeries([Point(lon, lat)], crs=CRS_LL).to_crs(CRS_M).iloc[0]
    return p.x, p.y


def compass(deg):
    names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return names[int((deg % 360) / 22.5 + 0.5) % 16]


def average_wind(df):
    """Vector-average (toward_deg, mean speed m/s, steadiness) of wind given as speed + FROM direction."""
    u = -df.wind_ms * np.sin(np.radians(df.wind_from_deg))
    v = -df.wind_ms * np.cos(np.radians(df.wind_from_deg))
    mu, mv, mean_speed = u.mean(), v.mean(), df.wind_ms.mean()
    return math.degrees(math.atan2(mu, mv)) % 360, mean_speed, math.hypot(mu, mv) / mean_speed


def mean_iou(domain, xy, target, real, runs, **wind):
    scores, clipped = [], 0
    for seed in range(runs):
        sim = simulate(domain, xy, target, seed=seed, **wind)
        scores.append(iou(sim, real))
        clipped += touches_edge(sim)
    return float(np.mean(scores)), clipped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--perimeter", default="data/processed/goose_2016_perimeter.geojson")
    ap.add_argument("--weather", default="data/samples/goose_weather_2016.csv")
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--max-rh", type=float, default=None,
                    help="only average hours with relative humidity below this (%%), e.g. 25 for the dry, "
                         "fire-friendly hours")
    ap.add_argument("--png", default="data/processed/spread_v1a_goose.png")
    a = ap.parse_args()

    geom = gpd.read_file(a.perimeter).to_crs(CRS_M).geometry.union_all()
    centroid = (geom.centroid.x, geom.centroid.y)
    starts = {
        "western tip (CAL FIRE point, snapped inside)": snap_into_perimeter(geom, to_utm(*CAL_FIRE_POINT)),
        "perimeter centroid (reference)": centroid,
    }

    wx = pd.read_csv(a.weather, parse_dates=["time_utc"])
    window = wx[(wx.time_utc >= "2016-07-31 00:00") & (wx.time_utc <= "2016-08-01 23:00")].dropna(
        subset=["wind_ms", "wind_from_deg"])
    if a.max_rh is not None:
        window = window[window.rh_pct < a.max_rh]
        if window.empty:
            sys.exit(f"No hours with humidity below {a.max_rh}%")
    toward, speed, steady = average_wind(window)
    which = f"hours with humidity < {a.max_rh:g}%" if a.max_rh is not None else "all hours"
    print(f"Wind used (31 Jul 00:00 - 1 Aug 23:00 UTC, {which}, {len(window)} h): blowing toward "
          f"{toward:.0f} deg ({compass(toward)}), mean {speed:.1f} m/s, steadiness {steady:.2f}")

    region = shapely.union_all([geom] + [Point(xy) for xy in starts.values()])
    radius = math.sqrt(geom.area / math.pi)
    # wind stretches the fire, so leave room for a fire up to ~2.5 times the round radius downwind
    domain = make_domain(region, centroid, margin=2.5 * radius + 500)
    real = rasterize(geom, domain)
    target = int(real.sum())
    print(f"Real Goose fire: {geom.area / 1e6:.2f} km2 -> {target} cells of {CELL_M} m, {a.runs} runs per cell below")

    print("\n=== Mean IoU by wind strength k (k = 0 is Version 0, no wind) ===")
    rows, warn = [], 0
    for k in K_VALUES:
        row = {"k": k}
        for name, xy in starts.items():
            score, clipped = mean_iou(domain, xy, target, real, a.runs, wind_toward_deg=toward, wind_k=k)
            row[name.split(" (")[0]] = round(score, 3)
            warn += clipped
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))
    for name, xy in starts.items():
        print(f"round baseline, {name.split(' (')[0]}: {iou(circle_baseline(domain, xy, target), real):.3f}")
    if warn:
        print(f"WARNING: {warn} runs touched the domain edge, so some scores may be cut short")

    tip_name = list(starts)[0]
    tip_key = tip_name.split(" (")[0]
    best_k = max(rows, key=lambda r: r[tip_key])["k"]

    print(f"\n=== Wind direction scan (start: {tip_key}, k = {DIRECTION_SCAN_K}) ===")
    scan = []
    for ang in range(0, 360, 30):
        score, _ = mean_iou(domain, starts[tip_name], target, real, a.runs,
                            wind_toward_deg=ang, wind_k=DIRECTION_SCAN_K)
        scan.append({"wind toward (deg)": ang, "compass": compass(ang), "mean IoU": round(score, 3)})
    scan_df = pd.DataFrame(scan)
    print(scan_df.to_string(index=False))
    best = scan_df.loc[scan_df["mean IoU"].idxmax()]
    print(f"Best-scoring direction: {int(best['wind toward (deg)'])} deg ({best['compass']}); "
          f"the weather data says {toward:.0f} deg ({compass(toward)}).")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        sim = simulate(domain, starts[tip_name], target, seed=0, wind_toward_deg=toward, wind_k=best_k)
        fig, ax = plt.subplots(figsize=(9, 6))
        ext = (domain.x0, domain.x0 + domain.n_cols * CELL_M, domain.y0, domain.y0 + domain.n_rows * CELL_M)
        ax.imshow(np.ma.masked_where(~sim, sim), origin="lower", extent=ext, cmap="autumn", alpha=0.7)
        gpd.GeoSeries([geom], crs=CRS_M).boundary.plot(ax=ax, color="black", linewidth=1.5)
        x, y = starts[tip_name]
        ax.plot(x, y, marker="*", markersize=14, color="blue")
        ax.annotate("", xy=(x + 1500 * math.sin(math.radians(toward)), y + 1500 * math.cos(math.radians(toward))),
                    xytext=(x, y), arrowprops=dict(arrowstyle="->", color="blue", lw=2))
        ax.set_title(f"Version 1a (orange, k={best_k}, wind toward {toward:.0f} deg) vs real Goose (black)")
        ax.set_aspect("equal")
        Path(a.png).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(a.png, dpi=150, bbox_inches="tight")
        print(f"\nPicture saved: {a.png}")
    except ImportError:
        print("matplotlib not installed: skipped the picture")


if __name__ == "__main__":
    main()
