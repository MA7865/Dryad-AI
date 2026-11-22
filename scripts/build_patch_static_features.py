"""
Build the shared 500 m static terrain table.

Usage:
    python scripts/build_patch_static_features.py --dem C:\\path\\to\\dem.tif

If a LANDFIRE raster is supplied with --landfire, its values are kept as
fuel_model and the basename is recorded in fuel_source. Without it, fuel_model
and fuel_source are null. Missing terrain is never represented by zero.

Elevation, slope and aspect are derived from the DEM in EPSG:32611. Elevation
is the mean within a patch, slope is the mean of 3x3 terrain slope in degrees,
and aspect is the circular mean in degrees.
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


def build(dem_path: Path, landfire_path: Path | None = None) -> pd.DataFrame:
    if not dem_path.exists():
        raise FileNotFoundError(
            f"DEM not found: {dem_path}. Download a DEM or pass --dem with a local path."
        )
    try:
        import rasterio
        from rasterio.mask import mask
    except ImportError as exc:
        raise RuntimeError("rasterio is required. Install requirements.txt before running this script.") from exc

    if not GRID_PATH.exists():
        raise FileNotFoundError(f"Shared grid not found: {GRID_PATH}")
    grid = gpd.read_file(GRID_PATH).sort_values("patch_id")
    grid_m = grid.to_crs("EPSG:32611")
    rows = []

    if landfire_path is not None:
        if not landfire_path.exists():
            raise FileNotFoundError(f"LANDFIRE raster not found: {landfire_path}")

    with rasterio.open(dem_path) as dem:
        dem_crs = dem.crs
        for _, patch in grid_m.iterrows():
            patch_ll = gpd.GeoSeries([patch.geometry], crs="EPSG:32611").to_crs(dem_crs).iloc[0]
            geom = [patch_ll.__geo_interface__]
            try:
                values, dem_transform = mask(dem, geom, crop=True, all_touched=True, filled=False)
                elev = values[0].compressed()
                elev_m = float(np.mean(elev)) if elev.size else None

                dem_values = values[0].filled(np.nan)
                if dem_values.shape[0] > 1 and dem_values.shape[1] > 1:
                    res_x = abs(dem_transform.a)
                    res_y = abs(dem_transform.e)
                    dzdx = np.gradient(dem_values, res_x, axis=1)
                    dzdy = np.gradient(dem_values, res_y, axis=0)
                    slope = np.degrees(np.arctan(np.sqrt(dzdx ** 2 + dzdy ** 2)))
                    aspect = (np.degrees(np.arctan2(dzdx, -dzdy)) + 360) % 360
                    valid_slope = slope[np.isfinite(slope)]
                    valid_aspect = aspect[np.isfinite(aspect)]
                    slope_deg = float(np.mean(valid_slope)) if valid_slope.size else None
                    if valid_aspect.size:
                        rad = np.radians(valid_aspect)
                        angle = math.degrees(math.atan2(np.mean(np.sin(rad)), np.mean(np.cos(rad)))) % 360
                        aspect_deg = round(angle, 3)
                    else:
                        aspect_deg = None
                else:
                    slope_deg = None
                    aspect_deg = None
            except Exception:
                elev_m = None
                slope_deg = None
                aspect_deg = None

            fuel_model = None
            fuel_source = None
            if landfire_path is not None:
                try:
                    with rasterio.open(landfire_path) as fuel:
                        fuel_geom = gpd.GeoSeries([patch.geometry], crs="EPSG:32611").to_crs(fuel.crs).iloc[0]
                        fuel_values, _ = mask(fuel, [fuel_geom.__geo_interface__], crop=True, all_touched=True)
                        fuel_flat = fuel_values[0].ravel()
                        fuel_flat = fuel_flat[np.isfinite(fuel_flat)]
                        if fuel_flat.size:
                            fuel_model = int(np.median(fuel_flat))
                    fuel_source = landfire_path.name
                except Exception:
                    fuel_model = None
                    fuel_source = landfire_path.name

            rows.append({
                "patch_id": patch["patch_id"],
                "elev_m": round(elev_m, 3) if elev_m is not None else None,
                "slope_deg": round(slope_deg, 3) if slope_deg is not None else None,
                "aspect_deg": round(aspect_deg, 3) if aspect_deg is not None else None,
                "fuel_model": fuel_model,
                "fuel_source": fuel_source,
            })

    return pd.DataFrame(rows, columns=["patch_id", "elev_m", "slope_deg", "aspect_deg", "fuel_model", "fuel_source"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dem", required=True, type=Path)
    parser.add_argument("--landfire", type=Path)
    args = parser.parse_args()
    table = build(args.dem, args.landfire)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(table)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
