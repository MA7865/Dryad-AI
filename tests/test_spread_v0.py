"""Tests for the Version 0 spread prototype. Run: python -m pytest tests/test_spread_v0.py -v"""
import numpy as np
import pytest
from shapely.geometry import Point

from modules.fire_monitoring.spread_v0 import (
    CELL_M, circle_baseline, iou, make_domain, rasterize, simulate, snap_into_perimeter, touches_edge,
)

REAL = Point(500_000, 4_100_000).buffer(1_500)       # a round 'real fire', radius 1.5 km
IGNITION = (500_000, 4_100_000)


@pytest.fixture
def domain():
    return make_domain(REAL, IGNITION)


def test_grid_is_aligned_to_90_m_so_it_lines_up_with_30_m_data(domain):
    assert domain.x0 % CELL_M == 0 and domain.y0 % CELL_M == 0
    assert CELL_M % 30 == 0


def test_domain_contains_the_fire_and_the_ignition_point(domain):
    assert rasterize(REAL, domain).sum() > 0
    domain.cell_of(*IGNITION)                         # raises if outside


def test_ignition_outside_domain_is_rejected(domain):
    with pytest.raises(ValueError):
        domain.cell_of(0, 0)


def test_simulation_burns_exactly_the_target_area(domain):
    target = int(rasterize(REAL, domain).sum())
    assert int(simulate(domain, IGNITION, target, seed=1).sum()) == target


def test_same_seed_same_fire_different_seed_different_fire(domain):
    target = int(rasterize(REAL, domain).sum())
    a, b, c = (simulate(domain, IGNITION, target, seed=s) for s in (1, 1, 2))
    assert np.array_equal(a, b) and not np.array_equal(a, c)


def _connected_cells(fire, start):
    """Count the burned cells reachable from `start` through the 8 neighbours (plain Python)."""
    from collections import deque
    seen, queue = {start}, deque([start])
    while queue:
        r, c = queue.popleft()
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                n = (r + dr, c + dc)
                if (0 <= n[0] < fire.shape[0] and 0 <= n[1] < fire.shape[1]
                        and fire[n] and n not in seen):
                    seen.add(n)
                    queue.append(n)
    return len(seen)


def test_fire_contains_ignition_cell_and_is_one_connected_blob(domain):
    fire = simulate(domain, IGNITION, 500, seed=3)
    r, c = domain.cell_of(*IGNITION)
    assert fire[r, c]
    assert _connected_cells(fire, (r, c)) == int(fire.sum())


def test_circle_baseline_has_the_requested_area(domain):
    assert int(circle_baseline(domain, IGNITION, 700).sum()) == 700


def test_iou_extremes():
    a = np.array([[1, 1, 0, 0]], dtype=bool)
    assert iou(a, a) == 1.0
    assert iou(a, ~a) == 0.0
    empty = np.zeros((1, 4), dtype=bool)
    assert iou(empty, empty) == 0.0                     # empty vs empty: no crash, score 0


def test_started_in_the_right_place_the_blob_matches_a_round_fire_well(domain):
    real = rasterize(REAL, domain)
    scores = [iou(simulate(domain, IGNITION, int(real.sum()), seed=s), real) for s in range(10)]
    assert np.mean(scores) > 0.8


def test_started_far_from_the_real_fire_the_score_is_low(domain):
    real = rasterize(REAL, domain)
    far = (IGNITION[0] + 1_400, IGNITION[1])
    scores = [iou(simulate(domain, far, int(real.sum()), seed=s), real) for s in range(5)]
    assert np.mean(scores) < 0.8


def test_edge_touching_is_detected():
    fire = np.zeros((5, 5), dtype=bool)
    fire[2, 2] = True
    assert not touches_edge(fire)
    fire[0, 3] = True
    assert touches_edge(fire)


def test_a_big_enough_margin_keeps_the_fire_off_the_edge():
    import math
    target = 1119
    radius = math.sqrt(target * 90 * 90 / math.pi)
    domain = make_domain(Point(500_000, 4_100_000).buffer(1_000), IGNITION, margin=radius + 500)
    assert not touches_edge(simulate(domain, IGNITION, target, seed=4))


def test_snap_moves_an_outside_point_just_inside_and_leaves_inside_points_alone():
    from shapely.geometry import Point
    outside = (REAL.centroid.x - 2_200, REAL.centroid.y)        # 700 m outside a 1.5 km circle
    snapped = snap_into_perimeter(REAL, outside)
    assert REAL.contains(Point(snapped))
    assert Point(snapped).distance(REAL.exterior) < 2 * CELL_M
    assert snap_into_perimeter(REAL, IGNITION) == IGNITION


# ---- Version 1a: wind --------------------------------------------------------------------

def test_wind_strength_zero_gives_exactly_the_no_wind_fire(domain):
    a = simulate(domain, IGNITION, 600, seed=7)
    b = simulate(domain, IGNITION, 600, seed=7, wind_toward_deg=90, wind_k=0)
    assert np.array_equal(a, b)


def test_wind_still_burns_exactly_the_target_area(domain):
    fire = simulate(domain, IGNITION, 600, seed=2, wind_toward_deg=90, wind_k=2)
    assert int(fire.sum()) == 600


def test_fire_reaches_further_downwind_than_upwind(domain):
    r0, c0 = domain.cell_of(*IGNITION)
    east, west = [], []
    for seed in range(15):
        cols = np.where(simulate(domain, IGNITION, 600, seed=seed, wind_toward_deg=90, wind_k=3))[1]
        east.append(cols.max() - c0)
        west.append(c0 - cols.min())
    assert np.mean(east) > 1.5 * np.mean(west)


def test_wind_from_the_west_beats_a_round_fire_on_an_east_west_oval():
    from shapely import affinity
    oval = affinity.scale(Point(503_000, 4_100_000).buffer(1.0, 64), 3000, 900)     # long axis east-west
    start = (500_100, 4_100_000)                                                    # western tip
    dom = make_domain(oval, start, margin=2_500)
    real = rasterize(oval, dom)
    target = int(real.sum())
    round_score = iou(circle_baseline(dom, start, target), real)
    wind_scores = [iou(simulate(dom, start, target, seed=s, wind_toward_deg=90, wind_k=3), real) for s in range(10)]
    assert np.mean(wind_scores) > round_score + 0.2


# ---- Version 1b: wind that changes with the area burned -------------------------------------------

def _domain_and_start():
    from modules.fire_monitoring.spread_v0 import Domain
    d = Domain(x0=0.0, y0=0.0, n_rows=200, n_cols=200)
    return d, (9000.0, 9000.0)


def test_constant_schedule_equals_static_wind():
    from modules.fire_monitoring.spread_v0 import simulate
    d, xy = _domain_and_start()
    static = simulate(d, xy, 800, seed=3, wind_toward_deg=90, wind_k=2.0)
    sched = simulate(d, xy, 800, seed=3, wind_schedule=[(90, 2.0)] * 12)
    assert (static == sched).all()


def test_schedule_still_burns_exactly_the_target_area():
    from modules.fire_monitoring.spread_v0 import simulate
    d, xy = _domain_and_start()
    fire = simulate(d, xy, 800, seed=1, wind_schedule=[(90, 2.0)] * 6 + [(270, 2.0)] * 6)
    assert int(fire.sum()) == 800


def test_wind_that_turns_gives_a_different_fire_than_either_steady_wind():
    from modules.fire_monitoring.spread_v0 import simulate
    d, xy = _domain_and_start()
    east = simulate(d, xy, 1500, seed=5, wind_schedule=[(90, 3.0)] * 8)
    turn = simulate(d, xy, 1500, seed=5, wind_schedule=[(90, 3.0)] * 4 + [(270, 3.0)] * 4)
    assert (east != turn).any()
    cols_east = int(((east).nonzero()[1]).max()) - int(((east).nonzero()[1]).min())
    cols_turn = int(((turn).nonzero()[1]).max()) - int(((turn).nonzero()[1]).min())
    assert cols_turn != cols_east
