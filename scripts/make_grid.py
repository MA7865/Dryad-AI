"""
make_grid.py -- builds the shared 500 m patch grid for the Shaver Lake study area.

Run ONCE, commit the output, and have every module load that same file:
    python make_grid.py
Output: data/grid.geojson  (polygons in EPSG:4326, one per 500 m cell)

Install:  pip install geopandas shapely pyproj
"""
import math
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

# ---- Agreed team settings (change only if the whole team agrees) ----------
WEST, SOUTH, EAST, NORTH = -119.50, 37.00, -119.25, 37.20  # study area, lon/lat
CELL_M = 500                    # cell size in metres
CRS_METRIC = "EPSG:32611"       # UTM zone 11N: coordinates in metres
CRS_OUT = "EPSG:4326"           # WGS84 lon/lat, used for all GeoJSON output
OUT_FILE = Path("data/grid.geojson")
# ---------------------------------------------------------------------------


def build_grid() -> gpd.GeoDataFrame:
    # 1. Study area as a polygon, moved into metres.
    study_ll = box(WEST, SOUTH, EAST, NORTH)  # box(minx, miny, maxx, maxy)
    study_m = gpd.GeoSeries([study_ll], crs=CRS_OUT).to_crs(CRS_METRIC).iloc[0]
    minx, miny, maxx, maxy = study_m.bounds

    # 2. Snap the origin to a multiple of 500 m so the grid is anchored to the
    #    UTM coordinate system. Anyone re-running this gets identical cells.
    x0 = math.floor(minx / CELL_M) * CELL_M
    y0 = math.floor(miny / CELL_M) * CELL_M
    n_cols = math.ceil((maxx - x0) / CELL_M)
    n_rows = math.ceil((maxy - y0) / CELL_M)

    # 3. Make every square; keep only those that touch the study area.
    #    row 0 = southern edge, col 0 = western edge.
    records = []
    for row in range(n_rows):
        for col in range(n_cols):
            cell = box(
                x0 + col * CELL_M,
                y0 + row * CELL_M,
                x0 + (col + 1) * CELL_M,
                y0 + (row + 1) * CELL_M,
            )
            if cell.intersects(study_m):
                records.append(
                    {"patch_id": f"P_r{row:03d}_c{col:03d}", "row": row, "col": col, "geometry": cell}
                )

    grid_m = gpd.GeoDataFrame(records, geometry="geometry", crs=CRS_METRIC)

    # 4. Add each cell's centre point (lon/lat), then convert to lon/lat.
    centres = grid_m.geometry.centroid.to_crs(CRS_OUT)
    grid = grid_m.to_crs(CRS_OUT)
    grid["center_lon"] = centres.x.round(6)
    grid["center_lat"] = centres.y.round(6)
    return grid


def check_grid(grid: gpd.GeoDataFrame) -> None:
    assert grid["patch_id"].is_unique, "patch_id values must be unique"
    assert grid.crs.to_string() == CRS_OUT, "grid must be in EPSG:4326"
    assert grid.geometry.is_valid.all(), "invalid geometry found"
    minx, miny, maxx, maxy = grid.total_bounds
    print(f"Cells:        {len(grid)}")
    print(f"Rows x cols:  {grid['row'].max() + 1} x {grid['col'].max() + 1}")
    print(f"Grid extent:  west {minx:.4f}, south {miny:.4f}, east {maxx:.4f}, north {maxy:.4f}")
    cell_km2 = grid.to_crs(CRS_METRIC).area.mean() / 1e6
    print(f"Avg cell area: {cell_km2:.3f} km2 (expected {(CELL_M / 1000) ** 2:.3f})")


if __name__ == "__main__":
    grid = build_grid()
    check_grid(grid)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    grid.to_file(OUT_FILE, driver="GeoJSON")
    print(f"Saved {OUT_FILE}")
