"""Vegetation anomaly detection utilities."""

import numpy as np
import pandas as pd


def calculate_vegetation_anomalies(
    historical: pd.DataFrame,
    baseline_years=(2022, 2023, 2024, 2025),
    target_year=2026
) -> pd.DataFrame:
    """
    Compute peer-adjusted NDVI and NDMI anomalies.

    Uses M1's consistent historical feature table.

    Negative anomaly:
        Patch is below its baseline after adjusting
        for regional reference-year changes.

    This does not identify or diagnose disease.
    """

    df = historical.copy()

    # M1's reference-group conditions
    reference_mask = (
        (df["burn_frac"] < 0.05)
        & (df["forest_frac"] >= 0.20)
        & df["NDVI"].notna()
        & df["NDMI"].notna()
    )

    reference = df.loc[reference_mask]

    results = []

    for index in ("NDVI", "NDMI"):

        # Same-year reference median
        yearly_medians = (
            reference.groupby("year")[index]
            .median()
        )

        # Average regional reference median
        # across baseline years only
        baseline_regional = (
            yearly_medians
            .reindex(baseline_years)
            .mean()
        )

        target_regional = yearly_medians.get(
            target_year, np.nan
        )

        regional_shift = (
            target_regional - baseline_regional
        )

        # Per-patch baseline over 2022–2025
        baseline = (
            df[df["year"].isin(baseline_years)]
            .groupby("patch_id")[index]
            .mean()
        )

        # Current target-year observations
        current = (
            df[df["year"] == target_year]
            .set_index("patch_id")
        )

        anomaly = (
            current[index]
            - baseline
            - regional_shift
        )

        result = pd.DataFrame({
            "patch_id": current.index,
            f"{index.lower()}_anomaly": anomaly.values
        })

        results.append(result)

    merged = results[0].merge(
        results[1],
        on="patch_id",
        how="outer",
        validate="one_to_one"
    )

    return merged
