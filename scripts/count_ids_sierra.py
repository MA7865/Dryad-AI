"""count_ids_sierra.py -- how many USFS damage polygons exist in the Sierra Nevada, per year and cause."""
import json

import pandas as pd
import requests

URL = ("https://apps.fs.usda.gov/arcx/rest/services/EDW/"
       "EDW_InsectandDiseaseSurvey_01/MapServer/1/query")
BBOX = "-121.7,35.3,-117.8,40.5"      # west,south,east,north (generous Sierra box)

params = {
    "where": "SURVEY_YEAR >= 2019",
    "geometry": BBOX, "geometryType": "esriGeometryEnvelope", "inSR": 4326,
    "spatialRel": "esriSpatialRelIntersects",
    "groupByFieldsForStatistics": "SURVEY_YEAR,DCA_COMMON_NAME,DAMAGE_TYPE",
    "outStatistics": json.dumps([
        {"statisticType": "count", "onStatisticField": "OBJECTID", "outStatisticFieldName": "polygons"},
        {"statisticType": "sum", "onStatisticField": "ACRES", "outStatisticFieldName": "acres"},
    ]),
    "f": "json",
}
r = requests.get(URL, params=params, timeout=180)
r.raise_for_status()
data = r.json()
if "error" in data:
    raise SystemExit(data["error"])

df = pd.DataFrame([f["attributes"] for f in data["features"]])
df.columns = [c.lower() for c in df.columns]
pd.set_option("display.width", 200)

print("=== Polygons and acres per survey year ===")
print(df.groupby("survey_year")[["polygons", "acres"]].sum().round(0))
print("\n=== Top 15 causes (polygons per year) ===")
tbl = df.pivot_table(index="dca_common_name", columns="survey_year", values="polygons",
                     aggfunc="sum", fill_value=0)
print(tbl.assign(total=tbl.sum(axis=1)).sort_values("total", ascending=False).head(15))
print("\n=== Damage type ===")
print(df.groupby("damage_type")["polygons"].sum().sort_values(ascending=False))