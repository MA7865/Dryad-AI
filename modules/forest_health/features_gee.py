"""
features_gee.py -- the single definition of M1's satellite, terrain and climate features.
Used for training and for live scoring, so a model never sees features computed one way in
training and another way in serving.
"""
import math
from datetime import datetime, timezone

import ee

S2 = "COPERNICUS/S2_SR_HARMONIZED"
TERRACLIMATE = "IDAHO_EPSCOR/TERRACLIMATE"
STATIC = ["forest_frac", "burn_frac", "elev", "slope", "asp_sin", "asp_cos"]
YEARLY = ["NDVI", "NDMI", "NBR", "NDVI_sq", "NDMI_sq", "obs_count", "def_wy", "pdsi_jjas"]


def mask_clouds(img):
    scl = img.select("SCL")
    m = (scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11)))
    return img.updateMask(m)


def add_indices(img):
    return img.addBands([
        img.normalizedDifference(["B8", "B4"]).rename("NDVI"),
        img.normalizedDifference(["B8", "B11"]).rename("NDMI"),
        img.normalizedDifference(["B8", "B12"]).rename("NBR"),
    ])


def static_stack(burn_end: str = "2025-01-01"):
    """Features that do not change with the summer: tree cover, burn history, terrain."""
    forest = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").eq(10)
    burned = (ee.ImageCollection("MODIS/061/MCD64A1")
              .filterDate("2015-01-01", burn_end)
              .select("BurnDate").max().unmask(0).gt(0))
    terrain = ee.Terrain.products(ee.Image("USGS/SRTMGL1_003"))
    asp = terrain.select("aspect").multiply(math.pi / 180)
    stack = (forest.rename("forest_frac")
             .addBands(burned.rename("burn_frac"))
             .addBands(terrain.select("elevation").rename("elev"))
             .addBands(terrain.select("slope"))
             .addBands(asp.sin().rename("asp_sin"))
             .addBands(asp.cos().rename("asp_cos")))
    return stack, forest


def latest_climate_year() -> int:
    """Latest year whose water year (Oct-Sep) is complete in TerraClimate (it lags real time)."""
    ms = ee.ImageCollection(TERRACLIMATE).aggregate_max("system:time_start").getInfo()
    last = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return last.year if last.month >= 9 else last.year - 1


def climate_years(year: int):
    """(current, previous) climate years for a summer. Falls back to the latest data TerraClimate has."""
    shift = max(0, year - latest_climate_year())
    return year - shift, year - 1 - shift


def year_stack(year: int, region, forest, clim_year: int | None = None):
    """
    June-September features of one year, on tree pixels only.
    clim_year: year whose climate is used (default: the same year; the live pipeline passes the
    latest year TerraClimate has).
    """
    cy = clim_year or year
    col = (ee.ImageCollection(S2).filterBounds(region)
           .filterDate(f"{year}-06-01", f"{year}-10-01")
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 60))
           .map(mask_clouds).map(add_indices))
    idx = col.select(["NDVI", "NDMI", "NBR"]).median()
    obs = col.select("NDMI").count().rename("obs_count")
    sq = idx.select(["NDVI", "NDMI"]).pow(2).rename(["NDVI_sq", "NDMI_sq"])   # for the spread
    tc = ee.ImageCollection(TERRACLIMATE)
    def_wy = (tc.filterDate(f"{cy - 1}-10-01", f"{cy}-10-01")
              .select("def").sum().rename("def_wy"))
    pdsi = (tc.filterDate(f"{cy}-06-01", f"{cy}-10-01")
            .select("pdsi").mean().rename("pdsi_jjas"))
    return (idx.updateMask(forest)
            .addBands(sq.updateMask(forest))
            .addBands(obs.updateMask(forest))
            .addBands(def_wy).addBands(pdsi))


def cell_features(fc, year: int, burn_end: str = "2025-01-01", clim_year: int | None = None):
    """
    One row per cell in `fc` (each feature needs a "cell_id" property): static + summer features.
    NOTE: the FIRST band (forest_frac) fixes the sampling grid used by reduceRegions. Do not reorder.
    """
    static, forest = static_stack(burn_end)
    stack = static.addBands(year_stack(year, fc.geometry().bounds(), forest, clim_year))
    return (stack.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=20, tileScale=4)
            .select(["cell_id"] + STATIC + YEARLY, None, False))