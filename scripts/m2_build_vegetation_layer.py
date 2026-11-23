
import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data" / "processed" / "vegetation"

REFERENCE = FOLDER / "vegetation_reference.geojson"
FEATURES = FOLDER / "vegetation_features.csv"
BURN_QUALITY = FOLDER / "vegetation_burn_quality.csv"
OUTPUT = FOLDER / "vegetation.geojson"

# Load reference vegetation polygons
with open(REFERENCE, encoding="utf-8") as f:
    reference = json.load(f)

# Load satellite and anomaly information
satellite = pd.read_csv(FEATURES)
burn_quality = pd.read_csv(BURN_QUALITY)

# Ensure the files have unique patch IDs
for name, df in [
    ("satellite", satellite),
    ("burn_quality", burn_quality)
]:
    if df["patch_id"].duplicated().any():
        raise ValueError(f"Duplicate patch IDs in {name}")

merged = satellite.merge(
    burn_quality,
    on="patch_id",
    how="outer",
    validate="one_to_one"
)

# Convert pandas NaN/NumPy values into JSON-safe values
def clean(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value

records = {
    row["patch_id"]: {
        key: clean(value)
        for key, value in row.items()
        if key != "patch_id"
    }
    for row in merged.to_dict("records")
}

generated_at = datetime.now(timezone.utc).isoformat()

for feature in reference["features"]:
    properties = feature["properties"]
    patch_id = properties["patch_id"]

    extra = records.get(patch_id)

    if extra is None:
        properties["data_quality"] = "missing"
        continue

    # Preserve LANDFIRE information
    reference_quality = properties.get("data_quality")

    # Add satellite, anomaly, and burn information
    properties.update(extra)

    properties["generated_at"] = generated_at
    properties["layer_type"] = "vegetation"
    properties["model_version"] = "m2-v0.1"
    properties["source"] = (
        "LANDFIRE LF2024 EVT; "
        "Sentinel-2 SR Harmonized; "
        "M1 historical summer features"
    )

    # Do not call reference classes ML predictions
    properties["prediction_kind"] = "reference_lookup"

    # Combine reference coverage with satellite eligibility
    if reference_quality == "missing":
        properties["data_quality"] = "missing"
    elif reference_quality == "partial":
        if properties["data_quality"] != "missing":
            properties["data_quality"] = "limited"

# Validate that the layer matches the shared grid
grid_path = ROOT / "data" / "grid.geojson"

with open(grid_path, encoding="utf-8") as f:
    grid = json.load(f)

expected_ids = {
    f["properties"]["patch_id"]
    for f in grid["features"]
}

actual_ids = [
    f["properties"]["patch_id"]
    for f in reference["features"]
]

assert len(actual_ids) == len(expected_ids)
assert len(set(actual_ids)) == len(actual_ids)
assert set(actual_ids) == expected_ids

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(reference, f, indent=2, allow_nan=False)

print("Vegetation layer created!")
print("Total features:", len(reference["features"]))
print("Output:", OUTPUT)
print("File size MB:", round(OUTPUT.stat().st_size / 1e6, 2))
