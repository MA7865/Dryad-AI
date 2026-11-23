"""
terrain.py -- elevation for the fire-spread model (Version 2: slope).

Elevation comes from the free AWS "Terrain Tiles" (Terrarium PNG format, built from USGS 3DEP / SRTM and
other sources; roughly 30 m cells at zoom 12 in California). Each tile is a 256 x 256 PNG where
    elevation_m = R * 256 + G + B / 256 - 32768
Tiles are downloaded once and cached on disk (data/raw/terrain/, not committed).

The spread model works on a 90 m grid (spread_v0.Domain). get_elevation() returns the mean elevation of
each 90 m cell, from a 3 x 3 sample of the 30 m surface, so a single noisy pixel does not make a fake cliff.

Nothing here needs an API key. Terrain tiles: https://registry.opendata.aws/terrain-tiles/
"""
import math
import time
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from PIL import Image
from pyproj import Transformer

from modules.fire_monitoring.spread_v0 import CRS_LL, CRS_M, Domain

TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
ZOOM = 12
TILE_PX = 256
DEFAULT_CACHE = Path("data/raw/terrain")
SUB_OFFSETS_M = (-30.0, 0.0, 30.0)          # 3 x 3 samples inside each 90 m cell

_TO_LL = Transformer.from_crs(CRS_M, CRS_LL, always_xy=True)


class TerrainError(RuntimeError):
    """Terrain tiles could not be downloaded."""


def decode_terrarium(rgb: np.ndarray) -> np.ndarray:
    """(256, 256, 3) uint8 array -> elevation in metres."""
    rgb = rgb.astype(np.float64)
    return rgb[..., 0] * 256.0 + rgb[..., 1] + rgb[..., 2] / 256.0 - 32768.0


def encode_terrarium(elev: np.ndarray) -> np.ndarray:
    """Inverse of decode_terrarium (used by the tests to build fake tiles)."""
    v = np.asarray(elev, dtype=np.float64) + 32768.0
    r = np.floor(v / 256.0)
    g = np.floor(v - r * 256.0)
    b = np.floor((v - np.floor(v)) * 256.0)
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


def lonlat_to_global_px(lon, lat, zoom: int = ZOOM):
    """Web-Mercator pixel position of (lon, lat) on the whole-world image at this zoom."""
    n = TILE_PX * 2 ** zoom
    lat = np.clip(lat, -85.05112878, 85.05112878)
    x = (np.asarray(lon, dtype=np.float64) + 180.0) / 360.0 * n
    y = (1.0 - np.log(np.tan(np.radians(lat)) + 1.0 / np.cos(np.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def fetch_tile(z: int, x: int, y: int, cache_dir: Path = DEFAULT_CACHE, retries: int = 3) -> np.ndarray:
    """One tile as an elevation array (metres), from the cache or the web."""
    path = Path(cache_dir) / str(z) / str(x) / f"{y}.png"
    if path.exists():
        data = path.read_bytes()
    else:
        url = TILE_URL.format(z=z, x=x, y=y)
        problem = ""
        for attempt in range(retries):
            try:
                r = requests.get(url, timeout=30)
                if r.status_code == 200:
                    data = r.content
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                    break
                problem = f"HTTP {r.status_code}"
            except requests.RequestException as e:
                problem = type(e).__name__
            time.sleep(1.5 * 2 ** attempt)
        else:
            raise TerrainError(f"could not download terrain tile {z}/{x}/{y} ({problem})")
    return decode_terrarium(np.asarray(Image.open(BytesIO(data)).convert("RGB")))


def elevation_at(lons, lats, zoom: int = ZOOM, cache_dir: Path = DEFAULT_CACHE, tile_fn=fetch_tile) -> np.ndarray:
    """Bilinear elevation (m) at the given points. lons and lats are arrays of the same shape."""
    lons, lats = np.asarray(lons, dtype=np.float64), np.asarray(lats, dtype=np.float64)
    px, py = lonlat_to_global_px(lons, lats, zoom)
    px, py = px - 0.5, py - 0.5                          # pixel centres sit half a pixel in
    x0, y0 = np.floor(px).astype(int), np.floor(py).astype(int)
    tx0, tx1 = int(x0.min()) // TILE_PX, (int(x0.max()) + 1) // TILE_PX
    ty0, ty1 = int(y0.min()) // TILE_PX, (int(y0.max()) + 1) // TILE_PX
    mosaic = np.full(((ty1 - ty0 + 1) * TILE_PX, (tx1 - tx0 + 1) * TILE_PX), np.nan)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            mosaic[(ty - ty0) * TILE_PX:(ty - ty0 + 1) * TILE_PX,
                   (tx - tx0) * TILE_PX:(tx - tx0 + 1) * TILE_PX] = tile_fn(zoom, tx, ty, cache_dir)
    ix, iy = x0 - tx0 * TILE_PX, y0 - ty0 * TILE_PX
    fx, fy = px - x0, py - y0
    z00, z10 = mosaic[iy, ix], mosaic[iy, ix + 1]
    z01, z11 = mosaic[iy + 1, ix], mosaic[iy + 1, ix + 1]
    return (z00 * (1 - fx) * (1 - fy) + z10 * fx * (1 - fy) + z01 * (1 - fx) * fy + z11 * fx * fy)


def get_elevation(domain: Domain, cache_dir: Path = DEFAULT_CACHE, tile_fn=fetch_tile) -> np.ndarray:
    """Mean elevation (m) of every 90 m cell of the simulation domain. Shape = domain.shape.

    Row 0 is the southern edge and column 0 the western edge, like every other array in the model.
    """
    memo = {}

    def cached_tile(z, tx, ty, cache):                  # decode each tile once, not once per sample point
        if (z, tx, ty) not in memo:
            memo[(z, tx, ty)] = tile_fn(z, tx, ty, cache)
        return memo[(z, tx, ty)]

    xs, ys = domain.centres()
    total = np.zeros(domain.shape)
    for dy in SUB_OFFSETS_M:
        for dx in SUB_OFFSETS_M:
            lon, lat = _TO_LL.transform(xs + dx, ys + dy)
            total += elevation_at(lon, lat, cache_dir=cache_dir, tile_fn=cached_tile)
    return total / len(SUB_OFFSETS_M) ** 2
