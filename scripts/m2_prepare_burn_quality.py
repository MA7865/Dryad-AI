
from pathlib import Path
import pandas as pd

from modules.vegetation.preprocessing import (
    prepare_burn_and_quality
)

ROOT = Path(__file__).resolve().parents[1]

historical = pd.read_csv(
    ROOT / "data/processed/m1_features_summers.csv"
)

anomalies = pd.read_csv(
    ROOT / "data/processed/vegetation/vegetation_anomalies.csv"
)

result = prepare_burn_and_quality(
    historical,
    anomalies,
    year=2026
)

output = (
    ROOT / "data/processed/vegetation"
    / "vegetation_burn_quality.csv"
)

output.parent.mkdir(parents=True, exist_ok=True)
result.to_csv(output, index=False)

print("Total patches:", len(result))
print("Unique patch IDs:", result["patch_id"].nunique())

print("\nBurn status:")
print(result["burn_status"].value_counts())

print("\nAnomaly status:")
print(result["anomaly_status"].value_counts())

print("\nData quality:")
print(result["data_quality"].value_counts())

print("\nMissing anomalies:")
print(result[["ndvi_anomaly", "ndmi_anomaly"]].isna().sum())

print("\nSaved:", output)
