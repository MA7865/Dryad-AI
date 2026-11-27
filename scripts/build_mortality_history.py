"""
build_mortality_history.py -- mortality likelihood for every Shaver Lake patch for each summer 2022-latest.
Summers 2022-2024 come from the training table (Shaver rows); later summers are computed from Earth Engine.
    python -m scripts.build_mortality_history
Writes data/processed/m1_mortality_history.json (small; committed so teammates do not need the training data)
"""
import json

import numpy as np
import pandas as pd

from modules.forest_health import model_service as ms
from modules.forest_health.paths import MORTALITY_HISTORY

TRAIN = "data/training/cells_features.csv"


def from_training() -> pd.DataFrame:
    d = pd.read_csv(TRAIN, low_memory=False)
    d = d[d["in_shaver"]].sort_values(["patch_id", "year"]).copy()
    g = d.groupby("patch_id")
    for c in ("NDVI", "NDMI", "NBR"):
        d[f"d{c}"] = d[c] - g[c].shift(1)
    d["def_wy_prev"] = g["def_wy"].shift(1)
    d["cell_id"] = d["patch_id"]
    d["climate_year"] = d["year"]
    return d[d["year"].between(2022, 2024)]


def main() -> None:
    frames = [from_training()]
    for y in range(2025, ms.model_year() + 1):
        f = ms.fetch_features(y)
        if "climate_year" not in f.columns:
            f["climate_year"] = y
        frames.append(f)
    allf = pd.concat(frames, ignore_index=True, sort=False)
    years = sorted(int(y) for y in allf["year"].unique())
    ids = sorted(allf["cell_id"].unique())
    out = {pid: {"likelihood": [None] * len(years), "percentile": [None] * len(years)} for pid in ids}
    climate = {}
    for i, y in enumerate(years):
        sub = allf[allf["year"] == y].reset_index(drop=True)
        s = ms.score(sub)
        climate[y] = int(sub["climate_year"].iloc[0])
        for pid, p, pc, st in zip(s["patch_id"], s["mortality_likelihood"],
                                  s["mortality_percentile"], s["model_status"]):
            if st == "scored":
                out[pid]["likelihood"][i] = float(p)
                out[pid]["percentile"][i] = float(pc)
        vals = [v["likelihood"][i] for v in out.values() if v["likelihood"][i] is not None]
        print(f"{y}: scored {len(vals)}, mean likelihood {np.mean(vals):.3f}, max {np.max(vals):.3f}, "
              f"climate year {climate[y]}")
    MORTALITY_HISTORY.write_text(json.dumps({"years": years, "climate_year": climate, "patches": out},
                                            separators=(",", ":")))
    print("Wrote", MORTALITY_HISTORY)


if __name__ == "__main__":
    main()