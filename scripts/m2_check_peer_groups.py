
import json
from pathlib import Path
from collections import Counter

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data" / "processed" / "vegetation"

with open(
    FOLDER / "vegetation.geojson",
    encoding="utf-8"
) as f:
    geojson = json.load(f)

properties = [
    feature["properties"]
    for feature in geojson["features"]
]

df = pd.DataFrame(properties)

eligible = df[
    (df["anomaly_eligible"] == True)
    & df["vegetation_class"].notna()
].copy()

print("=== ELIGIBLE VEGETATION PATCHES ===")
print("Total patches:", len(df))
print("Eligible with vegetation class:", len(eligible))

print("\n=== VEGETATION PEER GROUPS ===")
counts = eligible["vegetation_class"].value_counts()

print(counts.to_string())

print("\nGroups with at least 30 patches:",
      (counts >= 30).sum())

print("Groups with fewer than 30 patches:",
      (counts < 30).sum())

print("\n=== HISTORICAL COMPLETENESS ===")

historical = pd.read_csv(
    ROOT / "data/processed/m1_features_summers.csv"
)

history = historical[
    historical["patch_id"].isin(eligible["patch_id"])
]

print(
    history.groupby("year")[["NDVI", "NDMI"]]
    .count()
)

print("\n=== ANOMALY RANGES ===")

print(
    eligible[["ndvi_anomaly", "ndmi_anomaly"]]
    .describe()
    .round(4)
)
