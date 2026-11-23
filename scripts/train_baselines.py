"""
train_baselines.py -- M1 stage 4: environment-only vs Option A (environment + satellite).

    python scripts/train_baselines.py
Reads : data/training/cells_features.csv
Writes: data/training/baseline_metrics.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold

DATA = Path("data/training/cells_features.csv")
OUT = Path("data/training/baseline_metrics.json")
SEED = 0
POS, NEG = 0.10, 0.01        # polygon cover: >= POS is positive; < NEG in the surveyed area is negative
YEARS = [2021, 2022, 2023, 2024]

ENV = ["elev", "slope", "asp_sin", "asp_cos", "forest_frac", "def_wy", "def_wy_prev", "pdsi_jjas"]
SAT = ["NDVI", "NDMI", "NBR", "NDVI_sd", "NDMI_sd", "dNDVI", "dNDMI", "dNBR"]
MODELS = {"1_environment_only": ENV, "2_option_A": ENV + SAT}


def build():
    raw = pd.read_csv(DATA, low_memory=False)
    shaver_blocks = set(raw.loc[raw["in_shaver"], "block"])
    d = raw.sort_values(["cell_id", "year"]).copy()
    g = d.groupby("cell_id")
    for c, new in (("NDVI", "dNDVI"), ("NDMI", "dNDMI"), ("NBR", "dNBR")):
        d[new] = d[c] - g[c].shift(1)
    d["def_wy_prev"] = g["def_wy"].shift(1)
    d = d[d["year"].isin(YEARS)].copy()

    d["cover"], d["near"] = np.nan, False
    for y in YEARS:
        m = d["year"] == y
        d.loc[m, "cover"] = d.loc[m, f"cover_{y}"]
        d.loc[m, "near"] = d.loc[m, f"near_{y}"]
    d["y"] = np.where(d["cover"] >= POS, 1, np.where((d["cover"] < NEG) & d["near"], 0, -1))
    d = d[(d["y"] >= 0) & (d["burn_frac"] <= 0.05) & (d["forest_frac"] >= 0.2)
          & d["NDVI"].notna() & (d["obs_count"] >= 3) & d["dNDVI"].notna()].reset_index(drop=True)
    return d, shaver_blocks


def fit_predict(train, test, feats):
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                         l2_regularization=1.0, random_state=SEED)
    clf.fit(train[feats], train["y"])
    return clf.predict_proba(test[feats])[:, 1]


def metrics(y, p):
    k = max(1, int(0.10 * len(y)))
    top = np.argsort(-p)[:k]
    return {"n": int(len(y)), "positives": int(y.sum()), "base_rate": round(float(y.mean()), 3),
            "auc": round(float(roc_auc_score(y, p)), 3),
            "pr_auc": round(float(average_precision_score(y, p)), 3),
            "precision_top10pct": round(float(y[top].mean()), 3)}


def block_boot(frame, cols, n_boot=300):
    """95% intervals from resampling whole blocks. Returns {col: (lo, hi)} and the (A - env) AUC difference."""
    rng = np.random.default_rng(SEED)
    groups = {b: g for b, g in frame.groupby("block")}
    blocks = np.array(list(groups))
    auc = {c: [] for c in cols}
    diff = []
    for _ in range(n_boot):
        s = pd.concat([groups[b] for b in rng.choice(blocks, size=len(blocks), replace=True)])
        if s["y"].nunique() < 2:
            continue
        a = {c: roc_auc_score(s["y"], s[c]) for c in cols}
        for c in cols:
            auc[c].append(a[c])
        diff.append(a[cols[1]] - a[cols[0]])
    ci = {c: tuple(np.round(np.percentile(v, [2.5, 97.5]), 3)) for c, v in auc.items()}
    return ci, tuple(np.round(np.percentile(diff, [2.5, 97.5]), 3))


def report(name, frame, results):
    cols = [f"p_{m}" for m in MODELS]
    ci, dci = block_boot(frame, cols) if frame["block"].nunique() > 5 else ({}, None)
    print(f"\n=== {name} ===")
    results[name] = {}
    for m, c in zip(MODELS, cols):
        r = metrics(frame["y"].to_numpy(), frame[c].to_numpy())
        if c in ci:
            r["auc_95ci"] = list(ci[c])
        results[name][m] = r
        print(f"{m:22s}", r)
    if dci:
        results[name]["auc_gain_A_over_env_95ci"] = list(dci)
        print("AUC gain of Option A over environment-only, 95% interval:", dci)


def main():
    d, shaver_blocks = build()
    print(f"Labelled cell-years: {len(d)} | positives {int(d['y'].sum())} ({d['y'].mean():.1%})")
    print(d.groupby("year")["y"].agg(["size", "sum"]).rename(columns={"size": "cells", "sum": "positives"}))
    results = {}

    # 1) Space test: hold out whole 20 km blocks (2021-2023, not Shaver)
    a = d[(d["year"] <= 2023) & ~d["in_shaver"]].reset_index(drop=True)
    for m, feats in MODELS.items():
        p = np.zeros(len(a))
        for tr, te in GroupKFold(n_splits=5).split(a, a["y"], a["block"]):
            p[te] = fit_predict(a.iloc[tr], a.iloc[te], feats)
        a[f"p_{m}"] = p
    report("space_test_blocks_held_out_2021_2023", a, results)

    # 2) Strict test: new blocks AND new year
    rng = np.random.default_rng(SEED)
    blocks = sorted(set(d["block"]) - shaver_blocks)
    hold = set(rng.choice(blocks, size=int(0.2 * len(blocks)), replace=False))
    tr = d[(d["year"] <= 2023) & ~d["block"].isin(hold | shaver_blocks) & ~d["in_shaver"]]
    te = d[(d["year"] == 2024) & d["block"].isin(hold)].copy()
    for m, feats in MODELS.items():
        te[f"p_{m}"] = fit_predict(tr, te, feats)
    report("strict_test_new_blocks_and_2024", te, results)

    # 3) Shaver Lake: never seen in training
    tr = d[(d["year"] <= 2023) & ~d["block"].isin(shaver_blocks) & ~d["in_shaver"]]
    sh = d[d["in_shaver"]].copy()
    for m, feats in MODELS.items():
        sh[f"p_{m}"] = fit_predict(tr, sh, feats)
    report("shaver_lake_never_seen", sh, results)

    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nSaved {OUT}")


if __name__ == "__main__":
    main()