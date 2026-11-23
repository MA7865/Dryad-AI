
"""
M2 historical anomaly backtest.

Uses:
- The full unburned forest regional reference
- Vegetation-specific eligible peer groups
- Historical baselines preceding each target year

This is an exploratory backtest, not a
validated disturbance-detection model.
"""

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data" / "processed" / "vegetation"

HISTORY = ROOT / "data/processed/m1_features_summers.csv"
REFERENCE = FOLDER / "vegetation_reference.geojson"
OUTPUT = FOLDER / "anomaly_backtest.csv"


def main():
    historical = pd.read_csv(HISTORY)

    with open(REFERENCE, encoding="utf-8") as f:
        reference_geojson = json.load(f)

    vegetation = pd.DataFrame([
        {
            "patch_id": feature["properties"]["patch_id"],
            "vegetation_class": feature["properties"].get(
                "vegetation_class"
            )
        }
        for feature in reference_geojson["features"]
    ])

    df = historical.merge(
        vegetation,
        on="patch_id",
        validate="many_to_one"
    )

    # IMPORTANT:
    # The regional reference must use the full
    # 754-patch reference population, not only
    # the six large vegetation peer groups.
    regional_reference = historical[
        (historical["burn_frac"] < 0.05)
        & (historical["forest_frac"] >= 0.20)
        & historical["NDVI"].notna()
        & historical["NDMI"].notna()
    ].copy()

    regional_medians = (
        regional_reference
        .groupby("year")[["NDVI", "NDMI"]]
        .median()
    )

    # Select patches eligible for peer analysis.
    eligible = df[
        (df["burn_frac"] < 0.05)
        & (df["forest_frac"] >= 0.20)
        & df["vegetation_class"].notna()
        & df["NDVI"].notna()
        & df["NDMI"].notna()
    ].copy()

    class_counts = (
        eligible[["patch_id", "vegetation_class"]]
        .drop_duplicates()
        ["vegetation_class"]
        .value_counts()
    )

    large_classes = set(
        class_counts[class_counts >= 30].index
    )

    eligible = eligible[
        eligible["vegetation_class"].isin(
            large_classes
        )
    ].copy()

    print("Regional reference patches:",
          regional_reference["patch_id"].nunique())

    print("Peer groups:", len(large_classes))

    print("Unique eligible patches:",
          eligible["patch_id"].nunique())

    results = []

    for target_year in [2024, 2025, 2026]:
        baseline_years = list(
            range(2022, target_year)
        )

        baseline = eligible[
            eligible["year"].isin(baseline_years)
        ]

        current = eligible[
            eligible["year"] == target_year
        ].copy()

        for index in ["NDVI", "NDMI"]:

            patch_baseline = (
                baseline.groupby("patch_id")[index]
                .mean()
            )

            # Use the full regional reference
            # for the shift calculation.
            regional_shift = (
                regional_medians.loc[
                    target_year, index
                ]
                - regional_medians.loc[
                    baseline_years, index
                ].mean()
            )

            current[f"{index.lower()}_anomaly"] = (
                current[index]
                - current["patch_id"].map(
                    patch_baseline
                )
                - regional_shift
            )

        current["target_year"] = target_year

        results.append(current[
            [
                "patch_id",
                "vegetation_class",
                "target_year",
                "ndvi_anomaly",
                "ndmi_anomaly"
            ]
        ])

    backtest = pd.concat(
        results,
        ignore_index=True
    )

    if backtest.duplicated(
        ["patch_id", "target_year"]
    ).any():
        raise ValueError(
            "Duplicate patch-year records"
        )

    print("\n=== CORRECTED BACKTEST ===")

    for year, group in backtest.groupby(
        "target_year"
    ):
        print(f"\nYear: {year}")
        print("Patches:", len(group))

        print(
            group[
                ["ndvi_anomaly", "ndmi_anomaly"]
            ]
            .describe()
            .round(4)
        )

    backtest.to_csv(
        OUTPUT,
        index=False
    )

    print("\nSaved:", OUTPUT)


if __name__ == "__main__":
    main()
