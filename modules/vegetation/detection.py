
"""
M2 statistical vegetation anomaly detection.

Flags unusually negative NDVI / NDMI changes
using vegetation-class historical thresholds.

This is exploratory change detection,
not disease diagnosis or a trained ML model.
"""

import pandas as pd


METHOD = "historical_class_lower_5pct_v0"


def detect_negative_changes(
    patches: pd.DataFrame,
    thresholds: pd.DataFrame,
) -> pd.DataFrame:
    """
    Return anomaly detection results for eligible patches.

    Required patch columns:
        patch_id
        vegetation_class
        ndvi_anomaly
        ndmi_anomaly
        anomaly_eligible

    Required threshold columns:
        vegetation_class
        ndvi_threshold
        ndmi_threshold

    An ineligible patch is not evaluated.
    A patch with missing values is not evaluated.
    """

    patch_columns = {
        "patch_id",
        "vegetation_class",
        "ndvi_anomaly",
        "ndmi_anomaly",
        "anomaly_eligible",
    }

    threshold_columns = {
        "vegetation_class",
        "ndvi_threshold",
        "ndmi_threshold",
    }

    if not patch_columns.issubset(patches.columns):
        raise ValueError(
            "Missing patch columns: "
            f"{sorted(patch_columns - set(patches.columns))}"
        )

    if not threshold_columns.issubset(thresholds.columns):
        raise ValueError(
            "Missing threshold columns: "
            f"{sorted(threshold_columns - set(thresholds.columns))}"
        )

    if patches["patch_id"].isna().any():
        raise ValueError("Missing patch IDs")

    if patches["patch_id"].duplicated().any():
        raise ValueError("Duplicate patch IDs")

    if thresholds["vegetation_class"].isna().any():
        raise ValueError("Missing threshold class names")

    if thresholds["vegetation_class"].duplicated().any():
        raise ValueError("Duplicate vegetation threshold classes")

    result = patches.copy()

    result = result.merge(
        thresholds[
            [
                "vegetation_class",
                "ndvi_threshold",
                "ndmi_threshold",
            ]
        ],
        on="vegetation_class",
        how="left",
        validate="many_to_one",
    )

    # Missing eligibility must not become True.
    eligible = (
        result["anomaly_eligible"]
        .astype("boolean")
        .fillna(False)
    )

    required_values = [
        "ndvi_anomaly",
        "ndmi_anomaly",
        "ndvi_threshold",
        "ndmi_threshold",
    ]

    for column in required_values:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    has_values = (
        result[required_values].notna().all(axis=1)
    )

    can_evaluate = eligible & has_values

    # Nullable Booleans distinguish "not evaluated"
    # from a confident False result.
    result["ndvi_flag"] = pd.Series(
        pd.NA,
        index=result.index,
        dtype="boolean",
    )

    result["ndmi_flag"] = pd.Series(
        pd.NA,
        index=result.index,
        dtype="boolean",
    )

    result.loc[can_evaluate, "ndvi_flag"] = (
        result.loc[can_evaluate, "ndvi_anomaly"]
        < result.loc[can_evaluate, "ndvi_threshold"]
    )

    result.loc[can_evaluate, "ndmi_flag"] = (
        result.loc[can_evaluate, "ndmi_anomaly"]
        < result.loc[can_evaluate, "ndmi_threshold"]
    )

    result["anomaly_detected"] = (
        result["ndvi_flag"] | result["ndmi_flag"]
    ).astype("boolean")

    result["detection_status"] = "not_evaluated"

    result.loc[
        can_evaluate,
        "detection_status",
    ] = "not_flagged"

    result.loc[
        result["anomaly_detected"].fillna(False),
        "detection_status",
    ] = "negative_change_flagged"

    result["anomaly_method"] = METHOD

    return result
