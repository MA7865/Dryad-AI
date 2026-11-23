import json
from pathlib import Path

import pytest

from modules.fire_monitoring import simulate_fire_spread

FIXTURE = Path(__file__).parent / "fixtures" / "fire_spread.json"
START = (-119.4987, 37.0140)          # inside the Goose perimeter, near its western tip
REQUIRED = {"feature_id", "patch_id", "layer_type", "observed_at", "generated_at",
            "model_version", "source", "data_quality", "data_kind", "simulation_step", "perimeter_time"}


def run(**kw):
    args = dict(ignition=START, target_area_km2=9.07, wind_dir_deg=272, wind_k=2.0, seed=0,
                generated_at="2026-11-18T00:00:00Z")
    args.update(kw)
    return simulate_fire_spread(**args)


def test_collection_shape_and_required_fields():
    fc = run()
    assert fc["type"] == "FeatureCollection" and fc["features"]
    for f in fc["features"]:
        assert REQUIRED <= set(f["properties"])
        assert f["properties"]["layer_type"] == "fire_spread"
        assert f["properties"]["data_kind"] == "simulated"
        assert f["properties"]["perimeter_time"] is None
        assert f["geometry"]["type"] == "Polygon"


def test_patch_ids_unique_and_exist_in_grid():
    from modules.fire_monitoring.active_fire import load_grid
    ids = [f["properties"]["patch_id"] for f in run()["features"]]
    assert len(ids) == len(set(ids))
    assert set(ids) <= set(load_grid()["patch_id"])


def test_same_seed_same_output_different_seed_differs():
    assert run() == run()
    assert run() != run(seed=1)


def test_ignition_patch_is_step_zero_and_steps_nonnegative():
    steps = [f["properties"]["simulation_step"] for f in run()["features"]]
    assert min(steps) == 0 and all(s >= 0 for s in steps)


def test_burned_fraction_between_zero_and_one():
    assert all(0 < f["properties"]["burned_fraction"] <= 1 for f in run()["features"])


def test_bigger_fire_touches_more_patches():
    assert len(run(target_area_km2=3.0)["features"]) < len(run(target_area_km2=9.07)["features"])


def test_ignition_outside_study_area_raises():
    with pytest.raises(ValueError):
        run(ignition=(-120.0, 37.1))


def test_nonpositive_area_raises():
    with pytest.raises(ValueError):
        run(target_area_km2=0)


def test_matches_saved_fixture():
    assert FIXTURE.exists(), "run scripts/make_fire_spread_fixture.py"
    assert json.loads(json.dumps(run())) == json.loads(FIXTURE.read_text())


def test_wind_from_west_spreads_east_not_west():
    """Team convention: wind_dir_deg is where the wind comes FROM. From the west -> fire moves east."""
    fc = run(ignition=(-119.375, 37.10), wind_dir_deg=270, wind_k=3.0, target_area_km2=3.0)
    import statistics
    ign = [f for f in fc["features"] if f["properties"]["simulation_step"] == 0][0]
    ign_col = int(ign["properties"]["patch_id"].split("_c")[1])
    cols = [int(f["properties"]["patch_id"].split("_c")[1]) for f in fc["features"]]
    assert statistics.mean(cols) > ign_col


def test_wind_from_east_spreads_west():
    fc = run(ignition=(-119.375, 37.10), wind_dir_deg=90, wind_k=3.0, target_area_km2=3.0)
    import statistics
    ign = [f for f in fc["features"] if f["properties"]["simulation_step"] == 0][0]
    ign_col = int(ign["properties"]["patch_id"].split("_c")[1])
    cols = [int(f["properties"]["patch_id"].split("_c")[1]) for f in fc["features"]]
    assert statistics.mean(cols) < ign_col
