"""
build_seasonal_history.py -- OPTIONAL: condition index for autumn, winter and spring windows 2022-latest
(summers already exist). Each season is scored against unburned patches of the SAME season (pooled over
years), so compare the same season across years. Resumable.
    python -m scripts.build_seasonal_history
Writes data/processed/m1_seasonal_history.json
"""
import json
from datetime import date

import pandas as pd

from modules.forest_health import live_gee
from modules.forest_health.paths import CACHE, SEASONAL_HISTORY
from modules.forest_health.scoring import score_table

SEASONS = {   # season: (start month-day, start-year offset, end month-day, end-year offset, label)
    "autumn": ("10-01", 0, "12-01", 0, "Autumn {y} (Oct-Nov)"),
    "winter": ("12-01", -1, "03-01", 0, "Winter {y} (Dec-Feb)"),
    "spring": ("03-01", 0, "06-01", 0, "Spring {y} (Mar-May)"),
}
FIRST = 2022
MIN_OBS = 3


def window(y, season):
    sm, so, em, eo, label = SEASONS[season]
    return f"{y + so}-{sm}", f"{y + eo}-{em}", label.format(y=y)


def main() -> None:
    today = date.today()
    meta, tables = [], []
    for season in SEASONS:
        frames = []
        for y in range(FIRST, today.year + 1):
            start, end, label = window(y, season)
            if date.fromisoformat(end) > today:
                continue                                   # only complete seasons
            cache = CACHE / "seasonal" / f"{season}_{y}.csv"
            if cache.exists():
                df = pd.read_csv(cache)
            else:
                print(f"fetching {season} {y}: {start} to {end}", flush=True)
                df = live_gee.fetch_window_features(start, end)
                df["year"] = y
                cache.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(cache, index=False)
            df["frame_id"] = f"{y}-{season}"
            frames.append(df)
            meta.append({"id": f"{y}-{season}", "season": season, "year": y,
                         "label": label, "window": [start, end]})
        if not frames:
            continue
        scored, _, _ = score_table(pd.concat(frames, ignore_index=True))
        weak = (scored["data_quality"] == "good") & (scored["obs_count"].fillna(0) < MIN_OBS)
        scored.loc[weak, "data_quality"] = "limited"
        tables.append(scored)

    S = pd.concat(tables, ignore_index=True)
    ids = [m["id"] for m in meta]
    pos = {fid: i for i, fid in enumerate(ids)}
    patches = {}
    for pid, g in S.groupby("patch_id"):
        arr = {k: [None] * len(ids) for k in ("health_index", "health_band", "ndvi", "ndmi", "data_quality")}
        for r in g.itertuples():
            i = pos[r.frame_id]
            arr["health_index"][i] = None if pd.isna(r.health_index) else int(round(r.health_index))
            arr["health_band"][i] = r.health_band
            arr["ndvi"][i] = None if pd.isna(r.ndvi) else round(float(r.ndvi), 3)
            arr["ndmi"][i] = None if pd.isna(r.ndmi) else round(float(r.ndmi), 3)
            arr["data_quality"][i] = r.data_quality
        patches[pid] = arr
    SEASONAL_HISTORY.write_text(json.dumps({"frames": meta, "patches": patches}, separators=(",", ":")))
    print(f"Wrote {SEASONAL_HISTORY}: {len(ids)} frames, {len(patches)} patches")
    print(S.groupby("frame_id")["health_band"].value_counts().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()