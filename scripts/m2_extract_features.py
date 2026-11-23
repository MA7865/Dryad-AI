
"""
M2 Sentinel-2 feature extraction.

Extracts NDVI, NDMI, and observation counts
for the shared 2,061-patch grid.

Validates results before replacing the output CSV.
Importing this module does not run Earth Engine.
"""

import json
import math
import os
import tempfile
from pathlib import Path

import ee
import pandas as pd

from scripts.m2_check_satellite import (
    mask_clouds,
    add_indices,
    initialize_gee,
    DATASET,
    START_DATE,
    END_DATE,
)


ROOT = Path(__file__).resolve().parents[1]

GRID = ROOT / "data" / "grid.geojson"

OUTPUT = (
    ROOT / "data" / "processed"
    / "vegetation" / "vegetation_features.csv"
)

EXPECTED_PATCHES = 2061


def load_grid():
    """Load and validate the shared grid."""
    with open(GRID, encoding="utf-8") as f:
        grid = json.load(f)

    if grid.get("type") != "FeatureCollection":
        raise ValueError("Invalid grid GeoJSON")

    features = grid.get("features", [])

    patch_ids = [
        f["properties"]["patch_id"]
        for f in features
    ]

    if len(patch_ids) != EXPECTED_PATCHES:
        raise ValueError(
            f"Expected {EXPECTED_PATCHES} grid patches; "
            f"found {len(patch_ids)}"
        )

    if len(set(patch_ids)) != len(patch_ids):
        raise ValueError("Duplicate patch IDs in grid")

    if any(not isinstance(pid, str) or not pid for pid in patch_ids):
        raise ValueError("Invalid patch ID in grid")

    return features, patch_ids


def validate_extraction(df, expected_ids):
    """Reject incomplete or inconsistent extraction results."""
    columns = [
        "patch_id",
        "NDVI",
        "NDMI",
        "obs_count",
    ]

    missing_columns = set(columns) - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing extracted columns: "
            f"{sorted(missing_columns)}"
        )

    if len(df) != len(expected_ids):
        raise ValueError(
            "Extraction returned an unexpected row count: "
            f"{len(df)}"
        )

    if df["patch_id"].isna().any():
        raise ValueError("Missing patch IDs")

    if df["patch_id"].duplicated().any():
        raise ValueError("Duplicate extracted patch IDs")

    if set(df["patch_id"]) != set(expected_ids):
        raise ValueError(
            "Extracted patch IDs do not match shared grid"
        )

    for name in ["NDVI", "NDMI", "obs_count"]:
        df[name] = pd.to_numeric(
            df[name],
            errors="raise",
        )

        if df[name].isna().any():
            raise ValueError(
                f"Missing {name} values"
            )

        if not df[name].map(math.isfinite).all():
            raise ValueError(
                f"Non-finite {name} values"
            )

    for name in ["NDVI", "NDMI"]:
        if not df[name].between(-1, 1).all():
            raise ValueError(
                f"{name} outside valid index range"
            )

    if not (df["obs_count"] > 0).all():
        raise ValueError(
            "Some patches have no clear observations"
        )

    return df


def save_safely(df):
    """
    Write a temporary CSV, then atomically
    replace the previous result.

    A failed validation leaves the old CSV intact.
    """
    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            prefix="m2_features_",
            dir=OUTPUT.parent,
            encoding="utf-8",
            newline="",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            df.to_csv(temp_file, index=False)

        # Confirm the staged file can be loaded.
        staged = pd.read_csv(temp_path)

        validate_extraction(
            staged,
            df["patch_id"].tolist(),
        )

        os.replace(temp_path, OUTPUT)

    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main():
    # Validate local input before any GEE request.
    grid_features, expected_ids = load_grid()

    # Authentication and network work start here.
    initialize_gee()

    features = [
        ee.Feature(
            ee.Geometry(
                patch["geometry"],
                None,
                False,
            ),
            {
                "patch_id":
                patch["properties"]["patch_id"]
            },
        )
        for patch in grid_features
    ]

    grid_fc = ee.FeatureCollection(features)

    collection = (
        ee.ImageCollection(DATASET)
        .filterBounds(
            grid_fc.geometry().bounds()
        )
        .filterDate(
            START_DATE,
            END_DATE,
        )
        .filter(
            ee.Filter.lt(
                "CLOUDY_PIXEL_PERCENTAGE", 60
            )
        )
    )

    processed = (
        collection
        .map(mask_clouds)
        .map(add_indices)
    )

    composite = processed.select(
        ["NDVI", "NDMI"]
    ).median()

    observations = (
        processed.select("NDVI")
        .count()
        .rename("obs_count")
    )

    stack = composite.addBands(observations)

    print("Starting Earth Engine extraction...")

    reduced = stack.reduceRegions(
        collection=grid_fc,
        reducer=ee.Reducer.mean(),
        scale=20,
        tileScale=4,
    )

    reduced = reduced.select(
        [
            "patch_id",
            "NDVI",
            "NDMI",
            "obs_count",
        ],
        None,
        False,
    )

    rows = [
        feature["properties"]
        for feature in reduced.getInfo()["features"]
    ]

    df = pd.DataFrame(rows)

    df = validate_extraction(
        df,
        expected_ids,
    )

    # Restore the exact original grid ordering.
    df = df.set_index("patch_id")
    df = df.loc[expected_ids].reset_index()

    df = df[
        ["patch_id", "NDVI", "NDMI", "obs_count"]
    ].copy()

    df["year"] = 2026
    df["window_start"] = START_DATE
    df["window_end"] = END_DATE

    # Only replace the existing CSV after success.
    save_safely(df)

    print("Extraction complete!")
    print("Rows:", len(df))
    print("Columns:", df.columns.tolist())
    print(df.head())
    print("Saved to:", OUTPUT)


if __name__ == "__main__":
    main()
