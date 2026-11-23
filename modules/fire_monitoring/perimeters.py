"""
perimeters.py -- M4's shared function: historical fire perimeters (CAL FIRE) as contract GeoJSON.

    from modules.fire_monitoring import get_perimeters
    fc = get_perimeters(year_from=2016, year_to=2016)        # the Goose fire

Reads data/processed/fire_perimeters_shaver.geojson (built once by scripts/build_perimeters.py from the
big CAL FIRE download). These are HISTORICAL records of the final burned area, not a fire's growth
over time. Unknown values are null.
"""
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import pandas as pd

PERIMETERS_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "fire_perimeters_shaver.geojson"
LAYER_TYPE = "fire_perimeter"
DATA_KIND = "observed"
SOURCE = "CAL FIRE FRAP perimeters"
MODEL_VERSION = "m4-perimeters-0.1"


@lru_cache(maxsize=4)
def _load(path: str) -> gpd.GeoDataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Perimeter file not found: {p}. Build it with scripts/build_perimeters.py (see docs/DATA_SOURCES.md).")
    df = gpd.read_file(p)
    for col in ("alarm_date", "containment_date"):          # GeoJSON readers may turn date text into timestamps
        ts = pd.to_datetime(df[col], errors="coerce", utc=True)
        df[col] = ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ").astype(object).where(ts.notna(), None)
    return df


def reload_data() -> None:
    """Forget the cached file (use after rebuilding it)."""
    _load.cache_clear()


def _clean(value):
    """NaN / NA / NaT -> None so the JSON carries null, never NaN."""
    return None if pd.isna(value) else value


def get_perimeters(year_from: int = None, year_to: int = None, path: Path = None,
                   generated_at: str = None) -> dict:
    """Historical fire perimeters overlapping the Shaver Lake study area, as a FeatureCollection.

    year_from, year_to: keep fires from these years (both included). A fire with an unknown year is
                        left out when either bound is given.
    """
    if year_from is not None and year_to is not None and year_from > year_to:
        raise ValueError("year_from must not be after year_to")
    df = _load(str(path or PERIMETERS_PATH))
    year = pd.to_numeric(df["year"], errors="coerce")
    keep = pd.Series(True, index=df.index)
    if year_from is not None:
        keep &= year >= year_from
    if year_to is not None:
        keep &= year <= year_to
    generated_at = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    features = []
    for idx, r in df[keep].iterrows():
        yr = _clean(r["year"])
        name = _clean(r["fire_name"])
        alarm = _clean(r["alarm_date"])
        fid = f"{LAYER_TYPE}:{name or 'unnamed'}_{int(yr) if yr is not None else 'unknown'}_{idx}"
        features.append({
            "type": "Feature",
            "geometry": r.geometry.__geo_interface__,
            "properties": {
                "feature_id": fid,
                "patch_id": None,
                "layer_type": LAYER_TYPE,
                "observed_at": alarm,
                "generated_at": generated_at,
                "model_version": MODEL_VERSION,
                "source": SOURCE,
                "data_quality": "ok",
                "data_kind": DATA_KIND,
                "fire_name": name,
                "year": int(yr) if yr is not None else None,
                "alarm_date": alarm,
                "containment_date": _clean(r["containment_date"]),
                "area_ha": float(r["area_ha"]) if _clean(r["area_ha"]) is not None else None,
                "cause": _clean(r["cause"]),
                "agency": _clean(r["agency"]),
                "overlaps_study_area": True,
                "perimeter_time": _clean(r["containment_date"]) or alarm,
            },
        })
    return {"type": "FeatureCollection", "features": features}
