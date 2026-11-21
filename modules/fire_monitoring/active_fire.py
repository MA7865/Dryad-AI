"""
active_fire.py -- M4's shared function: FIRMS detections -> contract-shaped GeoJSON.

    from modules.fire_monitoring import get_active_fires
    fc = get_active_fires(start="2016-07-29", end="2016-08-10", source="VIIRS_SNPP_SP")

Returns a GeoJSON FeatureCollection (a dict). Every feature has layer_type "active_fire".
Raises FirmsError if FIRMS cannot be reached; returns an empty FeatureCollection when there
simply are no detections.
"""
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .firms_client import fetch_detections

STUDY_BBOX = (-119.50, 37.00, -119.25, 37.20)        # west, south, east, north (docs/STUDY_AREA.md)
GRID_PATH = Path(__file__).resolve().parents[2] / "data" / "grid.geojson"
DEFAULT_SOURCE = "VIIRS_NOAA20_NRT"                   # live monitoring; use *_SP sources for history
MODEL_VERSION = "m4-firms-0.1"
LAYER_TYPE = "active_fire"


@lru_cache(maxsize=1)
def load_grid() -> gpd.GeoDataFrame:
    if not GRID_PATH.exists():
        raise FileNotFoundError(f"Shared grid not found at {GRID_PATH}. Run scripts/make_grid.py.")
    return gpd.read_file(GRID_PATH)[["patch_id", "geometry"]].sort_values("patch_id")


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _check_bbox(bbox) -> tuple:
    west, south, east, north = (float(v) for v in bbox)
    sw, ss, se, sn = STUDY_BBOX
    if not (west < east and south < north):
        raise ValueError("bbox must be (west, south, east, north) with west < east and south < north")
    if west < sw or south < ss or east > se or north > sn:
        raise ValueError(f"bbox must lie inside the study area {STUDY_BBOX}")
    return west, south, east, north


def to_iso_utc(acq_date, acq_time) -> str:
    """FIRMS date '2016-08-01' + time 912 (HHMM, UTC) -> '2016-08-01T09:12:00Z'."""
    hhmm = f"{int(acq_time):04d}"
    return f"{acq_date}T{hhmm[:2]}:{hhmm[2:]}:00Z"


def detections_to_features(df: pd.DataFrame, source: str, generated_at: str = None) -> list:
    """Turn FIRMS rows into contract features, each tagged with the patch it falls in."""
    if df.empty:
        return []
    generated_at = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pts = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["longitude"], df["latitude"]), crs="EPSG:4326"
    )
    # 'intersects' so a point exactly on a cell edge still gets a patch; if two cells match,
    # the first patch_id alphabetically wins, so results are repeatable.
    joined = gpd.sjoin(pts, load_grid(), how="left", predicate="intersects")
    joined = joined[~joined.index.duplicated(keep="first")]

    features = []
    for _, r in joined.sort_values(["acq_date", "acq_time", "latitude", "longitude"]).iterrows():
        observed = to_iso_utc(r["acq_date"], r["acq_time"])
        det_id = f"{source}_{observed.replace('-', '').replace(':', '')}_{r['latitude']:.5f}_{r['longitude']:.5f}"
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point",
                         "coordinates": [round(float(r["longitude"]), 5), round(float(r["latitude"]), 5)]},
            "properties": {
                "feature_id": f"{LAYER_TYPE}:{det_id}",
                "patch_id": r["patch_id"] if isinstance(r["patch_id"], str) else None,
                "layer_type": LAYER_TYPE,
                "observed_at": observed,
                "generated_at": generated_at,
                "model_version": MODEL_VERSION,
                "source": source,
                "data_quality": "good",
                "detection_id": det_id,
                "confidence": str(r["confidence"]),
                "detection_time": observed,
                "satellite_source": source,
                "frp_mw": float(r["frp"]) if "frp" in r and pd.notna(r["frp"]) else None,
                "day_night": str(r["daynight"]) if "daynight" in r else None,
            },
        })
    return features


def get_active_fires(bbox=STUDY_BBOX, start=None, end=None, source=DEFAULT_SOURCE) -> dict:
    """Active-fire detections (satellite thermal detections, NOT confirmed fires) as GeoJSON.

    bbox:   (west, south, east, north), must lie inside the study area.
    start, end: dates (or 'YYYY-MM-DD'), both included, UTC. Default: yesterday and today.
    source: FIRMS source. Live: VIIRS_NOAA20_NRT / VIIRS_NOAA21_NRT.
            History: VIIRS_NOAA20_SP / VIIRS_NOAA21_SP (2018+), VIIRS_SNPP_SP (2012+).
    """
    bbox = _check_bbox(bbox)
    today = datetime.now(timezone.utc).date()
    end = _as_date(end) if end is not None else today
    start = _as_date(start) if start is not None else end - timedelta(days=1)
    if start > end:
        raise ValueError("start must not be after end")

    df = fetch_detections(bbox, start, end, source)
    return {"type": "FeatureCollection", "features": detections_to_features(df, source)}
