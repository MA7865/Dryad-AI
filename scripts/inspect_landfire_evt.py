
from pathlib import Path
import rasterio
from collections import Counter

folder = Path("data/raw/landfire")

rasters = list(folder.rglob("*.tif"))

print("Raster files found:")
for raster in rasters:
    print(" -", raster)

if len(rasters) != 1:
    print(
        "\nExpected one EVT raster. "
        "Check which file is the EVT product."
    )
else:
    raster_path = rasters[0]

    with rasterio.open(raster_path) as src:
        print("\nRaster information:")
        print("File:", raster_path)
        print("CRS:", src.crs)
        print("Resolution:", src.res)
        print("Width:", src.width)
        print("Height:", src.height)
        print("Bands:", src.count)
        print("NoData:", src.nodata)
        print("Bounds:", src.bounds)

        print("\nRaster tags:")
        print(src.tags())

        print("\nFirst 15 unique pixel values:")

        # Read a small window, not the entire raster.
        from rasterio.windows import Window

        w = Window(
            0, 0,
            min(src.width, 300),
            min(src.height, 300)
        )

        arr = src.read(1, window=w, masked=True)

        counts = Counter(
            arr.compressed().tolist()
        )

        print(counts.most_common(15))
