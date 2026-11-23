
"""
M2: Compare the production anomaly values with
the experimental 2026 backtest values.

Read-only diagnostic. Does not modify files.
"""

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data" / "processed" / "vegetation"

BACKTEST_FILE = FOLDER / "anomaly_backtest.csv"
LAYER_FILE = FOLDER / "vegetation.geojson"
THRESHOLD_FILE = FOLDER / "anomaly_threshold_test.csv"


def main():
    backtest = pd.read_csv(BACKTEST_FILE)

    backtest_2026 = backtest[
        backtest["target_year"] == 2026
    ].copy()

    with open(LAYER_FILE, encoding="utf-8") as f:
        geojson = json.load(f)

    production = pd.DataFrame([
        {
            "patch_id": feature["properties"]["patch_id"],
            "production_ndvi": feature["properties"].get(
                "ndvi_anomaly"
            ),
            "production_ndmi": feature["properties"].get(
                "ndmi_anomaly"
            ),
        }
        for feature in geojson["features"]
    ])

    if backtest_2026["patch_id"].duplicated().any():
        raise ValueError("Duplicate backtest patch IDs")

    if production["patch_id"].duplicated().any():
        raise ValueError("Duplicate production patch IDs")

    comparison = backtest_2026.merge(
        production,
        on="patch_id",
        how="left",
        validate="one_to_one"
    )

    print("=== ANOMALY CONSISTENCY CHECK ===")
    print("Compared patches:", len(comparison))

    for index in ["ndvi", "ndmi"]:
        experimental = comparison[f"{index}_anomaly"]

        current = pd.to_numeric(
            comparison[f"production_{index}"],
            errors="coerce"
        )

        difference = (experimental - current).abs()

        print(f"\n{index.upper()} comparison:")
        print(
            "Missing production values:",
            int(current.isna().sum())
        )
        print(
            "Mean absolute difference:",
            round(difference.mean(), 6)
        )
        print(
            "Maximum absolute difference:",
            round(difference.max(), 6)
        )
        print(
            "Different by > 0.001:",
            int((difference > 0.001).sum())
        )

    # Compare each patch's existing anomaly score
    # against the experimental thresholds.
    thresholds = pd.read_csv(THRESHOLD_FILE)

    required = {
        "patch_id",
        "ndvi_threshold",
        "ndmi_threshold",
        "anomaly_detected"
    }

    if not required.issubset(thresholds.columns):
        raise ValueError("Threshold output has missing columns")

    comparison = comparison.merge(
        thresholds[list(required)],
        on="patch_id",
        how="left",
        validate="one_to_one"
    )

    production_flag = (
        (
            comparison["production_ndvi"]
            < comparison["ndvi_threshold"]
        )
        |
        (
            comparison["production_ndmi"]
            < comparison["ndmi_threshold"]
        )
    )

    experimental_flag = (
        comparison["anomaly_detected"]
        .astype("boolean")
    )

    valid = (
        comparison["production_ndvi"].notna()
        & comparison["production_ndmi"].notna()
        & comparison["ndvi_threshold"].notna()
        & comparison["ndmi_threshold"].notna()
        & experimental_flag.notna()
    )

    disagreements = (
        valid
        & (
            production_flag
            != experimental_flag.fillna(False)
        )
    )

    print("\n=== FLAG AGREEMENT ===")
    print(
        "Comparable patches:",
        int(valid.sum())
    )
    print(
        "Flags using production anomalies:",
        int((production_flag & valid).sum())
    )
    print(
        "Flags using experimental anomalies:",
        int((experimental_flag.fillna(False) & valid).sum())
    )
    print(
        "Disagreeing patches:",
        int(disagreements.sum())
    )

    print("\nDiagnostic complete. No files changed.")


if __name__ == "__main__":
    main()
