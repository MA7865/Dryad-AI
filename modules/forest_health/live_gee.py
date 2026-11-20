"""
live_gee.py -- M1: pulls a Sentinel-2 composite for a date window straight from
Earth Engine and returns one row per patch (same columns as the exported table).

Needs: pip install earthengine-api   and a one-time:  python -c "import ee; ee.Authenticate()"
"""
import os
import json
from datetime import date, timedelta
from pathlib import Path

import ee
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
GRID = ROOT / "data" / "grid.geojson"
PROJECT = "gen-lang-client-0751448138"   # Earth Engine project (change to yours)
S2 = "COPERNICUS/S2_SR_HARMONIZED"
_initialised = False


def init() -> None:
    global _initialised
    if _initialised:
        return
    account, key = os.getenv("EE_SERVICE_ACCOUNT"), os.getenv("EE_KEY_FILE")
    if account and key:
        ee.Initialize(ee.ServiceAccountCredentials(account, key), project=PROJECT)
    else:
        ee.Initialize(project=PROJECT)
    _initialised = True


def _grid_fc() -> ee.FeatureCollection:
    """The shared grid, built from the local file so it works for any teammate's account."""
    feats = json.loads(GRID.read_text())["features"]
    return ee.FeatureCollection([
        ee.Feature(ee.Geometry(f["geometry"], None, False),
                   {"patch_id": f["properties"]["patch_id"],
                    "row": f["properties"]["row"], "col": f["properties"]["col"]})
        for f in feats
    ])


def _mask_clouds(img):
    scl = img.select("SCL")
    m = (scl.neq(3).And(scl.neq(8)).And(scl.neq(9))
            .And(scl.neq(10)).And(scl.neq(11)))
    return img.updateMask(m)


def _add_indices(img):
    return img.addBands([
        img.normalizedDifference(["B8", "B4"]).rename("NDVI"),
        img.normalizedDifference(["B8", "B11"]).rename("NDMI"),
        img.normalizedDifference(["B8", "B12"]).rename("NBR"),
    ])


def latest_scene_date() -> str:
    """Date of the newest Sentinel-2 scene over the study area (YYYY-MM-DD)."""
    init()
    aoi = _grid_fc().geometry().bounds()
    newest = (ee.ImageCollection(S2).filterBounds(aoi)
              .filterDate((date.today() - timedelta(days=30)).isoformat(),
                          (date.today() + timedelta(days=1)).isoformat())
              .sort("system:time_start", False).first())
    return ee.Date(newest.get("system:time_start")).format("YYYY-MM-dd").getInfo()


def fetch_window_features(start: str, end: str, cloud_max: int = 60) -> pd.DataFrame:
    """One row per patch for scenes between start (inclusive) and end (exclusive)."""
    init()
    grid = _grid_fc()
    aoi = grid.geometry().bounds()

    col = (ee.ImageCollection(S2).filterBounds(aoi).filterDate(start, end)
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_max)))
    n_scenes = col.size().getInfo()
    if n_scenes == 0:
        raise RuntimeError(f"No Sentinel-2 scenes between {start} and {end}")

    masked = col.map(_mask_clouds).map(_add_indices)
    img = masked.select(["NDVI", "NDMI", "NBR"]).median()
    obs = masked.select("NDMI").count().rename("obs_count")   # clear observations per pixel
    forest = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").eq(10)
    burned = (ee.ImageCollection("MODIS/061/MCD64A1")
              .filterDate("2015-01-01", end).select("BurnDate")
              .max().unmask(0).gt(0))

    stack = (img.updateMask(forest)
             .addBands(img.select("NDMI").mask().rename("valid"))
             .addBands(forest.rename("forest_frac"))
             .addBands(burned.rename("burn_frac"))
             .addBands(obs.updateMask(forest)))

    cols = ["patch_id", "row", "col", "NDVI", "NDMI", "NBR",
            "valid", "forest_frac", "burn_frac", "obs_count"]
    out = (stack.reduceRegions(collection=grid, reducer=ee.Reducer.mean(),
                               scale=20, tileScale=4)
           .select(cols, None, False))            # drop geometry: much smaller download
    rows = [f["properties"] for f in out.getInfo()["features"]]

    df = pd.DataFrame(rows)
    df["year"] = int(end[:4])
    df["window_start"], df["window_end"] = start, end
    df.attrs["n_scenes"] = n_scenes
    return df