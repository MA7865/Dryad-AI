
"""
M2 Sentinel-2 satellite diagnostic.

Reusable cloud masking and vegetation-index
functions are safe to import.

Earth Engine is initialized only when this
script is explicitly run.
"""

import os

import ee


# Shaver Lake study area
BOUNDS = [-119.50, 37.00, -119.25, 37.20]

START_DATE = "2026-06-01"
END_DATE = "2026-09-01"

DATASET = "COPERNICUS/S2_SR_HARMONIZED"


def mask_clouds(img):
    """Mask the same SCL classes as the original M2 script."""
    scl = img.select("SCL")

    clear = (
        scl.neq(3)
        .And(scl.neq(8))
        .And(scl.neq(9))
        .And(scl.neq(10))
        .And(scl.neq(11))
    )

    return img.updateMask(clear)


def add_indices(img):
    """Add NDVI and NDMI bands."""
    ndvi = img.normalizedDifference(
        ["B8", "B4"]
    ).rename("NDVI")

    ndmi = img.normalizedDifference(
        ["B8", "B11"]
    ).rename("NDMI")

    return img.addBands([ndvi, ndmi])


def initialize_gee():
    """Initialize Earth Engine using M2's project."""
    project = os.environ.get("EE_PROJECT")

    if not project:
        raise RuntimeError(
            "EE_PROJECT is not configured. "
            "Set it before running Earth Engine scripts."
        )

    ee.Initialize(project=project)


def main():
    initialize_gee()

    aoi = ee.Geometry.Rectangle(BOUNDS)

    collection = (
        ee.ImageCollection(DATASET)
        .filterBounds(aoi)
        .filterDate(START_DATE, END_DATE)
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

    sample_point = ee.Geometry.Point([
        -119.40, 37.10
    ])

    sample = composite.reduceRegion(
        reducer=ee.Reducer.first(),
        geometry=sample_point,
        scale=20,
        maxPixels=10000,
    ).getInfo()

    print("Images:", collection.size().getInfo())
    print("Sample coordinates:", [-119.40, 37.10])
    print("NDVI:", sample.get("NDVI"))
    print("NDMI:", sample.get("NDMI"))


if __name__ == "__main__":
    main()
