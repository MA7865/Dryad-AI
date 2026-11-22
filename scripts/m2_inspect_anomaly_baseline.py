
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

df = pd.read_csv(
    ROOT / "data/processed/m1_features_summers.csv"
)

print("=== ALL PATCHES ===")

print(
    df.groupby("year")[["NDVI", "NDMI"]]
    .agg(["count", "mean", "median", "std"])
    .round(4)
)

# Use the same unburned/forest thresholds as M1.
reference = df[
    (df["burn_frac"] < 0.05) &
    (df["forest_frac"] >= 0.20) &
    df["NDVI"].notna() &
    df["NDMI"].notna()
].copy()

print("\n=== UNBURNED FOREST REFERENCE ===")

print(
    reference.groupby("year")[["NDVI", "NDMI"]]
    .agg(["count", "mean", "median", "std"])
    .round(4)
)

print("\n=== FOREST AND BURN DISTRIBUTION ===")

latest = df[df["year"] == 2026]

print("Mostly burned (burn_frac >= 0.50):",
      (latest["burn_frac"] >= 0.50).sum())

print("Low forest cover (forest_frac < 0.20):",
      (latest["forest_frac"] < 0.20).sum())

print("Unburned forest reference:",
      len(reference[reference["year"] == 2026]))

print("\n=== SAMPLE PATCH HISTORY ===")

sample_id = "P_r000_c023"

print(
    df[df["patch_id"] == sample_id][
        ["patch_id", "year", "NDVI", "NDMI",
         "forest_frac", "burn_frac"]
    ].to_string(index=False)
)
