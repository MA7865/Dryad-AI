
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data" / "processed" / "vegetation"

INPUT = FOLDER / "anomaly_backtest.csv"
OUTPUT = FOLDER / "anomaly_threshold_test.csv"

df = pd.read_csv(INPUT)

required = {
    "patch_id", "vegetation_class", "target_year",
    "ndvi_anomaly", "ndmi_anomaly"
}

if not required.issubset(df.columns):
    raise ValueError("Missing required backtest columns")

if df.duplicated(["patch_id", "target_year"]).any():
    raise ValueError("Duplicate patch-year records")

# Threshold calibration uses 2024 and 2025 only.
calibration = df[df["target_year"].isin([2024, 2025])].copy()
evaluation = df[df["target_year"] == 2026].copy()

thresholds = (
    calibration.groupby("vegetation_class")
    .agg(
        ndvi_threshold=("ndvi_anomaly",
                        lambda s: s.quantile(0.05)),
        ndmi_threshold=("ndmi_anomaly",
                        lambda s: s.quantile(0.05)),
        calibration_count=("patch_id", "size")
    )
    .reset_index()
)

# Require at least 60 class-year observations.
thresholds = thresholds[
    thresholds["calibration_count"] >= 60
]

evaluation = evaluation.merge(
    thresholds,
    on="vegetation_class",
    how="left",
    validate="many_to_one"
)

evaluation["ndvi_flag"] = (
    evaluation["ndvi_anomaly"]
    < evaluation["ndvi_threshold"]
)

evaluation["ndmi_flag"] = (
    evaluation["ndmi_anomaly"]
    < evaluation["ndmi_threshold"]
)

# Nullable Boolean supports True, False and missing values.
evaluation["anomaly_detected"] = (
    evaluation["ndvi_flag"] | evaluation["ndmi_flag"]
).astype("boolean")

# A missing threshold must never produce a
# confident "no anomaly" classification.
missing_threshold = (
    evaluation["ndvi_threshold"].isna()
    | evaluation["ndmi_threshold"].isna()
)

evaluation["anomaly_status"] = "not_flagged"

evaluation.loc[
    evaluation["anomaly_detected"],
    "anomaly_status"
] = "negative_change_flagged"

evaluation.loc[
    missing_threshold,
    "anomaly_status"
] = "not_evaluated"

evaluation.loc[
    missing_threshold,
    "anomaly_detected"
] = pd.NA

evaluation["anomaly_method"] = (
    "historical_class_lower_5pct_v0"
)

print("=== THRESHOLDS BY VEGETATION CLASS ===")
print(
    thresholds[
        [
            "vegetation_class",
            "calibration_count",
            "ndvi_threshold",
            "ndmi_threshold"
        ]
    ].to_string(index=False)
)

print("\n=== 2026 EVALUATION ===")
print("Total evaluated patches:", len(evaluation))
print("Status counts:")
print(evaluation["anomaly_status"].value_counts())

print("\nFlagged by index:")
print("NDVI:", int(evaluation["ndvi_flag"].sum()))
print("NDMI:", int(evaluation["ndmi_flag"].sum()))
print(
    "Either:",
    int((evaluation["anomaly_detected"] == True).sum())
)

print("\nFlagged by vegetation class:")
print(
    evaluation.groupby("vegetation_class")[
        "anomaly_detected"
    ].apply(lambda s: int((s == True).sum()))
    .to_string()
)

evaluation.to_csv(OUTPUT, index=False)

print("\nSaved:", OUTPUT)
