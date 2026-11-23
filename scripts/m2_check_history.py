
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

historical = pd.read_csv(
    ROOT / "data/processed/m1_features_summers.csv"
)

current = pd.read_csv(
    ROOT / "data/processed/vegetation/vegetation_features.csv"
)

print("=== HISTORICAL DATA ===")
print("Rows:", len(historical))
print("Years:", sorted(historical["year"].unique()))
print("Unique patches:", historical["patch_id"].nunique())

print("\nMissing values by year:")
print(
    historical.groupby("year")[["NDVI", "NDMI"]]
    .apply(lambda x: x.isna().sum())
)

print("\n=== CURRENT DATA ===")
print("Rows:", len(current))
print("Unique patches:", current["patch_id"].nunique())

print("\n=== PATCH ID CHECK ===")
historical_ids = set(historical["patch_id"])
current_ids = set(current["patch_id"])

print("IDs match:", historical_ids == current_ids)

print("\n=== 2026 COMPARISON ===")

old_2026 = historical[
    historical["year"] == 2026
][["patch_id", "NDVI", "NDMI"]]

merged = current.merge(
    old_2026,
    on="patch_id",
    suffixes=("_current", "_m1"),
    validate="one_to_one"
)

print("Matched patches:", len(merged))

for index in ["NDVI", "NDMI"]:
    diff = (
        merged[f"{index}_current"]
        - merged[f"{index}_m1"]
    )

    print(f"\n{index} difference:")
    print("Mean:", round(diff.mean(), 4))
    print("Median:", round(diff.median(), 4))
    print("Mean absolute:", round(diff.abs().mean(), 4))
    print("90th percentile absolute:",
          round(diff.abs().quantile(0.9), 4))
