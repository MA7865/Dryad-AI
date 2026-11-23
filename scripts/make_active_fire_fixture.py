"""
make_active_fire_fixture.py -- turns FIRMS detections into contract-shaped `active_fire` GeoJSON.

Reads:   data/samples/goose_2016_firms_snpp.csv   (from fetch_goose_firms.py)
         data/grid.geojson                        (the shared 500 m grid)
Writes:  data/samples/active_fire_goose_2016.geojson   all detections
         tests/fixtures/active_fire.json                small fixture for the frontend

Run from the repo root:   python scripts/make_active_fire_fixture.py
Install once:             pip install geopandas pandas shapely
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.fire_monitoring.active_fire import detections_to_features, filter_confidence  # noqa: E402

WEST, SOUTH, EAST, NORTH = -119.50, 37.00, -119.25, 37.20   # docs/STUDY_AREA.md
SOURCE = "VIIRS_SNPP_SP"            # source the Goose CSV was downloaded from
MODEL_VERSION = "m4-firms-0.1"
FIXTURE_PER_DAY = 8                 # detections per date kept in the small fixture

COMMON = ["feature_id", "patch_id", "layer_type", "observed_at", "generated_at",
          "model_version", "source", "data_quality", "data_kind"]
M4_REQUIRED = ["detection_id", "confidence", "detection_time", "satellite_source"]
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def to_iso_utc(acq_date, acq_time) -> str:
    """FIRMS gives date '2016-08-01' and time 912 (HHMM, UTC) -> '2016-08-01T09:12:00Z'."""
    hhmm = f"{int(acq_time):04d}"
    return f"{acq_date}T{hhmm[:2]}:{hhmm[2:]}:00Z"


def build_features(csv_path: Path, grid_path: Path) -> list:
    """Same code path as get_active_fires: low-confidence dropped, features built by the module."""
    det = pd.read_csv(csv_path)
    if det.empty:
        sys.exit(f"{csv_path} has no detections.")
    det = filter_confidence(det)
    if det.empty:
        sys.exit("No detections left after the confidence filter.")
    return detections_to_features(det, SOURCE)


def validate(features: list) -> None:
    ids = set()
    for f in features:
        p = f["properties"]
        for k in COMMON + M4_REQUIRED:
            assert k in p, f"missing property {k}"
        assert p["layer_type"] == "active_fire"
        assert ISO_UTC.match(p["observed_at"]) and ISO_UTC.match(p["generated_at"]), "timestamp not ISO UTC"
        lon, lat = f["geometry"]["coordinates"]
        assert WEST <= lon <= EAST and SOUTH <= lat <= NORTH, f"outside study area: {lon}, {lat}"
        assert p["feature_id"] not in ids, "duplicate feature_id"
        ids.add(p["feature_id"])


def write_collection(features: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/samples/goose_2016_firms_snpp.csv")
    ap.add_argument("--grid", default="data/grid.geojson")
    ap.add_argument("--full-out", default="data/samples/active_fire_goose_2016.geojson")
    ap.add_argument("--fixture-out", default="tests/fixtures/active_fire.json")
    a = ap.parse_args()

    features = build_features(Path(a.csv), Path(a.grid))
    validate(features)

    # Small fixture: the first few detections from each date, so the frontend sees both days.
    by_day = {}
    for f in features:
        by_day.setdefault(f["properties"]["observed_at"][:10], []).append(f)
    fixture = [f for day in sorted(by_day) for f in by_day[day][:FIXTURE_PER_DAY]]

    write_collection(features, Path(a.full_out))
    write_collection(fixture, Path(a.fixture_out))

    no_patch = sum(f["properties"]["patch_id"] is None for f in features)
    patches = {f["properties"]["patch_id"] for f in features if f["properties"]["patch_id"]}
    print(f"Detections: {len(features)}  |  distinct patches hit: {len(patches)}  |  no patch: {no_patch}")
    for day in sorted(by_day):
        print(f"  {day}: {len(by_day[day])} detections")
    print(f"Saved {a.full_out}")
    print(f"Saved {a.fixture_out} ({len(fixture)} features)")
    print("All contract checks passed.")


if __name__ == "__main__":
    main()
