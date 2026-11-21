"""
extract_training_features.py -- pulls M1 satellite features for the sampled cells from Earth Engine.

  python -m scripts.extract_training_features --test        # 1 chunk, 1 year (timing and sanity)
  python -m scripts.extract_training_features --parity      # Shaver cells vs the existing summer table
  python -m scripts.extract_training_features --workers 3   # everything, 2020-2024 (resumable)
Output: data/training/features/part_*.csv  ->  data/training/cells_features.csv
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import ee
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from modules.forest_health import features_gee, live_gee

CELLS = Path("data/training/cells_sample.csv")
OUT_DIR = Path("data/training/features")
MERGED = Path("data/training/cells_features.csv")
SUMMERS = Path("data/processed/m1_features_summers.csv")
YEARS = [2020, 2021, 2022, 2023, 2024]
CHUNK = 1500                 # lower to 800 if Earth Engine reports a memory limit
CELL = 500
STATIC = ["forest_frac", "burn_frac", "elev", "slope", "asp_sin", "asp_cos"]
YEARLY = ["NDVI", "NDMI", "NBR", "NDVI_sq", "NDMI_sq", "obs_count", "def_wy", "pdsi_jjas"]


def arg(name, default):
    return type(default)(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def lonlat_rings(cells: pd.DataFrame):
    sq = gpd.GeoSeries(
        [box(x - CELL / 2, y - CELL / 2, x + CELL / 2, y + CELL / 2)
         for x, y in zip(cells["x"], cells["y"])], crs="EPSG:32611").to_crs("EPSG:4326")
    return [list(g.exterior.coords) for g in sq]


def run_task(tag, cell_rows, year, static, forest, prefix=""):
    out = OUT_DIR / f"{prefix}part_{tag}_y{year}.csv"
    if out.exists():
        return out
    fc = ee.FeatureCollection([
        ee.Feature(ee.Geometry.Polygon([ring], None, False), {"cell_id": cid})
        for ring, cid in zip(lonlat_rings(cell_rows), cell_rows["cell_id"])])
    reduced = features_gee.cell_features(fc, year)
    for attempt in range(3):
        try:
            rows = [f["properties"] for f in reduced.getInfo()["features"]]
            break
        except Exception as exc:
            print(f"  retry {tag} y{year}: {repr(exc)[:150]}", flush=True)
            time.sleep(10 * (attempt + 1))
    else:
        raise RuntimeError(f"gave up on {tag} year {year}")
    df = pd.DataFrame(rows)
    df["year"] = year
    df.to_csv(out, index=False)
    return out


def parity(cells, static, forest):
    """Do the new features reproduce the table the live pipeline already uses?"""
    sh = cells[cells["in_shaver"]].reset_index(drop=True)
    parts = []
    for year in (2022, 2024):
        for ci, i in enumerate(range(0, len(sh), CHUNK)):
            parts.append(pd.read_csv(run_task(f"s{ci:02d}", sh.iloc[i:i + CHUNK], year,
                                              static, forest, prefix="parity_")))
    new = pd.concat(parts).merge(sh[["cell_id", "patch_id"]], on="cell_id")
    old = pd.read_csv(SUMMERS)[["patch_id", "year", "NDVI", "NDMI", "NBR"]]
    m = new.merge(old, on=["patch_id", "year"], suffixes=("_new", "_old"))
    print(f"\nPARITY (Shaver patches, 2022 and 2024), rows compared: {len(m)}")
    for b in ("NDVI", "NDMI", "NBR"):
        d = (m[b + "_new"] - m[b + "_old"]).abs()
        print(f"  {b}: mean abs diff {d.mean():.5f} | max {d.max():.5f} | both missing: "
              f"{int((m[b + '_new'].isna() & m[b + '_old'].isna()).sum())}")


def merge(cells):
    feats = pd.concat([pd.read_csv(p) for p in sorted(OUT_DIR.glob("part_*.csv"))],
                      ignore_index=True)
    feats["NDVI_sd"] = np.sqrt((feats["NDVI_sq"] - feats["NDVI"] ** 2).clip(lower=0))
    feats["NDMI_sd"] = np.sqrt((feats["NDMI_sq"] - feats["NDMI"] ** 2).clip(lower=0))
    feats = feats.drop(columns=["NDVI_sq", "NDMI_sq"])
    keep = (["cell_id", "ix", "iy", "block", "in_shaver", "patch_id", "lon", "lat"]
            + [c for c in cells.columns if c.startswith(("cover_", "near_"))])
    out = feats.merge(cells[keep], on="cell_id")
    out.to_csv(MERGED, index=False)
    print(f"\nWrote {MERGED}: {len(out)} rows, {out['cell_id'].nunique()} cells")
    print("Missing values per column:\n", out.isna().sum()[lambda s: s > 0].to_string())
    print("Share with fewer than 3 clear observations:", round(float((out['obs_count'] < 3).mean()), 3))
    print("Share burned (burn_frac > 0.05):", round(float((out['burn_frac'] > 0.05).mean()), 3))


def main() -> None:
    live_gee.init()
    cells = pd.read_csv(CELLS).sort_values(["block", "cell_id"]).reset_index(drop=True)
    static, forest = features_gee.static_stack()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if "--parity" in sys.argv:
        parity(cells, static, forest)
        return

    chunks = [cells.iloc[i:i + CHUNK] for i in range(0, len(cells), CHUNK)]
    jobs = [(f"c{ci:03d}", ch, y) for ci, ch in enumerate(chunks) for y in YEARS]
    if "--test" in sys.argv:
        jobs = [("c000", chunks[0], 2023)]

    t0 = time.time()

    def go(job):
        tag, ch, year = job
        path = run_task(tag, ch, year, static, forest)
        print(f"done {tag} y{year} ({time.time() - t0:.0f}s)", flush=True)
        return path

    with ThreadPoolExecutor(max_workers=arg("--workers", 1)) as ex:
        results = list(ex.map(go, jobs))

    if "--test" in sys.argv:
        print(pd.read_csv(results[0]).describe().T.round(3).to_string())
        return
    merge(cells)


if __name__ == "__main__":
    main()