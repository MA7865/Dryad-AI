
import os
import json
from pathlib import Path

import ee
import pandas as pd

from scripts.m2_check_satellite import (
    mask_clouds,
    add_indices,
)

ROOT = Path(__file__).resolve().parents[1]
GRID = ROOT / "data" / "grid.geojson"
OUTPUT = (
    ROOT / "data" / "processed"
    / "vegetation" / "vegetation_features.csv"
)

PROJECT = os.environ["EE_PROJECT"]
ee.Initialize(project=PROJECT)

# Load the original shared grid
with open(GRID, encoding="utf-8") as f:
    grid = json.load(f)

features = [
    ee.Feature(
        ee.Geometry(p["geometry"], None, False),
        {"patch_id": p["properties"]["patch_id"]}
    )
    for p in grid["features"]
]

grid_fc = ee.FeatureCollection(features)

# Summer 2026 imagery
collection = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(grid_fc.geometry().bounds())
    .filterDate("2026-06-01", "2026-09-01")
    .filter(
        ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 60)
    )
)

processed = (
    collection
    .map(mask_clouds)
    .map(add_indices)
)

composite = processed.select(
    ["NDVI", "NDMI"]
).median()

# Number of clear observations for each pixel
observations = (
    processed.select("NDVI")
    .count()
    .rename("obs_count")
)

stack = composite.addBands(observations)

print("Starting Earth Engine extraction...")

reduced = stack.reduceRegions(
    collection=grid_fc,
    reducer=ee.Reducer.mean(),
    scale=20,
    tileScale=4
)

# Return properties only, not polygon geometries
reduced = reduced.select(
    ["patch_id", "NDVI", "NDMI", "obs_count"],
    None,
    False
)

rows = [
    f["properties"]
    for f in reduced.getInfo()["features"]
]

df = pd.DataFrame(rows)

# Keep expected fields and patch order
columns = [
    "patch_id", "NDVI", "NDMI", "obs_count"
]

for column in columns:
    if column not in df.columns:
        df[column] = None

df = df[columns]
df["year"] = 2026
df["window_start"] = "2026-06-01"
df["window_end"] = "2026-09-01"

OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True
)

df.to_csv(OUTPUT, index=False)

print("Extraction complete!")
print("Rows:", len(df))
print("Columns:", df.columns.tolist())
print(df.head())
print("Saved to:", OUTPUT)
