"""
count_candidate_detections.py -- how many satellite detections does each candidate fire have?

Run from the repo root (needs FIRMS_MAP_KEY in .env, like the Goose scripts):
    python scripts/count_candidate_detections.py "data/raw/California_Historic_Fire_Perimeters_-4891938132824355098.geojson"

For each fire in data/processed/validation_candidates.csv it downloads VIIRS detections (VIIRS_SNPP_SP,
which covers 2012 to mid-2026) for the first 7 days (day before the alarm date through alarm date + 6),
keeps confidence n and h (the shared rule), and counts those inside or within 375 m of the perimeter.
Downloads are saved in data/samples/validation/, so if your network drops just run it again: fires
already downloaded are not requested twice.

Writes data/processed/validation_detections.csv, and marks which fires are ELIGIBLE and SELECTED using
rules fixed here, before any model is scored:
  eligible  = at least MIN_DETECTIONS detections on the fire and on at least MIN_DAYS different days
  selected  = from the eligible fires, up to PER_CLASS per shape class (round < 1.5, medium, long >= 2.5),
              most detections first. Shape classes are used so the test set is not all round fires.
Install once:  pip install geopandas pyogrio shapely pandas pyproj requests python-dotenv
"""
import argparse
import sys
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import geopandas as gpd
import pandas as pd
import pyogrio
import shapely
from shapely.geometry import box
from shapely.validation import make_valid

from build_perimeters import find_col, to_iso_utc  # noqa: E402
from modules.fire_monitoring.active_fire import filter_confidence  # noqa: E402
from modules.fire_monitoring.firms_client import FirmsError, fetch_detections  # noqa: E402

SOURCE = "VIIRS_SNPP_SP"
CRS_LL, CRS_M = "EPSG:4326", "EPSG:32611"
CANDIDATES = Path("data/processed/validation_candidates.csv")
CACHE_DIR = Path("data/samples/validation")
OUT = Path("data/processed/validation_detections.csv")
WINDOW_DAYS = 7
MATCH_BUFFER_M = 375            # one VIIRS pixel
MIN_DETECTIONS, MIN_DAYS = 15, 2
PER_CLASS = 4
SIERRA_BBOX = (-121.5, 35.5, -117.8, 40.4)


def shape_class(elongation: float) -> str:
    return "round" if elongation < 1.5 else ("long" if elongation >= 2.5 else "medium")


def slug(name, year, alarm) -> str:
    return f"{str(name).strip().replace(' ', '_').replace('/', '-')}_{year}_{alarm[:10]}"


def load_perimeters(path: Path) -> gpd.GeoDataFrame:
    source = f"zip://{path}" if zipfile.is_zipfile(path) else str(path)
    file_crs = pyogrio.read_info(source).get("crs") or CRS_LL
    bounds = gpd.GeoSeries([box(*SIERRA_BBOX)], crs=CRS_LL).to_crs(file_crs).total_bounds
    raw = gpd.read_file(source, bbox=tuple(bounds))
    if raw.crs is None:
        raw = raw.set_crs(file_crs)
    name_c = find_col(raw.columns, "FIRE_NAME", "FIRENAME", "NAME")
    alarm_c = find_col(raw.columns, "ALARM_DATE", "ALARMDATE")
    year_c = find_col(raw.columns, "YEAR_", "YEAR")
    raw["geometry"] = raw.geometry.apply(make_valid)
    raw = raw.to_crs(CRS_M)
    raw["_key"] = [
        None if to_iso_utc(a) is None or pd.isna(pd.to_numeric(y, errors="coerce"))
        else slug(n, int(pd.to_numeric(y)), to_iso_utc(a))
        for n, y, a in zip(raw[name_c], raw[year_c], raw[alarm_c])]
    return raw.dropna(subset=["_key"]).drop_duplicates("_key").set_index("_key")


def detections_for(key: str, geom_m, alarm_iso: str) -> pd.DataFrame:
    """Cached download of the first WINDOW_DAYS days of detections around one fire."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{key}.csv"
    if cache.exists():
        return pd.read_csv(cache) if cache.stat().st_size > 1 else pd.DataFrame()
    alarm = date.fromisoformat(alarm_iso[:10])
    west, south, east, north = gpd.GeoSeries([geom_m.buffer(1000)], crs=CRS_M).to_crs(CRS_LL).total_bounds
    df = fetch_detections((west, south, east, north), alarm - timedelta(days=1),
                          alarm + timedelta(days=WINDOW_DAYS - 2), SOURCE)
    if df.empty:
        cache.write_text("")
    else:
        df.to_csv(cache, index=False)
    return df


def count_on_fire(df: pd.DataFrame, geom_m) -> pd.DataFrame:
    """Keep confidence n/h detections within MATCH_BUFFER_M of the perimeter; add UTC time and x, y (m)."""
    if df.empty:
        return df
    df = filter_confidence(df)
    if df.empty:
        return df
    pts = gpd.GeoSeries(gpd.points_from_xy(df["longitude"], df["latitude"]), crs=CRS_LL).to_crs(CRS_M)
    near = shapely.contains_xy(geom_m.buffer(MATCH_BUFFER_M), pts.x.values, pts.y.values)
    out = df[near].copy()
    out["x_m"], out["y_m"] = pts.x.values[near], pts.y.values[near]
    hhmm = out["acq_time"].astype(int).astype(str).str.zfill(4)
    out["time_utc"] = pd.to_datetime(out["acq_date"].astype(str) + " " + hhmm.str[:2] + ":" + hhmm.str[2:], utc=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("perimeters")
    ap.add_argument("--limit", type=int, default=None, help="only the first N candidates (for a quick test)")
    a = ap.parse_args()
    if not CANDIDATES.exists():
        sys.exit("Run scripts/list_validation_candidates.py first.")
    cand = pd.read_csv(CANDIDATES)
    if a.limit:
        cand = cand.head(a.limit)
    perims = load_perimeters(Path(a.perimeters))

    rows = []
    for i, c in cand.iterrows():
        key = slug(c.fire_name, c.year, c.alarm_date)
        if key not in perims.index:
            print(f"[{i + 1}/{len(cand)}] {key}: not found in the perimeter file, skipped")
            continue
        geom = perims.loc[key].geometry
        try:
            raw = detections_for(key, geom, c.alarm_date)
        except FirmsError as e:
            print(f"[{i + 1}/{len(cand)}] {key}: FIRMS problem ({e}). Run again to resume.")
            break
        on = count_on_fire(raw, geom)
        first = on["time_utc"].min() if len(on) else None
        rows.append({
            "key": key, "fire_name": c.fire_name, "year": c.year, "alarm_date": c.alarm_date,
            "area_km2": c.area_km2, "elongation": c.elongation, "shape_class": shape_class(c.elongation),
            "detections": len(on), "days_with_detections": int(on["acq_date"].nunique()) if len(on) else 0,
            "first_detection_utc": first.strftime("%Y-%m-%dT%H:%M:%SZ") if first is not None else None,
        })
        print(f"[{i + 1}/{len(cand)}] {key}: {len(on)} detections on {rows[-1]['days_with_detections']} days")

    res = pd.DataFrame(rows)
    if res.empty:
        sys.exit("Nothing to report.")
    res["eligible"] = (res.detections >= MIN_DETECTIONS) & (res.days_with_detections >= MIN_DAYS)
    res["selected"] = False
    for _, grp in res[res.eligible].groupby("shape_class"):
        top = grp.sort_values(["detections", "fire_name"], ascending=[False, True]).head(PER_CLASS)
        res.loc[top.index, "selected"] = True
    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False)

    print(f"\nFires checked: {len(res)} | eligible (>= {MIN_DETECTIONS} detections on >= {MIN_DAYS} days): "
          f"{int(res.eligible.sum())} | selected: {int(res.selected.sum())}")
    print(res[res.eligible].groupby("shape_class").size().to_string())
    print("\nSelected fires:")
    print(res[res.selected][["fire_name", "year", "area_km2", "elongation", "shape_class", "detections",
                            "days_with_detections"]].to_string(index=False))
    print(f"\nSaved {OUT}")


if __name__ == "__main__":
    main()
