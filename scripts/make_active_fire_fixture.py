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
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd

WEST, SOUTH, EAST, NORTH = -119.50, 37.00, -119.25, 37.20   # docs/STUDY_AREA.md
SOURCE = "VIIRS_SNPP_SP"            # source the Goose CSV was downloaded from
MODEL_VERSION = "m4-firms-0.1"
FIXTURE_PER_DAY = 8                 # detections per date kept in the small fixture

COMMON = ["feature_id", "patch_id", "layer_type", "observed_at", "generated_at",
          "model_version", "source", "data_quality"]
M4_REQUIRED = ["detection_id", "confidence", "detection_time", "satellite_source"]
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def to_iso_utc(acq_date, acq_time) -> str:
    """FIRMS gives date '2016-08-01' and time 912 (HHMM, UTC) -> '2016-08-01T09:12:00Z'."""
    hhmm = f"{int(acq_time):04d}"
    return f"{acq_date}T{hhmm[:2]}:{hhmm[2:]}:00Z"


def build_features(csv_path: Path, grid_path: Path) -> list:
    det = pd.read_csv(csv_path)
    if det.empty:
        sys.exit(f"{csv_path} has no detections.")
    grid = gpd.read_file(grid_path)[["patch_id", "geometry"]]

    pts = gpd.GeoDataFrame(
        det, geometry=gpd.points_from_xy(det["longitude"], det["latitude"]), crs="EPSG:4326"
    )
    # Which cell is each point in? 'intersects' so points exactly on a cell edge still match;
    # if two cells match, keep the first patch_id alphabetically so the result is repeatable.
    joined = gpd.sjoin(pts, grid.sort_values("patch_id"), how="left", predicate="intersects")
    joined = joined[~joined.index.duplicated(keep="first")]

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    features = []
    for _, r in joined.sort_values(["acq_date", "acq_time", "latitude", "longitude"]).iterrows():
        observed = to_iso_utc(r["acq_date"], r["acq_time"])
        det_id = f"{SOURCE}_{observed.replace('-', '').replace(':', '')}_{r['latitude']:.5f}_{r['longitude']:.5f}"
        patch = r["patch_id"] if isinstance(r["patch_id"], str) else None
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point",
                         "coordinates": [round(float(r["longitude"]), 5), round(float(r["latitude"]), 5)]},
            "properties": {
                "feature_id": f"active_fire:{det_id}",
                "patch_id": patch,
                "layer_type": "active_fire",
                "observed_at": observed,
                "generated_at": generated_at,
                "model_version": MODEL_VERSION,
                "source": SOURCE,
                "data_quality": "good",
                "detection_id": det_id,
                "confidence": str(r["confidence"]),
                "detection_time": observed,
                "satellite_source": SOURCE,
                # extras beyond the required M4 properties (tell the team / add to DATA_DICTIONARY.md)
                "frp_mw": float(r["frp"]) if "frp" in r and pd.notna(r["frp"]) else None,
                "day_night": str(r["daynight"]) if "daynight" in r else None,
            },
        })
    return features


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
