"""Preprocessing utilities for vegetation observations."""

import pandas as pd
import numpy as np


def prepare_burn_and_quality(
    historical: pd.DataFrame,
    anomalies: pd.DataFrame,
    year: int = 2026
) -> pd.DataFrame:
    """
    Combine M1 burn/forest data with M2 anomalies.

    Burn information is contextual only.
    Negative anomalies are NOT disease diagnoses.
    """

    latest = historical.loc[
        historical["year"] == year,
        ["patch_id", "forest_frac", "burn_frac"]
    ].copy()

    if latest["patch_id"].duplicated().any():
        raise ValueError("Duplicate patch IDs in historical data")

    if anomalies["patch_id"].duplicated().any():
        raise ValueError("Duplicate patch IDs in anomaly data")

    result = latest.merge(
        anomalies[
            ["patch_id", "ndvi_anomaly", "ndmi_anomaly"]
        ],
        on="patch_id",
        how="left",
        validate="one_to_one"
    )

    burn = result["burn_frac"]

    result["burn_status"] = np.select(
        [
            burn < 0.05,
            burn < 0.50
        ],
        [
            "unburned",
            "partial"
        ],
        default="mostly_burned"
    )

    # Any patch with at least 5% burned area is flagged.
    result["burned_flag"] = burn >= 0.05

    missing_indices = (
        result["ndvi_anomaly"].isna()
        | result["ndmi_anomaly"].isna()
    )

    # The minimum forest share matches M1's convention.
    low_forest = result["forest_frac"] < 0.20

    # Anomaly fields remain numeric measurements,
    # but only suitable patches are eligible for
    # subsequent interpretation.
    result["anomaly_status"] = np.select(
        [
            missing_indices,
            low_forest,
            result["burned_flag"]
        ],
        [
            "insufficient_data",
            "low_forest_cover",
            "burn_affected"
        ],
        default="not_evaluated"
    )

    result["data_quality"] = np.select(
        [
            missing_indices,
            low_forest,
            result["burned_flag"]
        ],
        [
            "missing",
            "limited",
            "limited"
        ],
        default="good"
    )

    return result
