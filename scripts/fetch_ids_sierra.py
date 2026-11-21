"""
fetch_ids_sierra.py -- downloads USFS damage polygons for the Sierra Nevada, 2021-2024.

    python scripts/fetch_ids_sierra.py
Output: data/training/ids_sierra_2021_2024.gpkg   (not committed)
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

URL = ("https://apps.fs.usda.gov/arcx/rest/services/EDW/"
       "EDW_InsectandDiseaseSurvey_01/MapServer/1/query")
BBOX = "-121.7,35.3,-117.8,40.5"          # west,south,east,north
YEARS = (2021, 2024)
PAGE = 250
FIELDS = ("OBJECTID,DAMAGE_AREA_ID,SURVEY_YEAR,DCA_COMMON_NAME,DCA_CODE,DAMAGE_TYPE,"
          "DAMAGE_TYPE_CODE,HOST,HOST_GROUP,PERCENT_AFFECTED,PERCENT_AFFECTED_CODE,"
          "PERCENT_MID,ACRES")
OUT = Path("data/training/ids_sierra_2021_2024.gpkg")


def main() -> None:
    features, offset = [], 0
    while True:
        params = {
            "where": f"SURVEY_YEAR >= {YEARS[0]} AND SURVEY_YEAR <= {YEARS[1]}",
            "geometry": BBOX, "geometryType": "esriGeometryEnvelope", "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": FIELDS, "outSR": 4326, "returnGeometry": "true",
            "orderByFields": "OBJECTID", "f": "geojson",
            "resultOffset": offset, "resultRecordCount": PAGE,
        }
        resp = requests.get(URL, params=params, timeout=180)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise SystemExit(f"Server error: {data['error']}")
        batch = data.get("features", [])
        if not batch:
            break
        features.extend(batch)
        offset += len(batch)
        print(f"  {len(features)} polygons...", flush=True)

    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    gdf.columns = [c.lower() for c in gdf.columns]
    gdf["geometry"] = gdf.geometry.make_valid()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(OUT, driver="GPKG")
    print(f"\nSaved {len(gdf)} polygons to {OUT}")

    pd.set_option("display.width", 200)
    print("\nPolygons per year:\n", gdf["survey_year"].value_counts().sort_index())
    print("\nDamage level (percent_affected):\n", gdf["percent_affected"].value_counts())
    print("\nPolygon size (acres):\n", gdf["acres"].describe().round(1))


if __name__ == "__main__":
    main()