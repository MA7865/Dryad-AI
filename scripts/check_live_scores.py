"""
check_live_scores.py -- are the live Shaver scores in a sensible range?
    python -m scripts.check_live_scores
Scores the same Shaver patches for summer 2024 and for the latest completed summer,
both through the live code path (needs both files in data/cache/forest_health).
"""
import json

import pandas as pd

from modules.forest_health import model_service as ms
from modules.forest_health.paths import CACHE, MODEL_CARD

cut = json.loads(MODEL_CARD.read_text())["bands"]["elevated"]
for y in (2024, ms.model_year()):
    df = pd.read_csv(CACHE / f"m1_model_features_{y}.csv")
    s = ms.score(df)
    p = s.loc[s["model_status"] == "scored", "mortality_likelihood"]
    print(f"\nSummer {y} (climate year {int(df['climate_year'].iloc[0])}): {len(p)} patches scored")
    print(p.describe(percentiles=[0.5, 0.9]).round(3).to_string())
    print(f"share at or above the Elevated cutoff ({cut:.3f}):", round(float((p >= cut).mean()), 3))