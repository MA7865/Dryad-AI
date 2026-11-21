"""
train_final.py -- M1 stage 5: trains the deployed model (Option A), measures calibration,
and writes the model card.

    python -m scripts.train_baselines     (run first: writes data/training/baseline_metrics.json)
    python -m scripts.train_final
Reads : data/training/cells_features.csv, data/training/baseline_metrics.json
Writes: models/m1_mortality_hgb.joblib, data/processed/m1_model_card.json
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from scripts.train_baselines import ENV, SAT, SEED, build, metrics

FEATS = ENV + SAT
MODEL_VERSION = "m1-mortality-hgb-v1"
MODEL_OUT = Path("models/m1_mortality_hgb.joblib")
CARD_OUT = Path("data/processed/m1_model_card.json")
BASELINES = Path("data/training/baseline_metrics.json")

FEATURE_NOTES = {
    "elev": "Elevation (m), SRTM",
    "slope": "Slope (degrees), SRTM",
    "asp_sin": "Aspect, sine component (east-west)",
    "asp_cos": "Aspect, cosine component (north-south)",
    "forest_frac": "Share of the patch that is tree cover (ESA WorldCover 2021)",
    "def_wy": "Climatic water deficit summed over the water year Oct-Sep (TerraClimate, raw units)",
    "def_wy_prev": "Same, for the previous water year",
    "pdsi_jjas": "Palmer Drought Severity Index, mean June-September (TerraClimate, raw units, scale 0.01)",
    "NDVI": "Mean NDVI of tree pixels, June-September median composite (Sentinel-2)",
    "NDMI": "Mean NDMI (canopy moisture) of tree pixels",
    "NBR": "Mean NBR of tree pixels",
    "NDVI_sd": "Spread of NDVI inside the patch (patchy dieback raises it)",
    "NDMI_sd": "Spread of NDMI inside the patch",
    "dNDVI": "NDVI minus the previous summer",
    "dNDMI": "NDMI minus the previous summer",
    "dNBR": "NBR minus the previous summer",
}

LIMITATIONS = [
    "Trained on where USFS aerial surveyors mapped tree mortality (mostly fir engraver and other bark beetles; 98% of polygons are mortality). It is not a general forest-health measure.",
    "Most of the skill comes from terrain, forest cover and climate. Satellite features add a small gain in whole-block testing and no demonstrable gain in the strict new-places-and-year test.",
    "Negatives are cells within 3 km of a survey polygon in the same year, because the survey service has no layer showing where aircraft flew. A cell with no polygon may simply not have been flown.",
    "The likelihood is relative to surveyed forest. The training sample had a much higher damage rate than the whole Sierra, so do not read it as a real-world probability.",
    "Burned patches (more than 5% burned since 2015) and patches with under 20% tree cover are not scored.",
    "Satellite features use June-September composites. The app applies the model to the latest completed summer.",
    "USFS polygons are approximate aerial sketches, some data is generalized, and the Forest Service has not assessed their accuracy.",
    "Performance at Shaver Lake is lower than the Sierra-wide figure and has no confidence interval (few cells). Terrain and climate vary less inside a small area, which may limit any such model (not verified).",
]


def new_clf():
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                          l2_regularization=1.0, random_state=SEED)


def block_auc_ci(frame, col, n_boot=300):
    rng = np.random.default_rng(SEED)
    groups = {b: g for b, g in frame.groupby("block")}
    blocks = np.array(list(groups))
    vals = []
    for _ in range(n_boot):
        s = pd.concat([groups[b] for b in rng.choice(blocks, size=len(blocks), replace=True)])
        if s["y"].nunique() == 2:
            vals.append(roc_auc_score(s["y"], s[col]))
    return [round(float(x), 3) for x in np.percentile(vals, [2.5, 97.5])]


def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    return str(o)


def main():
    d, shaver_blocks = build()
    pool = d[~d["in_shaver"]].reset_index(drop=True)          # Shaver Lake never enters training
    print(f"Training pool: {len(pool)} cell-years, {int(pool['y'].sum())} positives "
          f"({pool['y'].mean():.1%}), {pool['block'].nunique()} blocks")

    # 1) Out-of-fold predictions with whole blocks held out
    oof = np.zeros(len(pool))
    for tr, te in GroupKFold(n_splits=5).split(pool, pool["y"], pool["block"]):
        clf = new_clf().fit(pool.iloc[tr][FEATS], pool.iloc[tr]["y"])
        oof[te] = clf.predict_proba(pool.iloc[te][FEATS])[:, 1]
    pool["p"] = oof
    overall = metrics(pool["y"].to_numpy(), oof)
    overall["auc_95ci"] = block_auc_ci(pool, "p")
    by_year = {int(y): metrics(g["y"].to_numpy(), g["p"].to_numpy())
               for y, g in pool.groupby("year")}

    # 2) Bands from the out-of-fold score distribution
    c_elev, c_high = (float(x) for x in np.percentile(oof, [70, 90]))
    band = np.where(oof >= c_high, "High", np.where(oof >= c_elev, "Elevated", "Lower"))
    band_table = {}
    for b in ("High", "Elevated", "Lower"):
        m = band == b
        band_table[b] = {"n": int(m.sum()), "share_of_cells": round(float(m.mean()), 3),
                         "observed_damage_rate": round(float(pool.loc[m, "y"].mean()), 3)}

    # 3) Calibration by decile
    dec = pd.qcut(pd.Series(oof), 10, labels=False, duplicates="drop")
    calibration = (pd.DataFrame({"decile": dec, "p": oof, "y": pool["y"].to_numpy()})
                   .groupby("decile")
                   .agg(mean_predicted=("p", "mean"), observed_rate=("y", "mean"), n=("y", "size"))
                   .round(3).reset_index().to_dict("records"))

    # 4) Permutation importance on held-out blocks
    rng = np.random.default_rng(SEED)
    blocks = np.array(sorted(pool["block"].unique()))
    hold = set(rng.choice(blocks, size=int(0.2 * len(blocks)), replace=False))
    tr, te = pool[~pool["block"].isin(hold)], pool[pool["block"].isin(hold)]
    probe = new_clf().fit(tr[FEATS], tr["y"])
    pi = permutation_importance(probe, te[FEATS], te["y"], scoring="roc_auc",
                                n_repeats=5, random_state=SEED)
    importance = [{"feature": f, "auc_drop": round(float(v), 4)}
                  for f, v in sorted(zip(FEATS, pi.importances_mean), key=lambda t: -t[1])]

    # 5) Final model on the whole pool, then test it on Shaver Lake (never seen)
    final = new_clf().fit(pool[FEATS], pool["y"])
    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final, MODEL_OUT)
    sh = d[d["in_shaver"]].copy()
    sh["p"] = final.predict_proba(sh[FEATS])[:, 1]
    shaver = metrics(sh["y"].to_numpy(), sh["p"].to_numpy())

    base = json.loads(BASELINES.read_text()) if BASELINES.exists() else {}
    card = {
        "model_version": MODEL_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "algorithm": f"HistGradientBoostingClassifier (scikit-learn {sklearn.__version__})",
        "target": ("A 500 m patch is positive in a year if USFS aerial-survey MORTALITY polygons "
                   "cover at least 10% of it that year."),
        "features": FEATS,
        "feature_notes": FEATURE_NOTES,
        "training": {
            "rows": int(len(pool)), "positives": int(pool["y"].sum()),
            "years": "2021-2024", "spatial_blocks_20km": int(pool["block"].nunique()),
            "negatives": "cells within 3 km of a survey polygon of that year and under 1% covered",
            "excluded": ["burned (more than 5% since 2015)", "tree cover under 20%",
                         "fewer than 3 clear observations", "1-10% polygon coverage (ambiguous)"],
            "shaver_lake_in_training": False,
        },
        "evaluation": {
            "whole_blocks_held_out_out_of_fold_2021_2024": overall,
            "by_year_out_of_fold": by_year,
            "baseline_experiments": {
                "space_test_blocks_held_out_2021_2023": base.get("space_test_blocks_held_out_2021_2023"),
                "strict_test_new_blocks_and_2024": base.get("strict_test_new_blocks_and_2024"),
                "shaver_lake_never_seen_baseline": base.get("shaver_lake_never_seen"),
            },
            "shaver_lake_never_seen_deployed_model": shaver,
        },
        "bands": {"elevated": c_elev, "high": c_high, "table": band_table},
        "calibration_deciles": calibration,
        "permutation_importance": importance,
        "limitations": LIMITATIONS,
        "sources": ["USFS Insect and Disease Survey (damage areas, 2021-2024)",
                    "Sentinel-2 SR Harmonized (Google Earth Engine)", "ESA WorldCover v200",
                    "SRTM elevation", "MODIS MCD64A1 burned area", "TerraClimate"],
    }
    CARD_OUT.write_text(json.dumps(card, indent=2, default=_json_default))

    print("\nOut-of-fold (whole blocks held out):", overall)
    print("\nBy year:")
    for y, r in by_year.items():
        print(" ", y, r)
    print(f"\nBand cutoffs: Elevated >= {c_elev:.3f}, High >= {c_high:.3f}")
    for b, r in band_table.items():
        print(" ", b, r)
    print("\nCalibration (predicted vs observed):")
    for r in calibration:
        print(" ", r)
    print("\nTop features by AUC drop:")
    for r in importance[:8]:
        print(" ", r)
    print("\nShaver Lake, never seen:", shaver)
    print(f"\nSaved {MODEL_OUT} and {CARD_OUT}")


if __name__ == "__main__":
    main()