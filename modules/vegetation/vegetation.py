"""Vegetation analysis entry points.

Implementation depends on the selected vegetation dataset and project
requirements.
"""

"""
M2 Vegetation Intelligence interface.

Loads precomputed LANDFIRE vegetation and
satellite-derived anomaly information.

Normal API requests do not trigger Earth Engine.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

VEGETATION_FILE = (
    ROOT / "data" / "processed"
    / "vegetation" / "vegetation.geojson"
)


def predict_vegetation(
    patch_ids: list[str] | None = None,
    as_of: str | None = None
) -> dict:
    """
    Return M2 vegetation data as GeoJSON.

    Args:
        patch_ids: Optional list of shared patch IDs.
        as_of: Reserved for future time filtering.
               Currently only the 2026 layer exists.

    Returns:
        GeoJSON FeatureCollection.

    Raises:
        FileNotFoundError: If layer has not been built.
        ValueError: If an unknown patch ID is requested
                    or an unsupported date is provided.
    """

    if as_of is not None and as_of != "2026":
        raise ValueError(
            "Only the 2026 vegetation layer is available"
        )

    if not VEGETATION_FILE.exists():
        raise FileNotFoundError(
            "Vegetation layer not built. "
            "Run scripts/m2_build_vegetation_layer.py first."
        )

    with open(VEGETATION_FILE, encoding="utf-8") as f:
        data = json.load(f)

    if data.get("type") != "FeatureCollection":
        raise ValueError("Invalid vegetation GeoJSON")

    features = data.get("features", [])

    # No filter: return full vegetation layer
    if patch_ids is None:
        return data

    available_ids = {
        feature["properties"]["patch_id"]
        for feature in features
    }

    requested_ids = set(patch_ids)
    unknown = requested_ids - available_ids

    if unknown:
        raise ValueError(
            f"Unknown patch IDs: {sorted(unknown)}"
        )

    filtered = [
        feature
        for feature in features
        if feature["properties"]["patch_id"]
        in requested_ids
    ]

    return {
        "type": "FeatureCollection",
        "features": filtered
    }
