"""live_check.py -- fetches the latest 30 days from Earth Engine and prints a summary."""
from datetime import date, timedelta

from modules.forest_health import live_gee

newest = live_gee.latest_scene_date()
end = (date.fromisoformat(newest) + timedelta(days=1)).isoformat()
start = (date.fromisoformat(newest) - timedelta(days=29)).isoformat()
print("Newest scene:", newest, "| window:", start, "to", end)

df = live_gee.fetch_window_features(start, end)
print("Scenes in window:", df.attrs["n_scenes"], "| patches:", len(df))
print("Patches with NDVI:", int(df["NDVI"].notna().sum()))
print("Mean valid share (cloud/snow-free):", round(df["valid"].mean(), 2))
print(df[["NDVI", "NDMI", "NBR"]].describe().round(3))