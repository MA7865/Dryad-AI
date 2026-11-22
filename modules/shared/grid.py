"""Shared loading and point-to-patch lookup for the Shaver Lake grid."""
from functools import lru_cache
from pathlib import Path

import geopandas as gpd

GRID_PATH = Path(__file__).resolve().parents[2] / "data" / "grid.geojson"


@lru_cache(maxsize=1)
def load_grid() -> gpd.GeoDataFrame:
    """Load and cache the team grid, ordered deterministically by patch_id."""
    if not GRID_PATH.exists():
        raise FileNotFoundError(f"Shared grid not found at {GRID_PATH}.")
    return gpd.read_file(GRID_PATH)[["patch_id", "row", "col", "center_lon", "center_lat", "geometry"]].sort_values("patch_id")


def point_to_patch_id(lon: float, lat: float) -> str | None:
    """Map a WGS84 point to one patch using M4's intersects/first-ID rule."""
    from shapely.geometry import Point

    grid = load_grid()
    point = gpd.GeoSeries([Point(float(lon), float(lat))], crs="EPSG:4326")
    points = gpd.GeoDataFrame(geometry=point)
    joined = gpd.sjoin(points, grid, how="left", predicate="intersects")
    if joined.empty:
        return None
    patch_ids = joined["patch_id"].dropna()
    return str(patch_ids.iloc[0]) if not patch_ids.empty else None


def reload_data() -> None:
    load_grid.cache_clear()
