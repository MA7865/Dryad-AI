"""
build_summers.py -- M1: computes the June-September feature table for each summer straight
from Earth Engine (no browser export).

    python -m modules.forest_health.build_summers              # 2022 .. latest complete summer
    python -m modules.forest_health.build_summers --from 2022
Then:  python -m modules.forest_health.build_outputs
"""
import sys
from datetime import date

import pandas as pd

from . import live_gee
from .paths import CACHE, FEATURES


def main() -> None:
    first = 2022
    if "--from" in sys.argv:
        first = int(sys.argv[sys.argv.index("--from") + 1])
    today = date.today()
    last = today.year if today >= date(today.year, 10, 1) else today.year - 1

    frames = []
    for y in range(first, last + 1):
        print(f"Summer {y} ...", flush=True)
        df = live_gee.fetch_window_features(f"{y}-06-01", f"{y}-10-01")
        print(f"  scenes: {df.attrs['n_scenes']} | patches with NDVI: {int(df['NDVI'].notna().sum())}")
        frames.append(df.drop(columns=["window_start", "window_end"]))
    out = pd.concat(frames, ignore_index=True)

    # Burn status must not change from year to year: use the latest summer's burn_frac for all years.
    latest = out[out["year"] == out["year"].max()].set_index("patch_id")["burn_frac"]
    out["burn_frac"] = out["patch_id"].map(latest)

    CACHE.mkdir(parents=True, exist_ok=True)
    out.to_csv(FEATURES, index=False)
    print(f"Wrote {FEATURES} ({len(out)} rows)")


if __name__ == "__main__":
    main()