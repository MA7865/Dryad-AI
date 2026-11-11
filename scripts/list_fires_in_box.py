"""
list_fires_in_box.py -- lists every historical fire that touches the Shaver Lake box.

Run from the repo root:
    python scripts/list_fires_in_box.py "data/raw/California_Historic_Fire_Perimeters_-4891938132824355098"
(Use the exact file name you saved; quotes are fine if it has odd characters.)

Install once:  pip install geopandas pyogrio shapely pandas pyproj
Output: a table printed on screen + data/processed/fires_in_box.csv
"""
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
from shapely.geometry import box
from shapely.validation import make_valid

WEST, SOUTH, EAST, NORTH = -119.50, 37.00, -119.25, 37.20   # same as docs/STUDY_AREA.md
CRS_LL = "EPSG:4326"
CRS_M = "EPSG:32611"                                         # UTM 11N, metres
OUT_FILE = Path("data/processed/fires_in_box.csv")


def find_col(columns, *wanted):
    """Return the real column name matching any wanted name, ignoring case/underscores."""
    norm = {c.lower().replace("_", ""): c for c in columns}
    for w in wanted:
        hit = norm.get(w.lower().replace("_", ""))
        if hit:
            return hit
    return None


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit('Usage: python scripts/list_fires_in_box.py "<path to perimeter file>"')
    path = Path(sys.argv[1])
    if not path.exists():
        sys.exit(f"File not found: {path}")

    source = f"zip://{path}" if zipfile.is_zipfile(path) else str(path)

    # What is inside the file? (works for GeoJSON, GeoPackage, zipped shapefile)
    info = pyogrio.read_info(source)
    print(f"File CRS: {info.get('crs')}   Features: {info.get('features')}")
    print(f"Fields: {list(info.get('fields', []))}")

    # Read only the features near our box (box is converted to the file's CRS first).
    file_crs = info.get("crs") or CRS_LL
    box_in_file_crs = (
        gpd.GeoSeries([box(WEST, SOUTH, EAST, NORTH)], crs=CRS_LL).to_crs(file_crs).total_bounds
    )
    fires = gpd.read_file(source, bbox=tuple(box_in_file_crs))
    if fires.crs is None:
        fires = fires.set_crs(file_crs)
    print(f"Fires whose bounding rectangle touches the box: {len(fires)}")
    if fires.empty:
        sys.exit("Nothing found. Tell Claude the printed CRS/fields above.")

    fires["geometry"] = fires.geometry.apply(make_valid)
    fires_m = fires.to_crs(CRS_M)
    study_m = gpd.GeoSeries([box(WEST, SOUTH, EAST, NORTH)], crs=CRS_LL).to_crs(CRS_M).iloc[0]

    # Keep only fires that really overlap the box (not just rectangles that touch).
    fires_m = fires_m[fires_m.intersects(study_m)].copy()

    name_c = find_col(fires.columns, "FIRE_NAME", "FIRENAME", "NAME", "INCIDENT")
    year_c = find_col(fires.columns, "YEAR_", "YEAR", "FIRE_YEAR")
    alarm_c = find_col(fires.columns, "ALARM_DATE", "ALARMDATE", "START_DATE")
    cont_c = find_col(fires.columns, "CONT_DATE", "CONTDATE", "CONTAINMENT_DATE")
    acres_c = find_col(fires.columns, "GIS_ACRES", "ACRES")

    minx, miny, maxx, maxy = fires_m.total_bounds  # noqa: F841 (kept for debugging)
    rows = []
    for _, r in fires_m.iterrows():
        fx0, fy0, fx1, fy1 = r.geometry.bounds
        rows.append({
            "name": r[name_c] if name_c else None,
            "year": r[year_c] if year_c else None,
            "alarm_date": r[alarm_c] if alarm_c else None,
            "cont_date": r[cont_c] if cont_c else None,
            "acres_in_file": r[acres_c] if acres_c else None,
            "fire_area_km2": round(r.geometry.area / 1e6, 1),
            "inside_box_km2": round(r.geometry.intersection(study_m).area / 1e6, 1),
            "fire_width_km": round((fx1 - fx0) / 1000, 1),
            "fire_height_km": round((fy1 - fy0) / 1000, 1),
        })
    table = pd.DataFrame(rows)
    table["share_inside_box"] = (table["inside_box_km2"] / table["fire_area_km2"]).round(2)
    table = table.sort_values("year", ascending=False)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_FILE, index=False)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print(f"\n=== {len(table)} fires overlapping the Shaver Lake box (newest first) ===")
    print(table.to_string(index=False))
    print(f"\nSaved {OUT_FILE}")
    print("Reminder: FIRMS satellite data (NOAA-20) only goes back to April 2018.")


if __name__ == "__main__":
    main()
