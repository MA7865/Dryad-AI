
"""
Verify the regional reference population used
by M2 production anomaly calculations.

Read-only diagnostic.
"""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

HISTORY = (
    ROOT / "data" / "processed"
    / "m1_features_summers.csv"
)


def main():
    df = pd.read_csv(HISTORY)

    print("=== HISTORICAL DATA ===")
    print("Rows:", len(df))
    print("Columns:", list(df.columns))
    print("Years:", sorted(df["year"].unique()))

    # Reference population:
    # Unburned patches with sufficient forest cover.
    reference = df[
        (df["burn_frac"] < 0.05)
        & (df["forest_frac"] >= 0.20)
        & df["NDVI"].notna()
        & df["NDMI"].notna()
    ].copy()

    print("\n=== REFERENCE POPULATION ===")
    print(
        "Unique patches:",
        reference["patch_id"].nunique()
    )
    print(
        "Rows by year:",
        reference.groupby("year").size().to_dict()
    )

    print("\n=== REGIONAL MEDIANS ===")
    medians = (
        reference.groupby("year")[["NDVI", "NDMI"]]
        .median()
    )
    print(medians.round(6))

    print("\n=== REGIONAL SHIFTS ===")

    for year in [2024, 2025, 2026]:
        baseline_years = list(range(2022, year))

        if year not in medians.index:
            raise ValueError(
                f"Missing regional data for {year}"
            )

        shift = (
            medians.loc[year]
            - medians.loc[baseline_years].mean()
        )

        print(
            year,
            {
                index: round(float(value), 6)
                for index, value in shift.items()
            }
        )

    print("\nRead-only diagnostic complete.")


if __name__ == "__main__":
    main()
