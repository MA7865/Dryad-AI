"""
check_shaver_calibration.py -- at Shaver Lake, do predicted likelihoods match observed damage rates?
    python -m scripts.check_shaver_calibration
"""
import json

import joblib
import pandas as pd

from modules.forest_health.paths import MODEL_CARD, MODEL_FILE
from scripts.train_baselines import build

card = json.loads(MODEL_CARD.read_text())
model = joblib.load(MODEL_FILE)
d, _ = build()
sh = d[d["in_shaver"]].copy()
sh["p"] = model.predict_proba(sh[card["features"]])[:, 1]
print(f"Labelled Shaver Lake patch-years: {len(sh)} | damaged {int(sh['y'].sum())} ({sh['y'].mean():.1%})")
print(f"Mean predicted likelihood: {sh['p'].mean():.3f} | observed damage rate: {sh['y'].mean():.3f}")
sh["third"] = pd.qcut(sh["p"], 3, labels=["lowest third", "middle third", "highest third"])
print(sh.groupby("third", observed=True).agg(
    patches=("y", "size"), mean_predicted=("p", "mean"), observed_rate=("y", "mean")).round(3))
print("\nBy year:")
print(sh.groupby("year").agg(
    patches=("y", "size"), mean_predicted=("p", "mean"), observed_rate=("y", "mean")).round(3))