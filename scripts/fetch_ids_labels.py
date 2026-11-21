"""
fetch_ids_labels.py -- downloads USFS aerial survey damage polygons
that touch the Shaver Lake box, 2021-2024.

Run from the repo root:   python scripts/fetch_ids_labels.py
Output: data/raw/ids_shaver_2021_2024.geojson  + a summary printed on screen
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

URL = ("https://apps.fs.usda.gov/arcx/rest/services/EDW/"
       "EDW_InsectandDiseaseSurvey_01/MapServer/1/query")
BBOX = "-119.50,37.00,-119.25,37.20"   # west,south,east,north
YEARS = (2021, 2024)
PAGE = 500
OUT_FILE = Path("data/raw/ids_shaver_2021_2024.geojson")


def fetch_all() -> list:
    features, offset = [], 0
    while True:
        params = {
            "where": f"SURVEY_YEAR >= {YEARS[0]} AND SURVEY_YEAR <= {YEARS[1]}",
            "geometry": BBOX,
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "outSR": 4326,
            "returnGeometry": "true",
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": PAGE,
        }
        resp = requests.get(URL, params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise SystemExit(f"Server error: {data['error']}")
        batch = data.get("features", [])
        if not batch:
            break
        features.extend(batch)
        offset += len(batch)
        print(f"  downloaded {len(features)} polygons so far...")
    return features


def main() -> None:
    
    print("Requesting USFS damage polygons...")
    features = fetch_all()
    if not features:
        raise SystemExit("No polygons returned. Tell Claude.")

    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    gdf.columns = [c.lower() for c in gdf.columns]

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(OUT_FILE, driver="GeoJSON")
    print(f"\nSaved {len(gdf)} polygons to {OUT_FILE}")

    pd.set_option("display.width", 200)
    print("\n=== Polygons and acres per survey year ===")
    print(gdf.groupby("survey_year")["acres"].agg(polygons="size", acres="sum").round(0))

    print("\n=== Cause (dca_common_name), polygons per year ===")
    print(pd.crosstab(gdf["dca_common_name"], gdf["survey_year"]))

    print("\n=== Damage type ===")
    print(gdf["damage_type"].value_counts())

    print("\n=== Damage level (percent_affected) ===")
    print(gdf["percent_affected"].value_counts())


if __name__ == "__main__":
    main()