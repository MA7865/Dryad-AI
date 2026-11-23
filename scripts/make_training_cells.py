"""
make_training_cells.py -- builds the Sierra-wide sample of 500 m cells used to train and test M1 models.

    python scripts/make_training_cells.py
Reads : data/training/ids_sierra_2021_2024.gpkg, data/grid.geojson
Writes: data/training/cells_sample.csv   (not committed)
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import box

CRS_M = "EPSG:32611"          # same projection as the shared grid
CELL = 500
NEAR_M = 3000                 # "surveyed" = a polygon of that year within this distance
N_SAMPLE = 30000
SEED = 0
YEARS = [2021, 2022, 2023, 2024]
BLOCK = 40                    # 40 cells = 20 km blocks for spatial cross-validation
IDS = Path("data/training/ids_sierra_2021_2024.gpkg")
GRID = Path("data/grid.geojson")
OUT = Path("data/training/cells_sample.csv")


def main() -> None:
    polys = gpd.read_file(IDS).to_crs(CRS_M)
    polys = polys[polys["damage_type"].fillna("").str.contains("Mortality")].copy()
    polys["geometry"] = polys.geometry.make_valid()
    print(f"Mortality polygons: {len(polys)}")

    # Universe: cell centres within NEAR_M of any mortality polygon (any year)
    minx, miny, maxx, maxy = polys.total_bounds
    ix0, ix1 = int(minx // CELL) - 8, int(maxx // CELL) + 8
    iy0, iy1 = int(miny // CELL) - 8, int(maxy // CELL) + 8
    ixs, iys = np.meshgrid(np.arange(ix0, ix1 + 1), np.arange(iy0, iy1 + 1))
    ixs, iys = ixs.ravel(), iys.ravel()
    cx, cy = (ixs + 0.5) * CELL, (iys + 0.5) * CELL
    near_all = shapely.union_all(list(polys.geometry.simplify(50))).buffer(NEAR_M)
    in_universe = shapely.contains_xy(near_all, cx, cy)
    print(f"Cells within {NEAR_M} m of a polygon: {int(in_universe.sum())}")

    cand = pd.DataFrame({"ix": ixs[in_universe], "iy": iys[in_universe]})
    sample = cand.sample(n=min(N_SAMPLE, len(cand)), random_state=SEED)

    # Always include the shared Shaver Lake patches (the held-out final test)
    grid = gpd.read_file(GRID).to_crs(CRS_M)
    c = grid.geometry.centroid
    shaver = pd.DataFrame({"ix": (c.x // CELL).astype(int).values,
                           "iy": (c.y // CELL).astype(int).values,
                           "patch_id": grid["patch_id"].values})
    cells = pd.concat([sample.assign(patch_id=None), shaver], ignore_index=True)
    cells = cells.drop_duplicates(subset=["ix", "iy"], keep="last").reset_index(drop=True)

    cells["cell_id"] = "S_x" + cells["ix"].astype(str) + "_y" + cells["iy"].astype(str)
    cells["x"] = (cells["ix"] + 0.5) * CELL
    cells["y"] = (cells["iy"] + 0.5) * CELL
    cells["block"] = (cells["ix"] // BLOCK).astype(str) + "_" + (cells["iy"] // BLOCK).astype(str)
    cells["in_shaver"] = cells["patch_id"].notna()

    squares = gpd.GeoDataFrame(
        cells[["cell_id"]],
        geometry=[box(x - CELL / 2, y - CELL / 2, x + CELL / 2, y + CELL / 2)
                  for x, y in zip(cells["x"], cells["y"])], crs=CRS_M)
    pts = gpd.GeoDataFrame(cells[["cell_id"]],
                           geometry=gpd.points_from_xy(cells["x"], cells["y"]), crs=CRS_M)
    ll = pts.to_crs("EPSG:4326")
    cells["lon"], cells["lat"] = ll.geometry.x.values, ll.geometry.y.values

    for y in YEARS:
        py = polys[polys["survey_year"] == y][["geometry"]]
        inter = gpd.overlay(squares, py, how="intersection", keep_geom_type=True)
        cover = (inter.geometry.area / CELL ** 2).groupby(inter["cell_id"]).sum().clip(upper=1.0)
        cells[f"cover_{y}"] = cells["cell_id"].map(cover).fillna(0.0).round(3)
        near = gpd.sjoin_nearest(pts, py, how="inner", max_distance=NEAR_M)
        cells[f"near_{y}"] = cells["cell_id"].isin(near["cell_id"])
        print(f"  year {y} done", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cells.to_csv(OUT, index=False)

    print(f"\nSaved {len(cells)} cells to {OUT}")
    print("Shaver cells:", int(cells["in_shaver"].sum()), "| spatial blocks:", cells["block"].nunique())
    for y in YEARS:
        e = cells[cells[f"near_{y}"]]
        pos = int((e[f"cover_{y}"] >= 0.10).sum())
        print(f"{y}: surveyed-area cells {len(e)}, positives (10%+ covered) {pos} ({pos / len(e):.1%})")


if __name__ == "__main__":
    main()