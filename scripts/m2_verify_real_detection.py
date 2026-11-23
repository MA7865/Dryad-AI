
"""
M2: Verify anomaly detection using real data.

Calibrates thresholds from the corrected
2024-2025 historical backtest, then applies
them to the production vegetation layer.

Does not modify vegetation.geojson.
"""

import json
from pathlib import Path

import pandas as pd

from modules.vegetation.detection import (
    detect_negative_changes,
)


ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data" / "processed" / "vegetation"

BACKTEST = FOLDER / "anomaly_backtest.csv"
LAYER = FOLDER / "vegetation.geojson"
THRESHOLDS = FOLDER / "anomaly_thresholds.csv"
EXPERIMENT = FOLDER / "anomaly_threshold_test.csv"


def main():
    # Load the corrected historical backtest.
    history = pd.read_csv(BACKTEST)

    if history.duplicated(
        ["patch_id", "target_year"]
    ).any():
        raise ValueError(
            "Duplicate historical patch-year records"
        )

    calibration = history[
        history["target_year"].isin([2024, 2025])
    ].copy()

    # Both historical calibration years must exist.
    if set(calibration["target_year"]) != {
        2024, 2025
    }:
        raise ValueError(
            "Missing calibration years"
        )

    # Compute vegetation-specific thresholds.
    thresholds = (
        calibration.groupby("vegetation_class")
        .agg(
            ndvi_threshold=(
                "ndvi_anomaly",
                lambda s: s.quantile(0.05)
            ),
            ndmi_threshold=(
                "ndmi_anomaly",
                lambda s: s.quantile(0.05)
            ),
            calibration_count=(
                "patch_id", "size"
            )
        )
        .reset_index()
    )

    # Require at least 60 class-year observations.
    thresholds = thresholds[
        thresholds["calibration_count"] >= 60
    ].copy()

    if thresholds.empty:
        raise ValueError(
            "No vegetation classes have enough data"
        )

    thresholds.to_csv(
        THRESHOLDS,
        index=False
    )

    print("=== CALIBRATED THRESHOLDS ===")
    print("Vegetation groups:", len(thresholds))
    print("Saved:", THRESHOLDS)

    # Load the current production GeoJSON.
    with open(LAYER, encoding="utf-8") as f:
        geojson = json.load(f)

    patches = pd.DataFrame([
        feature["properties"]
        for feature in geojson["features"]
    ])

    if len(patches) != 2061:
        raise ValueError(
            "Unexpected number of vegetation patches"
        )

    # Apply the reusable backend detector.
    detected = detect_negative_changes(
        patches,
        thresholds
    )

    print("\n=== REAL DATA DETECTION ===")
    print("Total patches:", len(detected))

    print(
        "Eligible patches:",
        int(detected["anomaly_eligible"].sum())
    )

    print(
        "Flagged patches:",
        int(
            (
                detected["anomaly_detected"] == True
            ).sum()
        )
    )

    print(
        "Not flagged:",
        int(
            (
                detected["anomaly_detected"] == False
            ).sum()
        )
    )

    print(
        "Not evaluated:",
        int(
            detected["anomaly_detected"]
            .isna()
            .sum()
        )
    )

    print("\nDetection statuses:")
    print(
        detected["detection_status"]
        .value_counts()
        .to_string()
    )

    # Compare production detector with the
    # corrected experimental evaluation.
    experiment = pd.read_csv(EXPERIMENT)

    if experiment["patch_id"].duplicated().any():
        raise ValueError(
            "Duplicate experiment patch IDs"
        )

    comparison = detected[
        [
            "patch_id",
            "anomaly_detected"
        ]
    ].merge(
        experiment[
            [
                "patch_id",
                "anomaly_detected"
            ]
        ].rename(
            columns={
                "anomaly_detected":
                "experimental_flag"
            }
        ),
        on="patch_id",
        how="inner",
        validate="one_to_one"
    )

    if len(comparison) != len(experiment):
        raise ValueError(
            "Not all experimental patches matched"
        )

    # No experimental patch should be skipped.
    if comparison[
        "anomaly_detected"
    ].isna().any():
        raise ValueError(
            "Experimental patches unexpectedly "
            "not evaluated by production detector"
        )

    experimental_flags = (
        comparison["experimental_flag"]
        .astype("boolean")
    )

    disagreements = (
        comparison["anomaly_detected"]
        != experimental_flags
    )

    print("\n=== CONSISTENCY WITH EXPERIMENT ===")
    print("Compared:", len(comparison))
    print(
        "Flag disagreements:",
        int(disagreements.fillna(False).sum())
    )

    assert disagreements.fillna(False).sum() == 0

    print("\nVerification passed!")
    print("Production GeoJSON was not modified.")


if __name__ == "__main__":
    main()
