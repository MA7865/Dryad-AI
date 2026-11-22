"""
Build the shared 500 m static terrain and fuel table.

Defaults use the downloaded LANDFIRE rasters in data/raw/landfire/.
Elevation and slope are mean values for valid pixels. Aspect is the circular
mean of non-flat pixels (-1 and nodata pixels are excluded). Fuel is the most
common FBFM40 numeric code among valid pixels.

Run:
    python scripts/build_patch_static_features.py

The grid is loaded in EPSG:4326, converted to EPSG:5070 for patch raster
aggregation, and written in sorted patch_id order.
"""
import argparse
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GRID_PATH = ROOT / "data" / "grid.geojson"
OUT_PATH = ROOT / "data" / "processed" / "patch_static_features.csv"
LANDFIRE_ROOT = ROOT / "data" / "raw" / "landfire"

DEFAULT_ELEV = LANDFIRE_ROOT / "LF2020_Elev_CONUS" / "LF2020_Elev_CONUS.tif"
DEFAULT_SLOPE = LANDFIRE_ROOT / "LF2020_SlpD_CONUS" / "LF2020_SlpD_CONUS.tif"
DEFAULT_ASPECT = LANDFIRE_ROOT / "LF2020_Asp_CONUS" / "LF2020_Asp_CONUS.tif"
DEFAULT_FUEL = LANDFIRE_ROOT / "LF2025_FBFM40_CONUS" / "LF2025_FBFM40_CONUS.tif"


def _mask_values(dataset, geometry, *, nodata_values=()) -> np.ndarray:
    from rasterio.mask import mask

    values, _ = mask(dataset, [geometry], crop=True, all_touched=True)
    flat = values[0].ravel().astype(np.float64)
    flat = flat[np.isfinite(flat)]
    for nodata in nodata_values:
        flat = flat[flat != nodata]
    return flat


def circular_mean(values: np.ndarray) -> float | None:
    valid = values[(values >= 0) & (values <= 359) & np.isfinite(values)]
    if valid.size == 0:
        return None
    radians = np.radians(valid)
    mean = math.degrees(math.atan2(np.mean(np.sin(radians)), np.mean(np.cos(radians)))) % 360
    return round(float(mean), 3)


def build(
    dem_path: Path = DEFAULT_ELEV,
    slope_path: Path = DEFAULT_SLOPE,
    aspect_path: Path = DEFAULT_ASPECT,
    fuel_path: Path = DEFAULT_FUEL,
) -> pd.DataFrame:
    paths = {
        "Elevation": dem_path,
        "Slope": slope_path,
        "Aspect": aspect_path,
        "FBFM40": fuel_path,
    }
    missing = [f"{name}: {path}" for name, path in paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError("Required LANDFIRE raster missing:\n" + "\n".join(missing))

    try:
        import rasterio
    except ImportError as exc:
        raise RuntimeError("rasterio is required. Install it in the project venv.") from exc

    if not GRID_PATH.exists():
        raise FileNotFoundError(f"Shared grid not found: {GRID_PATH}")
    grid = gpd.read_file(GRID_PATH).sort_values("patch_id")
    rows = []

    with rasterio.open(dem_path) as elev_ds, rasterio.open(slope_path) as slope_ds, \
         rasterio.open(aspect_path) as aspect_ds, rasterio.open(fuel_path) as fuel_ds:
        target_crs = elev_ds.crs
        for name, dataset in (
            ("Elevation", elev_ds),
            ("Slope", slope_ds),
            ("Aspect", aspect_ds),
            ("FBFM40", fuel_ds),
        ):
            if dataset.crs != target_crs:
                raise ValueError(f"{name} CRS {dataset.crs} does not match Elevation CRS {target_crs}")

        grid_native = grid.to_crs(target_crs)
        for _, patch in grid_native.iterrows():
            geometry = patch.geometry.__geo_interface__

            elevation = _mask_values(elev_ds, geometry, nodata_values=(-9999, elev_ds.nodata))
            elev_m = round(float(np.mean(elevation)), 3) if elevation.size else None

            slope = _mask_values(slope_ds, geometry, nodata_values=(32767, 65535, slope_ds.nodata))
            slope = slope[(slope >= 0) & (slope <= 90)]
            slope_deg = round(float(np.mean(slope)), 3) if slope.size else None

            aspect = _mask_values(aspect_ds, geometry, nodata_values=(-9999, -1, aspect_ds.nodata))
            aspect_deg = circular_mean(aspect)

            fuel = _mask_values(fuel_ds, geometry, nodata_values=(32767, -9999, fuel_ds.nodata))
            fuel = fuel[(fuel >= 91) & (fuel <= 204)]
            fuel_model = None
            if fuel.size:
                values, counts = np.unique(fuel.astype(np.int32), return_counts=True)
                fuel_model = int(values[np.argmax(counts)])

            rows.append({
                "patch_id": patch["patch_id"],
                "elev_m": elev_m,
                "slope_deg": slope_deg,
                "aspect_deg": aspect_deg,
                "fuel_model": fuel_model,
                "fuel_source": fuel_path.name if fuel_model is not None else None,
            })

    return pd.DataFrame(rows, columns=["patch_id", "elev_m", "slope_deg", "aspect_deg", "fuel_model", "fuel_source"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dem", type=Path, default=DEFAULT_ELEV)
    parser.add_argument("--slope", type=Path, default=DEFAULT_SLOPE)
    parser.add_argument("--aspect", type=Path, default=DEFAULT_ASPECT)
    parser.add_argument("--landfire", type=Path, default=DEFAULT_FUEL)
    args = parser.parse_args()
    table = build(args.dem, args.slope, args.aspect, args.landfire)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(table)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
