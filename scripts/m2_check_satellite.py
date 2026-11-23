
import os
import ee

PROJECT = os.environ["EE_PROJECT"]

ee.Initialize(project=PROJECT)

# Shaver Lake study-area boundary
aoi = ee.Geometry.Rectangle([
    -119.50, 37.00,
    -119.25, 37.20
])

# Same cloud-masking approach as M1
def mask_clouds(img):
    scl = img.select("SCL")

    clear = (
        scl.neq(3)
        .And(scl.neq(8))
        .And(scl.neq(9))
        .And(scl.neq(10))
        .And(scl.neq(11))
    )

    return img.updateMask(clear)


# Same indices as M1
def add_indices(img):
    ndvi = img.normalizedDifference(
        ["B8", "B4"]
    ).rename("NDVI")

    ndmi = img.normalizedDifference(
        ["B8", "B11"]
    ).rename("NDMI")

    return img.addBands([ndvi, ndmi])


collection = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(aoi)
    .filterDate("2026-06-01", "2026-09-01")
    .filter(
        ee.Filter.lt(
            "CLOUDY_PIXEL_PERCENTAGE", 60
        )
    )
)

processed = collection.map(mask_clouds).map(add_indices)

composite = processed.select(
    ["NDVI", "NDMI"]
).median()

# A sample point inside the study area
sample_point = ee.Geometry.Point([
    -119.40, 37.10
])

sample = composite.reduceRegion(
    reducer=ee.Reducer.first(),
    geometry=sample_point,
    scale=20,
    maxPixels=10000
).getInfo()

print("Images:", collection.size().getInfo())
print("Sample coordinates:", [-119.40, 37.10])
print("NDVI:", sample.get("NDVI"))
print("NDMI:", sample.get("NDMI"))
