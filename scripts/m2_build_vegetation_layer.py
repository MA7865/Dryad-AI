
"""
M2: Build the combined vegetation GeoJSON layer.

Combines:
- LANDFIRE LF2024 EVT vegetation reference
- M2 Sentinel-2 summer 2026 features
- M1 historical anomaly and burn information

Normal API requests read this saved output.
They do not run Google Earth Engine.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


from modules.vegetation.detection import detect_negative_changes



ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data" / "processed" / "vegetation"

REFERENCE = FOLDER / "vegetation_reference.geojson"
FEATURES = FOLDER / "vegetation_features.csv"
BURN_QUALITY = FOLDER / "vegetation_burn_quality.csv"
OUTPUT = FOLDER / "vegetation.geojson"
THRESHOLDS = FOLDER / "anomaly_thresholds.csv"
GRID = ROOT / "data" / "grid.geojson"


def clean(value):
    """Convert pandas/NumPy missing values to JSON null."""
    if value is None:
        return None

    if isinstance(value, (list, dict)):
        return value

    if pd.isna(value):
        return None

    if hasattr(value, "item"):
        return value.item()

    return value


def build_vegetation_layer():
    # Load LANDFIRE reference GeoJSON
    with open(REFERENCE, encoding="utf-8") as f:
        reference = json.load(f)

    # Load satellite features and anomaly/burn data
    satellite = pd.read_csv(FEATURES)
    burn_quality = pd.read_csv(BURN_QUALITY)

    # Check for duplicate IDs
    for name, df in [
        ("satellite", satellite),
        ("burn_quality", burn_quality)
    ]:
        if df["patch_id"].duplicated().any():
            raise ValueError(
                f"Duplicate patch IDs in {name}"
            )

    # Combine CSV data
    merged = satellite.merge(
        burn_quality,
        on="patch_id",
        how="outer",
        validate="one_to_one"
    )

    records = {
        row["patch_id"]: {
            key: clean(value)
            for key, value in row.items()
            if key != "patch_id"
        }
        for row in merged.to_dict("records")
    }

    # Validate against the original shared grid
    with open(GRID, encoding="utf-8") as f:
        grid = json.load(f)

    expected_ids = {
        f["properties"]["patch_id"]
        for f in grid["features"]
    }

    actual_ids = [
        f["properties"]["patch_id"]
        for f in reference["features"]
    ]

    if (
        len(actual_ids) != len(expected_ids)
        or len(set(actual_ids)) != len(actual_ids)
        or set(actual_ids) != expected_ids
    ):
        raise ValueError(
            "Vegetation reference does not match shared grid"
        )

    if set(records) != expected_ids:
        raise ValueError(
            "Satellite/burn records do not match shared grid"
        )

    generated_at = datetime.now(
        timezone.utc
    ).isoformat()

    # Combine properties for each original patch
    for feature in reference["features"]:
        properties = feature["properties"]
        patch_id = properties["patch_id"]
        extra = records[patch_id]

        # Preserve LANDFIRE reference quality
        vegetation_quality = properties.get(
            "data_quality", "missing"
        )

        # Preserve historical anomaly quality
        anomaly_quality = extra.get(
            "data_quality", "missing"
        )

        anomaly_status = extra.get(
            "anomaly_status", "insufficient_data"
        )

        # Determine availability of M2 Sentinel-2 features
        ndvi = extra.get("NDVI")
        ndmi = extra.get("NDMI")
        obs_count = extra.get("obs_count")

        satellite_available = (
            ndvi is not None
            and ndmi is not None
            and obs_count is not None
            and obs_count > 0
        )

        # Add satellite and anomaly values
        properties.update(extra)

        # Separate quality fields
        properties["vegetation_data_quality"] = (
            vegetation_quality
        )

        properties["anomaly_data_quality"] = (
            anomaly_quality
        )

        properties["satellite_data_quality"] = (
            "available"
            if satellite_available
            else "missing"
        )

        # Eligibility does not mean anomaly detected
        properties["anomaly_eligible"] = (
            anomaly_status == "not_evaluated"
            and anomaly_quality == "good"
        )

        # Source provenance
        properties["vegetation_source"] = (
            "LANDFIRE LF2024 EVT"
        )

        properties["satellite_source"] = (
            "Sentinel-2 SR Harmonized; "
            "M2 summer 2026 extraction"
        )

        properties["anomaly_source"] = (
            "M1 summer features 2022-2026; "
            "2022-2025 baseline"
        )

        properties["generated_at"] = generated_at
        properties["layer_type"] = "vegetation"

        # No trained M2 predictive model yet
        properties["model_version"] = None
        properties["processing_version"] = "m2-v0.2"

        properties["source"] = (
            "LANDFIRE LF2024 EVT; "
            "Sentinel-2 SR Harmonized; "
            "M1 historical summer features"
        )

        # Vegetation class comes from reference data
        properties["prediction_kind"] = (
            "reference_lookup"
        )

        # Maintain backward-compatible combined quality
        if (
            vegetation_quality == "missing"
            or anomaly_quality == "missing"
        ):
            properties["data_quality"] = "missing"

        elif (
            vegetation_quality == "partial"
            or anomaly_quality != "good"
        ):
            properties["data_quality"] = "limited"

        else:
            properties["data_quality"] = "good"


    # -------------------------------------------------
    # M2 statistical anomaly detection
    # -------------------------------------------------

    if not THRESHOLDS.exists():
        raise FileNotFoundError(
            "Missing anomaly thresholds. Run "
            "python -m scripts.m2_verify_real_detection"
        )

    thresholds = pd.read_csv(THRESHOLDS)

    detection_input = pd.DataFrame([
        feature["properties"]
        for feature in reference["features"]
    ])

    detection_results = detect_negative_changes(
        detection_input,
        thresholds
    )

    detection_results = detection_results.set_index(
        "patch_id"
    )

    flagged_count = 0
    evaluated_count = 0

    for feature in reference["features"]:
        properties = feature["properties"]
        patch_id = properties["patch_id"]

        result = detection_results.loc[patch_id]

        detected = result["anomaly_detected"]

        # Convert nullable Pandas values into
        # standard JSON-compatible Python values.
        if pd.isna(detected):
            properties["anomaly_detected"] = None
        else:
            properties["anomaly_detected"] = bool(
                detected
            )
            evaluated_count += 1

            if bool(detected):
                flagged_count += 1

        for field in [
            "ndvi_flag",
            "ndmi_flag",
        ]:
            value = result[field]

            properties[field] = (
                None
                if pd.isna(value)
                else bool(value)
            )

        for field in [
            "ndvi_threshold",
            "ndmi_threshold",
        ]:
            value = result[field]

            properties[field] = (
                None
                if pd.isna(value)
                else float(value)
            )

        properties["detection_status"] = str(
            result["detection_status"]
        )

        properties["anomaly_method"] = str(
            result["anomaly_method"]
        )

    print(
        "Evaluated patches:",
        evaluated_count
    )

    print(
        "Negative changes flagged:",
        flagged_count
    )

    print(
        "Not evaluated:",
        len(reference["features"])
        - evaluated_count
    )

    output = {
        "type": "FeatureCollection",
        "features": reference["features"]
    }

    # Save the completed GeoJSON
    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(
            output,
            f,
            indent=2,
            allow_nan=False
        )

    print("Vegetation layer created!")
    print("Total features:", len(output["features"]))
    print("Output:", OUTPUT)
    print(
        "File size MB:",
        round(OUTPUT.stat().st_size / 1e6, 2)
    )


if __name__ == "__main__":
    build_vegetation_layer()
