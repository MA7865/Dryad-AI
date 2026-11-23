"""
list_validation_candidates.py -- which Sierra Nevada fires can we use to test the spread model?

Run from the repo root:
    python scripts/list_validation_candidates.py "data/raw/California_Historic_Fire_Perimeters_-4891938132824355098.geojson"

Selection rules (fixed BEFORE looking at any model score, so we cannot cherry-pick):
  * centroid inside a hand-drawn outline of the Sierra Nevada (SIERRA_POLYGON below; --no-polygon skips it)
  * year 2012 to 2025 (VIIRS satellite detections exist from 2012)
  * has an alarm date
  * area between --min-km2 (5) and --max-km2 (150)
Writes data/processed/validation_candidates.csv and prints the list.
Install once:  pip install geopandas pyogrio shapely pandas pyproj
"""
import argparse
import math
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
from shapely.geometry import Point, Polygon, box
from shapely.validation import make_valid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_perimeters import find_col, to_iso_utc  # noqa: E402

CRS_LL, CRS_M = "EPSG:4326", "EPSG:32611"
SIERRA_BBOX = (-121.5, 35.5, -117.8, 40.4)     # box used to read the file (generous)
# Rough outline of the Sierra Nevada (lon, lat), west edge north to south, then east edge south to north.
# Hand-drawn from town and valley positions, so treat the edges as +/- 10 km. It keeps out the Central
# Valley floor, the Coast Ranges and Tehachapi/Central Coast fires that sit inside the box above.
SIERRA_POLYGON = [(-121.3, 40.3), (-121.1, 39.5), (-121.0, 39.0), (-120.95, 38.5), (-120.5, 38.0),
                  (-120.0, 37.5), (-119.55, 37.0), (-119.2, 36.6), (-118.95, 36.2), (-118.8, 35.9),
                  (-118.55, 35.6), (-118.0, 35.6), (-117.9, 36.0), (-117.9, 36.5), (-118.3, 37.2),
                  (-118.7, 37.7), (-119.0, 38.2), (-119.4, 38.7), (-119.85, 39.3), (-119.9, 40.3)]
OUT = Path("data/processed/validation_candidates.csv")


def elongation(geom_m) -> float:
    """Length / width of the fire's minimum rotated rectangle (1 = round, 3 = a long thin fire)."""
    rect = geom_m.minimum_rotated_rectangle
    xs, ys = rect.exterior.coords.xy
    sides = sorted([math.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i]) for i in range(2)])
    return sides[1] / sides[0] if sides[0] else float("nan")


def in_sierra(lon: float, lat: float) -> bool:
    return Polygon(SIERRA_POLYGON).contains(Point(lon, lat))


def select(raw: gpd.GeoDataFrame, year_from=2012, year_to=2025, min_km2=5.0, max_km2=150.0,
           use_polygon=True) -> pd.DataFrame:
    fires = raw.copy()
    fires["geometry"] = fires.geometry.apply(make_valid)
    fires_m = fires.to_crs(CRS_M)
    c = lambda *n: find_col(fires.columns, *n)           # noqa: E731
    name_c, year_c = c("FIRE_NAME", "FIRENAME", "NAME"), c("YEAR_", "YEAR")
    alarm_c, cont_c = c("ALARM_DATE", "ALARMDATE"), c("CONT_DATE", "CONTDATE")
    rows = []
    for idx, r in fires_m.iterrows():
        alarm = to_iso_utc(fires.at[idx, alarm_c]) if alarm_c else None
        year = pd.to_numeric(fires.at[idx, year_c], errors="coerce") if year_c else float("nan")
        if alarm is None or pd.isna(year) or not (year_from <= year <= year_to):
            continue
        km2 = r.geometry.area / 1e6
        if not (min_km2 <= km2 <= max_km2):
            continue
        centre = gpd.GeoSeries([r.geometry.centroid], crs=CRS_M).to_crs(CRS_LL).iloc[0]
        if use_polygon and not in_sierra(centre.x, centre.y):
            continue
        rows.append({
            "fire_name": fires.at[idx, name_c] if name_c else None, "year": int(year),
            "alarm_date": alarm, "containment_date": to_iso_utc(fires.at[idx, cont_c]) if cont_c else None,
            "area_km2": round(km2, 1), "elongation": round(elongation(r.geometry), 2),
            "centroid_lon": round(centre.x, 4), "centroid_lat": round(centre.y, 4),
        })
    return pd.DataFrame(rows).sort_values(["year", "fire_name"]).reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--bbox", nargs=4, type=float, default=SIERRA_BBOX, metavar=("W", "S", "E", "N"),
                    help="box used to read the file")
    ap.add_argument("--no-polygon", action="store_true", help="skip the Sierra outline and keep everything in the box")
    ap.add_argument("--min-km2", type=float, default=5.0)
    ap.add_argument("--max-km2", type=float, default=150.0)
    a = ap.parse_args()
    path = Path(a.path)
    if not path.exists():
        sys.exit(f"File not found: {path}")
    source = f"zip://{path}" if zipfile.is_zipfile(path) else str(path)
    file_crs = pyogrio.read_info(source).get("crs") or CRS_LL
    bounds = gpd.GeoSeries([box(*a.bbox)], crs=CRS_LL).to_crs(file_crs).total_bounds
    raw = gpd.read_file(source, bbox=tuple(bounds))
    if raw.crs is None:
        raw = raw.set_crs(file_crs)
    print(f"Fires in the Sierra box: {len(raw)}")
    out = select(raw, min_km2=a.min_km2, max_km2=a.max_km2, use_polygon=not a.no_polygon)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"Candidates (Sierra outline, 2012-2025, alarm date known, {a.min_km2:g}-{a.max_km2:g} km2): {len(out)}")
    print(out.to_string(index=False))
    print(f"Elongation: {int((out.elongation < 1.5).sum())} round (<1.5), {int(((out.elongation >= 1.5) & (out.elongation < 2.5)).sum())} medium, {int((out.elongation >= 2.5).sum())} long (>=2.5)")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
