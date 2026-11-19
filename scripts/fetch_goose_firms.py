"""
fetch_goose_firms.py -- builds the M4 test case: the 2016 Goose fire.

What it does:
  1. Loads the Goose (2016) perimeter from the CAL FIRE file and saves a small copy
     to data/processed/goose_2016_perimeter.geojson
  2. Downloads FIRMS detections (VIIRS_SNPP_SP archive) for the fire dates, 5 days
     per request, and saves them to data/samples/goose_2016_firms_snpp.csv
  3. Counts how many detections fall inside the perimeter, day by day
  4. Writes an interactive map you open in your browser: data/processed/goose_map.html

Run from the repo root:
    python scripts/fetch_goose_firms.py "data/raw/California_Historic_Fire_Perimeters_-4891938132824355098"

Install once:  pip install requests pandas python-dotenv geopandas pyogrio shapely pyproj folium
Needs FIRMS_MAP_KEY in your .env file.
"""
import os
import sys
import time
import zipfile
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
import pyogrio
import requests
from dotenv import load_dotenv
from shapely.geometry import box
from shapely.validation import make_valid

# ---- Settings -------------------------------------------------------------
WEST, SOUTH, EAST, NORTH = -119.50, 37.00, -119.25, 37.20   # docs/STUDY_AREA.md
BBOX = f"{WEST},{SOUTH},{EAST},{NORTH}"
FIRE_NAME, FIRE_YEAR = "GOOSE", 2016
# Goose: alarm 2016-07-30, contained 2016-08-09 (from the CAL FIRE file).
# We add one day on each side to catch early/late detections.
START, END = date(2016, 7, 29), date(2016, 8, 10)
SOURCE = "VIIRS_SNPP_SP"        # SNPP archive: covers 2012-01-20 to 2026-07-31
BASE = "https://firms.modaps.eosdis.nasa.gov/api"
CRS_LL, CRS_M = "EPSG:4326", "EPSG:32611"
MATCH_BUFFER_M = 375            # one VIIRS pixel: a detection this close counts as "on" the fire
OUT_PERIM = Path("data/processed/goose_2016_perimeter.geojson")
OUT_CSV = Path("data/samples/goose_2016_firms_snpp.csv")
OUT_MAP = Path("data/processed/goose_map.html")
PALETTE = ["#440154", "#482878", "#3e4989", "#31688e", "#26828e", "#1f9e89", "#35b779",
           "#6ece58", "#b5de2b", "#fde725", "#fdae61", "#f46d43", "#d73027", "#a50026"]
# ---------------------------------------------------------------------------


def load_goose(path: Path) -> gpd.GeoDataFrame:
    source = f"zip://{path}" if zipfile.is_zipfile(path) else str(path)
    file_crs = pyogrio.read_info(source).get("crs") or CRS_LL
    bounds = gpd.GeoSeries([box(WEST, SOUTH, EAST, NORTH)], crs=CRS_LL).to_crs(file_crs).total_bounds
    fires = gpd.read_file(source, bbox=tuple(bounds))
    if fires.crs is None:
        fires = fires.set_crs(file_crs)
    year = pd.to_numeric(fires["YEAR_"], errors="coerce")
    name = fires["FIRE_NAME"].astype(str).str.upper().str.strip()
    goose = fires[(name == FIRE_NAME) & (year == FIRE_YEAR)].copy()
    if goose.empty:
        sys.exit(f"Could not find {FIRE_NAME} {FIRE_YEAR} in the perimeter file.")
    goose["geometry"] = goose.geometry.apply(make_valid)
    return goose.to_crs(CRS_LL)


def get_csv(url: str) -> pd.DataFrame:
    """One FIRMS request. Never prints the URL (it contains your key)."""
    try:
        resp = requests.get(url, timeout=90)
    except requests.RequestException as exc:
        sys.exit(f"Network problem: {type(exc).__name__}")
    if resp.status_code != 200:
        sys.exit(f"FIRMS answered with HTTP {resp.status_code}: {resp.text[:200]}")
    text = resp.text.strip()
    if not text:
        return pd.DataFrame()
    if "latitude" not in text.splitlines()[0]:
        sys.exit(f"Unexpected reply from FIRMS: {text[:300]}")
    return pd.read_csv(StringIO(text))


def fetch_detections(key: str) -> pd.DataFrame:
    parts, day = [], START
    while day <= END:
        n_days = min(5, (END - day).days + 1)       # a request allows 1-5 days
        url = f"{BASE}/area/csv/{key}/{SOURCE}/{BBOX}/{n_days}/{day.isoformat()}"
        df = get_csv(url)
        print(f"  {day} + {n_days} day(s): {len(df)} detections")
        parts.append(df)
        day += timedelta(days=n_days)
        time.sleep(1)                                # be polite to the server
    parts = [p for p in parts if not p.empty]
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True).drop_duplicates()


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit('Usage: python scripts/fetch_goose_firms.py "<path to perimeter file>"')
    path = Path(sys.argv[1])
    if not path.exists():
        sys.exit(f"File not found: {path}")
    load_dotenv()
    key = os.getenv("FIRMS_MAP_KEY")
    if not key:
        sys.exit("FIRMS_MAP_KEY not found. Check your .env file is in the repo root.")

    # 1. Perimeter
    goose = load_goose(path)
    OUT_PERIM.parent.mkdir(parents=True, exist_ok=True)
    goose.to_file(OUT_PERIM, driver="GeoJSON")
    area_km2 = goose.to_crs(CRS_M).area.sum() / 1e6
    print(f"Goose perimeter: {len(goose)} polygon(s), {area_km2:.1f} km2 -> {OUT_PERIM}")

    # 2. Detections
    print(f"Requesting {SOURCE} from {START} to {END}:")
    det = fetch_detections(key)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    det.to_csv(OUT_CSV, index=False)
    print(f"Total detections: {len(det)} -> {OUT_CSV}")
    if det.empty:
        sys.exit("No detections returned. Tell Claude what the output above says.")

    # 3. Inside / outside the perimeter (with a one-pixel tolerance)
    pts = gpd.GeoDataFrame(
        det, geometry=gpd.points_from_xy(det["longitude"], det["latitude"]), crs=CRS_LL
    )
    perim_m = goose.to_crs(CRS_M).geometry.union_all().buffer(MATCH_BUFFER_M)
    pts["on_fire"] = pts.to_crs(CRS_M).geometry.within(perim_m)
    summary = (
        pts.groupby("acq_date")
        .agg(detections=("on_fire", "size"), on_fire=("on_fire", "sum"))
        .reset_index()
    )
    summary["outside"] = summary["detections"] - summary["on_fire"]
    print("\n=== Detections per day (acq_date is UTC) ===")
    print(summary.to_string(index=False))
    print(f"\nWithin {MATCH_BUFFER_M} m of the perimeter: {int(pts['on_fire'].sum())} of {len(pts)}")

    # 4. Map
    centre = goose.geometry.union_all().centroid
    fmap = folium.Map(location=[centre.y, centre.x], zoom_start=12, tiles="CartoDB positron")
    folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Tiles &copy; Esri", name="Satellite (Esri)",
    ).add_to(fmap)
    folium.GeoJson(
        goose, name="Goose perimeter (CAL FIRE)",
        style_function=lambda _: {"color": "#d73027", "weight": 3, "fillOpacity": 0.08},
    ).add_to(fmap)
    dates = sorted(pts["acq_date"].unique())
    colour = {d: PALETTE[round(i * (len(PALETTE) - 1) / max(len(dates) - 1, 1))] for i, d in enumerate(dates)}
    layer = folium.FeatureGroup(name="FIRMS detections (colour = date)")
    for _, r in pts.iterrows():
        folium.CircleMarker(
            [r["latitude"], r["longitude"]], radius=5, color=colour[r["acq_date"]],
            fill=True, fill_opacity=0.8, weight=1,
            popup=f"{r['acq_date']} {int(r['acq_time']):04d} UTC | conf {r['confidence']} | FRP {r.get('frp', '')}",
        ).add_to(layer)
    layer.add_to(fmap)
    folium.LayerControl().add_to(fmap)
    legend = "".join(
        f"<span style='color:{colour[d]}'>&#9679;</span> {d}<br>" for d in dates
    )
    fmap.get_root().html.add_child(folium.Element(
        "<div style='position:fixed;bottom:20px;left:20px;z-index:9999;background:white;"
        f"padding:8px;border:1px solid #999;font-size:12px'><b>Detection date (UTC)</b><br>{legend}</div>"
    ))
    fmap.save(OUT_MAP)
    print(f"\nMap saved: {OUT_MAP}  (open it in your browser)")


if __name__ == "__main__":
    main()
