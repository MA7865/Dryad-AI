"""
check_parity.py -- do features computed through the live code path match the training table?
    python -m scripts.check_parity
"""
import pandas as pd

from modules.forest_health import model_service as ms

live24 = ms.fetch_features(2024)           # recomputed through the live code path (1-3 minutes)
train = pd.read_csv("data/training/cells_features.csv", low_memory=False)
tr24 = train[(train["year"] == 2024) & train["in_shaver"]]
m = live24.merge(tr24, left_on="cell_id", right_on="patch_id", suffixes=("_live", "_train"))
print("patches compared:", len(m))

static = ["elev", "slope", "asp_sin", "asp_cos", "forest_frac", "def_wy", "pdsi_jjas"]
spectral = ["NDVI", "NDMI", "NBR", "NDVI_sd", "NDMI_sd", "obs_count"]
bad = []
for c in static + spectral:
    dd = (m[c + "_live"] - m[c + "_train"]).abs()
    print(f"{c:12s} mean {dd.mean():.5f}  max {dd.max():.5f}")
    if c in static and dd.max() > 1e-3:
        bad.append(c)
print("\nPARITY OK" if not bad else f"\nCHECK THESE (should match almost exactly): {bad}")