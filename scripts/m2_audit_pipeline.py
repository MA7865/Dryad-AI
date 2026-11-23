
"""
M2 pipeline consistency audit.

Checks source files, shared patch IDs,
historical coverage and final output.

Read-only: does not modify any files.
"""

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FOLDER = DATA / "processed" / "vegetation"

FILES = {
    "grid": DATA / "grid.geojson",
    "reference": FOLDER / "vegetation_reference.geojson",
    "satellite": FOLDER / "vegetation_features.csv",
    "history": DATA / "processed" / "m1_features_summers.csv",
    "anomalies": FOLDER / "vegetation_anomalies.csv",
    "burn_quality": FOLDER / "vegetation_burn_quality.csv",
    "backtest": FOLDER / "anomaly_backtest.csv",
    "thresholds": FOLDER / "anomaly_thresholds.csv",
    "layer": FOLDER / "vegetation.geojson",
}


def load_geojson(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    assert data["type"] == "FeatureCollection"
    return data


def check_unique_ids(name, ids):
    ids = list(ids)

    assert len(ids) == len(set(ids)), (
        f"Duplicate patch IDs in {name}"
    )

    assert not any(pd.isna(x) for x in ids), (
        f"Missing patch IDs in {name}"
    )

    return set(ids)


def main():
    print("=== FILE AVAILABILITY ===")

    for name, path in FILES.items():
        assert path.is_file(), (
            f"Missing {name}: {path}"
        )

        print(
            f"{name}: OK "
            f"({path.stat().st_size / 1e6:.2f} MB)"
        )

    print("\n=== SHARED GRID ===")

    grid = load_geojson(FILES["grid"])

    grid_ids = check_unique_ids(
        "grid",
        (
            f["properties"]["patch_id"]
            for f in grid["features"]
        ),
    )

    assert len(grid_ids) == 2061
    print("Grid patches:", len(grid_ids))

    print("\n=== PATCH ID ALIGNMENT ===")

    for name in [
        "reference",
        "layer",
    ]:
        data = load_geojson(FILES[name])

        ids = check_unique_ids(
            name,
            (
                f["properties"]["patch_id"]
                for f in data["features"]
            ),
        )

        assert ids == grid_ids, (
            f"{name} does not match shared grid"
        )

        print(name, "matches grid:", len(ids))

    for name in [
        "satellite",
        "anomalies",
        "burn_quality",
    ]:
        df = pd.read_csv(FILES[name])

        ids = check_unique_ids(
            name,
            df["patch_id"],
        )

        assert ids == grid_ids, (
            f"{name} does not match shared grid"
        )

        print(name, "matches grid:", len(ids))

    print("\n=== HISTORICAL COVERAGE ===")

    history = pd.read_csv(FILES["history"])

    assert not history.duplicated(
        ["patch_id", "year"]
    ).any(), "Duplicate historical patch-years"

    years = sorted(
        history["year"].unique().tolist()
    )

    assert years == [
        2022, 2023, 2024, 2025, 2026
    ]

    for year in years:
        year_ids = set(
            history.loc[
                history["year"] == year,
                "patch_id"
            ]
        )

        assert year_ids == grid_ids, (
            f"Incomplete historical grid: {year}"
        )

        print(
            f"{year}: {len(year_ids)} patches"
        )

    print("\n=== THRESHOLD COVERAGE ===")

    thresholds = pd.read_csv(
        FILES["thresholds"]
    )

    assert not thresholds[
        "vegetation_class"
    ].duplicated().any()

    assert thresholds[
        ["ndvi_threshold", "ndmi_threshold"]
    ].notna().all().all()

    print(
        "Calibrated vegetation groups:",
        len(thresholds)
    )

    print("\n=== FINAL LAYER ===")

    layer = load_geojson(FILES["layer"])

    properties = pd.DataFrame([
        f["properties"]
        for f in layer["features"]
    ])

    counts = (
        properties["detection_status"]
        .value_counts()
        .to_dict()
    )

    assert len(properties) == 2061

    assert (
        properties["anomaly_detected"].isna()
        == (
            properties["detection_status"]
            == "not_evaluated"
        )
    ).all()

    print("Detection statuses:", counts)

    # Verify final NDVI/NDMI values still match
    # the M2 satellite extraction input.
    satellite = pd.read_csv(
        FILES["satellite"]
    )

    comparison = properties[
        ["patch_id", "NDVI", "NDMI"]
    ].merge(
        satellite[
            ["patch_id", "NDVI", "NDMI"]
        ],
        on="patch_id",
        suffixes=("_layer", "_source"),
        validate="one_to_one",
    )

    assert len(comparison) == 2061

    for index in ["NDVI", "NDMI"]:
        difference = (
            comparison[f"{index}_layer"]
            - comparison[f"{index}_source"]
        ).abs()

        assert difference.notna().all()
        assert difference.max() < 1e-8, (
            f"{index} differs from extraction source"
        )

        print(
            f"{index} aligned; "
            f"max difference: {difference.max():.10f}"
        )

    print("\nPIPELINE AUDIT PASSED")
    print("No files were modified.")


if __name__ == "__main__":
    main()
