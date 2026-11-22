"""
model_service.py -- M1: applies the trained mortality-likelihood model to the Shaver Lake patches.
Features come live from Earth Engine with the SAME recipe as training (features_gee.cell_features).

score_patches() -> (DataFrame, meta), or None when no trained model is installed
"""
import json
import time
from datetime import date
from functools import lru_cache

import ee
import joblib
import numpy as np
import pandas as pd

from . import features_gee, live_gee
from .paths import CACHE, GRID, MODEL_CARD, MODEL_FILE

MIN_OBS = 3
CACHE_DAYS = 14      # re-fetch the completed-summer features after this long (climate data arrives late)


def available() -> bool:
    return MODEL_FILE.exists() and MODEL_CARD.exists()


@lru_cache(maxsize=1)
def load():
    return joblib.load(MODEL_FILE), json.loads(MODEL_CARD.read_text())


def model_year(today: date | None = None) -> int:
    """Latest COMPLETE summer (June-September): this year from 1 October, otherwise last year."""
    today = today or date.today()
    return today.year if today >= date(today.year, 10, 1) else today.year - 1


def _cells_fc() -> ee.FeatureCollection:
    feats = json.loads(GRID.read_text())["features"]
    return ee.FeatureCollection([
        ee.Feature(ee.Geometry(f["geometry"], None, False),
                   {"cell_id": f["properties"]["patch_id"]})
        for f in feats])


def _fetch(fc, year: int, clim_year: int) -> pd.DataFrame:
    burn_end = f"{date.today().year + 1}-01-01"
    rows = features_gee.cell_features(fc, year, burn_end, clim_year).getInfo()["features"]
    return pd.DataFrame([r["properties"] for r in rows])


def fetch_features(year: int) -> pd.DataFrame:
    """Features of one completed summer for every Shaver patch, same columns as training."""
    cache = CACHE / f"m1_model_features_{year}.csv"
    if cache.exists() and (time.time() - cache.stat().st_mtime) < CACHE_DAYS * 86400:
        return pd.read_csv(cache)
    live_gee.init()
    cc, cp = features_gee.climate_years(year)
    fc = _cells_fc()
    cur, prev = _fetch(fc, year, cc), _fetch(fc, year - 1, cp)
    for label, frame in (("this summer", cur), ("last summer", prev)):
        gone = [c for c in ("NDVI", "def_wy", "pdsi_jjas") if c not in frame.columns]
        if gone:
            raise RuntimeError(f"Earth Engine returned no values for {gone} ({label})")
    prev = prev.set_index("cell_id")
    for c in ("NDVI", "NDMI", "NBR"):
        cur[f"d{c}"] = cur[c].to_numpy() - prev[c].reindex(cur["cell_id"]).to_numpy()
    cur["def_wy_prev"] = prev["def_wy"].reindex(cur["cell_id"]).to_numpy()
    cur["NDVI_sd"] = np.sqrt((cur["NDVI_sq"] - cur["NDVI"] ** 2).clip(lower=0))
    cur["NDMI_sd"] = np.sqrt((cur["NDMI_sq"] - cur["NDMI"] ** 2).clip(lower=0))
    cur["year"] = year
    cur["climate_year"] = cc
    CACHE.mkdir(parents=True, exist_ok=True)
    cur.to_csv(cache, index=False)
    return cur


def score(df: pd.DataFrame) -> pd.DataFrame:
    """Likelihood and band per patch; patches that do not meet the training rules are not scored."""
    model, card = load()
    feats = card["features"]
    status = np.select(
        [df["burn_frac"] > 0.05,
         ~(df["forest_frac"] >= 0.2),
         df["NDVI"].isna() | df["dNDVI"].isna() | df["def_wy_prev"].isna(),
         ~(df["obs_count"] >= MIN_OBS)],
        ["burned_not_scored", "too_little_forest", "missing_data", "too_few_observations"],
        default="scored")
    out = pd.DataFrame({"patch_id": df["cell_id"].to_numpy(), "model_status": status,
                        "mortality_likelihood": np.nan, "mortality_percentile": np.nan,
                        "mortality_band": None})
    ok = status == "scored"
    if ok.any():
        p = model.predict_proba(df.loc[ok, feats])[:, 1]
        out.loc[ok, "mortality_likelihood"] = np.round(p, 3)
        out.loc[ok, "mortality_percentile"] = np.round(100 * pd.Series(p).rank(pct=True).to_numpy())
        hi, el = card["bands"]["high"], card["bands"]["elevated"]
        out.loc[ok, "mortality_band"] = np.where(p >= hi, "High", np.where(p >= el, "Elevated", "Lower"))
    return out


def score_patches():
    if not available():
        return None
    year = model_year()
    df = fetch_features(year)
    out = score(df)
    _, card = load()
    counts = {k: int(v) for k, v in out["model_status"].value_counts().items()}
    cy = int(df["climate_year"].iloc[0]) if "climate_year" in df.columns else year
    meta = {"status": "ok", "model_version": card["model_version"],
            "window": f"{year}-06-01/{year}-09-30",
            "climate_year": cy, "climate_is_latest_available": cy != year,
            "scored": counts.get("scored", 0), "statuses": counts}
    return out, meta