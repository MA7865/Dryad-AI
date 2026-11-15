"""
scoring.py -- M1: turns the GEE feature table into per-patch condition scores.

Input : DataFrame with patch_id, year, NDVI, NDMI, forest_frac, valid, burn_frac
Output: (scored, trends, bounds)
  scored : one row per patch and year (health_index, health_band, ...)
  trends : one row per patch (trend_slope, trend_label)
  bounds : the NDVI/NDMI values that map to 0 and 100 (save these so
           scores stay comparable when new years are added)
"""
import numpy as np
import pandas as pd

# ---- Team-adjustable settings ---------------------------------------------
UNBURNED_MAX = 0.05      # burn_frac below this = unburned (reference group)
BURNED_MIN = 0.50        # burn_frac above this = mostly burned
MIN_FOREST_FRAC = 0.20   # below this a patch has too little forest to score
LOW_PCT, HIGH_PCT = 5, 95  # reference percentiles that map to 0 and 100
BAND_PCTS = (10, 30)     # reference percentiles: below the first = High stress, below the second = Moderate stress
TREND_STEP = 1.5         # points per year (relative to peers) to call a trend
TREND_YEARS = 5          # use the latest N summers
# ----------------------------------------------------------------------------


def _reference_mask(d: pd.DataFrame) -> pd.Series:
    return (
        (d["burn_frac"] < UNBURNED_MAX)
        & (d["forest_frac"] >= MIN_FOREST_FRAC)
        & d["ndvi"].notna()
        & d["ndmi"].notna()
    )


def reference_bounds(d: pd.DataFrame) -> dict:
    ref = d[_reference_mask(d)]
    return {
        name: (float(np.percentile(ref[name], LOW_PCT)),
               float(np.percentile(ref[name], HIGH_PCT)))
        for name in ("ndvi", "ndmi")
    }


def _scale(series: pd.Series, lo: float, hi: float) -> pd.Series:
    return ((series - lo) / (hi - lo)).clip(0, 1)


def _band(health_index, burn_status, cutoffs) -> str:
    if pd.isna(health_index):
        return "Not scored"
    if burn_status == "mostly_burned":
        return "Post-fire recovery"
    high_stress_below, moderate_below = cutoffs
    if health_index < high_stress_below:
        return "High stress"
    if health_index < moderate_below:
        return "Moderate stress"
    return "Healthy"


def _trend_label(slope, burn_status) -> str:
    if pd.isna(slope):
        return "Not enough data"
    if slope >= TREND_STEP:
        return "Recovering" if burn_status == "mostly_burned" else "Improving vs peers"
    if slope <= -TREND_STEP:
        return "Declining vs peers"
    return "Stable vs peers"


def score_table(df: pd.DataFrame, bounds: dict | None = None):
    d = df.rename(columns={"NDVI": "ndvi", "NDMI": "ndmi", "NBR": "nbr"}).copy()
    bounds = bounds or reference_bounds(d)

    scorable = (
        d["ndvi"].notna() & d["ndmi"].notna() & (d["forest_frac"] >= MIN_FOREST_FRAC)
    )
    s = 0.5 * _scale(d["ndvi"], *bounds["ndvi"]) + 0.5 * _scale(d["ndmi"], *bounds["ndmi"])
    d["health_index"] = (100 * s).round().where(scorable)
    if "band_cutoffs" not in bounds:
        ref_hi = d.loc[_reference_mask(d), "health_index"].dropna()
        bounds["band_cutoffs"] = tuple(float(np.percentile(ref_hi, p)) for p in BAND_PCTS)

    d["burn_status"] = pd.cut(
        d["burn_frac"], bins=[-0.01, UNBURNED_MAX, BURNED_MIN, 1.0],
        labels=["unburned", "partial", "mostly_burned"]).astype(str)
    d["health_band"] = [_band(h, b, bounds["band_cutoffs"])
                        for h, b in zip(d["health_index"], d["burn_status"])]

    d["data_quality"] = np.select(
        [~scorable, (d["valid"] < 0.9) | (d["forest_frac"] < 0.5)],
        ["not_scored", "limited"], default="good")

    # Peer-relative score: each patch minus the unburned median of the same year
    ref_median = d[_reference_mask(d)].groupby("year")["health_index"].median()
    d["peer_rel"] = d["health_index"] - d["year"].map(ref_median)

    # Trajectory: slope of peer_rel over the latest TREND_YEARS summers
    years = sorted(d["year"].unique())[-TREND_YEARS:]
    wide = d[d["year"].isin(years)].pivot(index="patch_id", columns="year", values="peer_rel")
    xs = np.array(years, dtype=float)
    rows = []
    for pid, r in wide.iterrows():
        y = r.to_numpy(dtype=float)
        ok = ~np.isnan(y)
        slope = float(np.polyfit(xs[ok], y[ok], 1)[0]) if ok.sum() >= 4 else np.nan
        rows.append((pid, slope, int(ok.sum())))
    trends = pd.DataFrame(rows, columns=["patch_id", "trend_slope", "years_used"])

    burn_by_patch = d.groupby("patch_id")["burn_status"].first()
    trends["burn_status"] = trends["patch_id"].map(burn_by_patch)
    trends["trend_label"] = [_trend_label(s_, b) for s_, b in
                             zip(trends["trend_slope"], trends["burn_status"])]
    return d, trends, bounds