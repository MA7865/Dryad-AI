
"""
M2: Inspect the actual vegetation GeoJSON fields.

Read-only diagnostic used to design the
Pydantic API response schema.
"""

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

INPUT = (
    ROOT / "data" / "processed"
    / "vegetation" / "vegetation.geojson"
)


def main():
    with open(INPUT, encoding="utf-8") as file:
        data = json.load(file)

    if data.get("type") != "FeatureCollection":
        raise ValueError("Expected GeoJSON FeatureCollection")

    features = data["features"]

    print("=== GEOJSON STRUCTURE ===")
    print("Feature count:", len(features))
    print("Top-level keys:", sorted(data.keys()))

    geometry_types = Counter(
        feature.get("geometry", {}).get("type")
        if feature.get("geometry") is not None
        else None
        for feature in features
    )

    print("Geometry types:", dict(geometry_types))

    print("\n=== PROPERTY SCHEMA ===")

    all_keys = sorted({
        key
        for feature in features
        for key in feature["properties"]
    })

    for key in all_keys:
        values = [
            feature["properties"].get(key)
            for feature in features
        ]

        types = sorted({
            type(value).__name__
            for value in values
            if value is not None
        })

        missing = sum(
            value is None
            for value in values
        )

        print(
            f"{key}: "
            f"types={types}, "
            f"null_or_absent={missing}"
        )

    print("\n=== DETECTION CONSISTENCY ===")

    for feature in features:
        p = feature["properties"]

        status = p.get("detection_status")
        detected = p.get("anomaly_detected")

        if status == "negative_change_flagged":
            assert detected is True

        elif status == "not_flagged":
            assert detected is False

        elif status == "not_evaluated":
            assert detected is None

        else:
            raise ValueError(
                f"Unexpected detection status: {status}"
            )

    assert len(features) == 2061

    print("All detection statuses consistent.")
    print("Inspection PASSED.")


if __name__ == "__main__":
    main()
