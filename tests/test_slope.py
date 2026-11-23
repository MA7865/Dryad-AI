"""Tests for Version 2 (slope) and terrain.py. No network: tiles are faked. Run: python -m pytest tests/test_slope.py -v"""
import numpy as np
import pytest
from shapely.geometry import Point

from modules.fire_monitoring import terrain
from modules.fire_monitoring.spread_v0 import (
    CELL_M, NEIGHBOURS, make_domain, rasterize, simulate, slope_multipliers)

IGN = (500_000, 4_100_000)
REAL = Point(*IGN).buffer(1_500)


@pytest.fixture
def domain():
    return make_domain(REAL, IGN)


def ramp_north(domain, rise_per_cell):
    """Elevation that rises toward the north (higher row numbers)."""
    rows = np.arange(domain.n_rows)[:, None] * np.ones((1, domain.n_cols))
    return rows * rise_per_cell


def test_terrarium_round_trip():
    elev = np.array([[0.0, 1.0], [1234.5, -50.25]])
    back = terrain.decode_terrarium(terrain.encode_terrarium(elev))
    assert np.allclose(back, elev, atol=1 / 256)


def test_global_pixel_known_points():
    x, y = terrain.lonlat_to_global_px(0.0, 0.0, zoom=1)
    assert x == pytest.approx(256) and y == pytest.approx(256)
    x, _ = terrain.lonlat_to_global_px(-180.0, 0.0, zoom=3)
    assert x == pytest.approx(0)


def fake_tile_fn(elev_of_global_px):
    """Tile function whose elevation is a known function of global pixel (x, y)."""
    def fn(z, tx, ty, cache_dir):
        xs = tx * terrain.TILE_PX + np.arange(terrain.TILE_PX)
        ys = ty * terrain.TILE_PX + np.arange(terrain.TILE_PX)
        gx, gy = np.meshgrid(xs, ys)
        return terrain.decode_terrarium(terrain.encode_terrarium(elev_of_global_px(gx, gy)))
    return fn


def test_get_elevation_matches_a_known_surface(domain):
    # elevation = 0.5 m per pixel going east, 2 m per pixel going south (y grows southward)
    fn = fake_tile_fn(lambda gx, gy: 1000 + 0.5 * (gx % 4096) + 2.0 * (gy % 4096) / 4)
    elev = terrain.get_elevation(domain, tile_fn=fn)
    assert elev.shape == domain.shape
    assert np.all(np.diff(elev, axis=1) > 0)            # rises toward the east
    assert np.all(np.diff(elev, axis=0) < 0)            # falls toward the north (rows go north)


def test_get_elevation_asks_for_each_tile_once(domain):
    calls = []

    def fn(z, tx, ty, cache_dir):
        calls.append((tx, ty))
        return np.full((terrain.TILE_PX, terrain.TILE_PX), 500.0)
    elev = terrain.get_elevation(domain, tile_fn=fn)
    assert np.allclose(elev, 500.0)
    assert len(calls) >= 1 and len(calls) == len(set(calls))


def test_no_slope_effect_when_b_is_zero_or_no_elevation(domain):
    assert slope_multipliers(None, 3.0) is None
    assert slope_multipliers(ramp_north(domain, 20.0), 0.0) is None


def test_slope_multiplier_is_above_one_uphill_and_below_one_downhill(domain):
    mult = slope_multipliers(ramp_north(domain, 30.0), 2.0)       # 30 m per 90 m cell = 0.33 rise/run going north
    for (dr, dc, _), m in zip(NEIGHBOURS, mult):
        interior = m[5:-5, 5:-5]
        # _shift: arrival at (r, c) comes from (r - dr, c - dc); higher row = north = uphill
        if dr == 1 and dc == 0:                                    # source one row south -> moving north -> uphill
            assert np.allclose(interior, np.exp(2.0 * 30 / CELL_M))
        if dr == -1 and dc == 0:                                   # moving south -> downhill
            assert np.allclose(interior, np.exp(-2.0 * 30 / CELL_M))
        if dr == 0:                                                # sideways on a north-facing ramp: flat
            assert np.allclose(interior, 1.0)


def test_slope_is_capped_at_45_degrees(domain):
    mult = slope_multipliers(ramp_north(domain, 900.0), 1.0)       # 10x steeper than 45 degrees
    assert max(m[5:-5, 5:-5].max() for m in mult) <= np.exp(1.0) * (1 + 1e-9)


def test_b_zero_gives_exactly_the_earlier_result(domain):
    target = int(rasterize(REAL, domain).sum())
    plain = simulate(domain, IGN, target, seed=4, wind_toward_deg=90, wind_k=1.0)
    with_zero = simulate(domain, IGN, target, seed=4, wind_toward_deg=90, wind_k=1.0,
                         elevation=ramp_north(domain, 30.0), slope_b=0.0)
    assert np.array_equal(plain, with_zero)


def test_fire_grows_uphill_faster(domain):
    target = int(rasterize(REAL, domain).sum())
    ys = []
    for seed in range(8):
        fire = simulate(domain, IGN, target, seed=seed, elevation=ramp_north(domain, 30.0), slope_b=3.0)
        rows = np.nonzero(fire)[0]
        ys.append(rows.mean() - domain.cell_of(*IGN)[0])
    assert np.mean(ys) > 3                                         # centre of the burn shifted north (uphill)


def test_wrong_elevation_shape_is_rejected(domain):
    with pytest.raises(ValueError):
        simulate(domain, IGN, 50, elevation=np.zeros((3, 3)), slope_b=1.0)


def test_slope_runs_together_with_an_hourly_wind_schedule(domain):
    fire = simulate(domain, IGN, 200, seed=1, wind_schedule=[(90, 1.0), (180, 1.0)],
                    elevation=ramp_north(domain, 20.0), slope_b=2.0)
    assert int(fire.sum()) == 200
