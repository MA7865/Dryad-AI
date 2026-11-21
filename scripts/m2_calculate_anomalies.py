
from pathlib import Path
import pandas as pd

from modules.vegetation.anomaly import (
    calculate_vegetation_anomalies
)

ROOT = Path(__file__).resolve().parents[1]

INPUT = ROOT / "data/processed/m1_features_summers.csv"

OUTPUT = (
    ROOT / "data/processed/vegetation"
    / "vegetation_anomalies.csv"
)

historical = pd.read_csv(INPUT)

anomalies = calculate_vegetation_anomalies(historical)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
anomalies.to_csv(OUTPUT, index=False)

print("Rows:", len(anomalies))
print("Unique patches:", anomalies["patch_id"].nunique())

print("\nAnomaly statistics:")
print(
    anomalies[["ndvi_anomaly", "ndmi_anomaly"]]
    .describe()
    .round(4)
)

print("\nSample:")
print(anomalies.head().to_string(index=False))

print("\nSaved:", OUTPUT)
