"""paths.py -- every M1 file location in one place."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

GRID = ROOT / "data" / "grid.geojson"                      # shared grid (in Git)
CONFIG = ROOT / "data" / "processed"                       # small settings (in Git)
BOUNDS_FILE = CONFIG / "m1_reference_bounds.json"
SAMPLE = ROOT / "data" / "samples" / "forest_health_sample.geojson"   # tiny example (in Git)

CACHE = ROOT / "data" / "cache" / "forest_health"          # generated, NOT in Git
FEATURES = ROOT / "data" / "processed" / "m1_features_summers.csv"   # frozen input (in Git)
LATEST = CACHE / "m1_forest_health_latest.geojson"
HISTORY = CACHE / "m1_patch_history.json"
LIVE = CACHE / "m1_forest_health_live.geojson"
LIVE_META = CACHE / "m1_live_meta.json"