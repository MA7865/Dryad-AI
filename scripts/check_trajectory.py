"""
check_trajectory.py -- does a patch's multi-summer NDMI trend (relative to peers) go with USFS-mapped damage?
    python -m scripts.check_trajectory
"""
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

d = pd.read_csv("data/training/cells_features.csv", low_memory=False)
ok = (d["burn_frac"] <= 0.05) & (d["forest_frac"] >= 0.2) & d["NDMI"].notna() & ~d["in_shaver"]
u = d[ok].copy()
u["rel"] = u["NDMI"] - u.groupby("year")["NDMI"].transform("median")     # relative to same-year peers
wide = u.pivot(index="cell_id", columns="year", values="rel")

lab = d[d["year"] == 2024][["cell_id", "cover_2024", "near_2024", "block"]].drop_duplicates("cell_id")
lab["y"] = np.where(lab["cover_2024"] >= 0.10, 1, np.where((lab["cover_2024"] < 0.01) & lab["near_2024"], 0, -1))
lab = lab[lab["y"] >= 0].set_index("cell_id")


def slope(years):
    xs = np.array(years, float)
    out = {}
    for cid, row in wide[years].iterrows():
        y = row.to_numpy(float)
        m = ~np.isnan(y)
        if m.sum() >= len(years) - 1:
            out[cid] = np.polyfit(xs[m], y[m], 1)[0]
    return pd.Series(out)


rng = np.random.default_rng(0)
for name, years in (("2020-2023 (before the survey year)", [2020, 2021, 2022, 2023]),
                    ("2020-2024 (including the survey year)", [2020, 2021, 2022, 2023, 2024])):
    s = slope(years).rename("s")
    f = lab.join(s, how="inner").dropna()
    auc = roc_auc_score(f["y"], -f["s"])                       # a falling trend should flag damage
    groups = {b: g for b, g in f.groupby("block")}
    keys = np.array(list(groups))
    boots = []
    for _ in range(300):
        g = pd.concat([groups[b] for b in rng.choice(keys, len(keys), replace=True)])
        if g["y"].nunique() == 2:
            boots.append(roc_auc_score(g["y"], -g["s"]))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    print(f"Trend {name}: AUC {auc:.3f} (95% {lo:.3f}-{hi:.3f}) | cells {len(f)} | positives {int(f['y'].sum())}")