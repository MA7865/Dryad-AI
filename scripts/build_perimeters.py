"""
build_perimeters.py -- turns the big CAL FIRE file into a small file the backend can read.

Run once from the repo root:
    python scripts/build_perimeters.py "data/raw/California_Historic_Fire_Perimeters_-4891938132824355098"

Reads only the fires that really overlap the Shaver Lake box, tidies the fields, simplifies the
outlines a little (10 m) so the file stays small, and writes
    data/processed/fire_perimeters_shaver.geojson     (EPSG:4326, committed to the repo)

The 249.5 MB raw file stays in data/raw/ (not committed). Re-run this only if the raw file changes.
Install once:  pip install geopandas pyogrio shapely pandas pyproj
"""
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
from shapely.geometry import box
from shapely.validation import make_valid

WEST, SOUTH, EAST, NORTH = -119.50, 37.00, -119.25, 37.20   # docs/STUDY_AREA.md
CRS_LL, CRS_M = "EPSG:4326", "EPSG:32611"
SIMPLIFY_M = 10.0
ACRES_TO_HA = 0.40468564224
OUT = Path("data/processed/fire_perimeters_shaver.geojson")


def find_col(columns, *wanted):
    """Real column name matching any wanted name, ignoring case and underscores (None if absent)."""
    norm = {c.lower().replace("_", ""): c for c in columns}
    for w in wanted:
        hit = norm.get(w.lower().replace("_", ""))
        if hit:
            return hit
    return None


def to_iso_utc(value):
    """CAL FIRE date text -> '2016-07-30T00:00:00Z', or None if missing or unreadable."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    ts = pd.to_datetime(str(value), errors="coerce", utc=True)
    return None if pd.isna(ts) else ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def clean_text(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def build(raw: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Raw CAL FIRE rows (any CRS) -> tidy rows in EPSG:4326 that overlap the study box."""
    study_m = gpd.GeoSeries([box(WEST, SOUTH, EAST, NORTH)], crs=CRS_LL).to_crs(CRS_M).iloc[0]
    fires = raw.copy()
    fires["geometry"] = fires.geometry.apply(make_valid)
    fires_m = fires.to_crs(CRS_M)
    keep = fires_m.intersects(study_m)
    fires, fires_m = fires[keep], fires_m[keep]

    c = lambda *n: find_col(fires.columns, *n)           # noqa: E731
    name_c, year_c = c("FIRE_NAME", "FIRENAME", "NAME", "INCIDENT"), c("YEAR_", "YEAR", "FIRE_YEAR")
    alarm_c, cont_c = c("ALARM_DATE", "ALARMDATE", "START_DATE"), c("CONT_DATE", "CONTDATE", "CONTAINMENT_DATE")
    acres_c, cause_c, agency_c = c("GIS_ACRES", "ACRES"), c("CAUSE"), c("AGENCY")
    col = lambda name: fires[name] if name else pd.Series([None] * len(fires), index=fires.index)  # noqa: E731

    out = gpd.GeoDataFrame({
        "fire_name": col(name_c).map(clean_text),
        "year": pd.to_numeric(col(year_c), errors="coerce").astype("Int64"),
        "alarm_date": col(alarm_c).map(to_iso_utc),
        "containment_date": col(cont_c).map(to_iso_utc),
        "area_ha": (pd.to_numeric(col(acres_c), errors="coerce") * ACRES_TO_HA).round(1),
        "cause": col(cause_c).map(clean_text),
        "agency": col(agency_c).map(clean_text),
    }, geometry=fires_m.geometry.simplify(SIMPLIFY_M).to_crs(CRS_LL), crs=CRS_LL)
    # CAL FIRE rows often have no year; fall back to the alarm date's year.
    missing = out["year"].isna() & out["alarm_date"].notna()
    out.loc[missing, "year"] = out.loc[missing, "alarm_date"].str[:4].astype(int)
    return out.sort_values(["year", "fire_name"], na_position="first").reset_index(drop=True)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit('Usage: python scripts/build_perimeters.py "<path to CAL FIRE perimeter file>"')
    path = Path(sys.argv[1])
    if not path.exists():
        sys.exit(f"File not found: {path}")
    source = f"zip://{path}" if zipfile.is_zipfile(path) else str(path)
    info = pyogrio.read_info(source)
    file_crs = info.get("crs") or CRS_LL
    bounds = gpd.GeoSeries([box(WEST, SOUTH, EAST, NORTH)], crs=CRS_LL).to_crs(file_crs).total_bounds
    raw = gpd.read_file(source, bbox=tuple(bounds))
    if raw.crs is None:
        raw = raw.set_crs(file_crs)
    print(f"Fires whose bounding box touches the study box: {len(raw)}")

    out = build(raw)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_file(OUT, driver="GeoJSON")
    print(f"Fires really overlapping the box: {len(out)}")
    print(f"  with a year: {int(out['year'].notna().sum())}, with an alarm date: {int(out['alarm_date'].notna().sum())}, "
          f"with an area: {int(out['area_ha'].notna().sum())}, with an agency: {int(out['agency'].notna().sum())}")
    print(f"Saved {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print(out[["fire_name", "year", "alarm_date", "area_ha"]].tail(8).to_string(index=False))


if __name__ == "__main__":
    main()
