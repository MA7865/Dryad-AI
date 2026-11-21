"""
spread_v0.py -- Version 0 of the M4 fire-spread prototype.

No wind, slope or fuel yet: every burning cell passes fire to its 8 neighbours with the same
chance, so the fire grows into a roughly round blob. This is the BASELINE that later versions
(wind, slope, fuel, Pyretechnics) have to beat.

Everything works in metres (UTM zone 11N, EPSG:32611) on a 90 m grid. 90 m is 3 x 30 m, so it
lines up with LANDFIRE's 30 m layers later. Row 0 is the southern edge, column 0 the western edge.

Version 1a adds an optional WIND: pass wind_toward_deg (the direction the wind blows toward, as a
compass bearing) and wind_k (how strongly wind favours spread: 0 = none). Each neighbour's chance
is multiplied by exp(k * (cos(angle between that direction and the wind) - 1)), so spread is
unchanged straight downwind, weaker across the wind and weakest against it. k is a tuning knob,
not a physical measurement. With wind_k = 0 the result is identical to Version 0.

Version 0 is told how big the real fire was (it stops when it has burned that many cells), so
its score measures SHAPE and LOCATION only. It has no real clock: a "step" is not an hour.
"""
import math
from dataclasses import dataclass

import numpy as np
import shapely

CELL_M = 90
CRS_LL, CRS_M = "EPSG:4326", "EPSG:32611"
SQRT2 = math.sqrt(2.0)
# (row offset, column offset, weight): diagonal neighbours are further away, so they get less chance
NEIGHBOURS = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
              (-1, -1, 1 / SQRT2), (-1, 1, 1 / SQRT2), (1, -1, 1 / SQRT2), (1, 1, 1 / SQRT2)]


@dataclass(frozen=True)
class Domain:
    x0: float          # west edge (m, UTM easting), a multiple of CELL_M
    y0: float          # south edge (m, UTM northing), a multiple of CELL_M
    n_rows: int
    n_cols: int
    cell: int = CELL_M

    @property
    def shape(self):
        return (self.n_rows, self.n_cols)

    def centres(self):
        xs = self.x0 + (np.arange(self.n_cols) + 0.5) * self.cell
        ys = self.y0 + (np.arange(self.n_rows) + 0.5) * self.cell
        return np.meshgrid(xs, ys)          # arrays of shape (n_rows, n_cols)

    def cell_of(self, x, y):
        row, col = int((y - self.y0) // self.cell), int((x - self.x0) // self.cell)
        if not (0 <= row < self.n_rows and 0 <= col < self.n_cols):
            raise ValueError("point lies outside the simulation domain")
        return row, col


def make_domain(geom_m, ignition_xy, margin=500.0, cell=CELL_M) -> Domain:
    """Smallest 90 m-aligned box around the real fire and the ignition point, plus a margin."""
    minx, miny, maxx, maxy = geom_m.bounds
    ix, iy = ignition_xy
    minx, maxx = min(minx, ix) - margin, max(maxx, ix) + margin
    miny, maxy = min(miny, iy) - margin, max(maxy, iy) + margin
    x0, y0 = math.floor(minx / cell) * cell, math.floor(miny / cell) * cell
    return Domain(x0, y0, math.ceil((maxy - y0) / cell), math.ceil((maxx - x0) / cell), cell)


def rasterize(geom_m, domain: Domain) -> np.ndarray:
    """True for every cell whose centre lies inside the polygon."""
    xs, ys = domain.centres()
    return shapely.contains_xy(geom_m, xs, ys)


def _shift(arr: np.ndarray, dr: int, dc: int) -> np.ndarray:
    """out[r, c] = arr[r - dr, c - dc], with False outside the array."""
    h, w = arr.shape
    out = np.zeros_like(arr)
    out[max(dr, 0):h + min(dr, 0), max(dc, 0):w + min(dc, 0)] = \
        arr[max(-dr, 0):h + min(-dr, 0), max(-dc, 0):w + min(-dc, 0)]
    return out


def direction_weights(wind_toward_deg=None, wind_k: float = 0.0) -> list:
    """NEIGHBOURS with each weight multiplied by the wind effect for that direction of travel."""
    out = []
    for dr, dc, w in NEIGHBOURS:
        if wind_toward_deg is None or wind_k == 0:
            m = 1.0
        else:
            bearing = math.degrees(math.atan2(dc, dr))      # compass bearing of travel: 0 = north, 90 = east
            m = math.exp(wind_k * (math.cos(math.radians(bearing - wind_toward_deg)) - 1.0))
        out.append((dr, dc, w * m))
    return out


def simulate(domain: Domain, ignition_xy, target_cells: int, p: float = 0.4,
             burn_steps: int = 3, seed: int = 0, max_steps: int = 10_000,
             wind_toward_deg: float = None, wind_k: float = 0.0, return_steps: bool = False):
    """Grow a fire from ignition_xy until it has burned exactly target_cells cells.

    p           chance per step that a burning cell ignites one orthogonal neighbour
    burn_steps  how many steps a cell keeps burning (and keeps passing fire on)
    wind_toward_deg, wind_k   optional wind (see the module note); k = 0 means no wind
    return_steps  if True, return (burned, step) where step[r, c] is the step the cell ignited
                  (0 = ignition cell, -1 = never burned)
    Returns a boolean array: True where the fire burned.
    """
    rng = np.random.default_rng(seed)
    weights = direction_weights(wind_toward_deg, wind_k)
    burned = np.zeros(domain.shape, dtype=bool)
    left = np.zeros(domain.shape, dtype=np.int16)          # burning steps remaining
    r, c = domain.cell_of(*ignition_xy)
    burned[r, c], left[r, c] = True, burn_steps
    step_of = np.full(domain.shape, -1, dtype=np.int32)
    step_of[r, c] = 0

    for step_no in range(1, max_steps + 1):
        if burned.sum() >= target_cells:
            break
        burning = left > 0
        if not burning.any():
            # The fire went out before reaching the target (a thin front can fizzle when the wind
            # makes most directions unlikely). Real fires do not stop at random, so the edge of the
            # burned area smoulders on: every burned cell with an unburned neighbour burns again.
            open_edge = np.zeros(domain.shape, dtype=bool)
            for dr, dc, _ in NEIGHBOURS:
                open_edge |= _shift(~burned, dr, dc)
            frontier = burned & open_edge
            if not frontier.any():
                break
            left[frontier] = burn_steps
            burning = left > 0
        new = np.zeros(domain.shape, dtype=bool)
        for dr, dc, weight in weights:
            new |= _shift(burning, dr, dc) & (rng.random(domain.shape) < p * weight)
        new &= ~burned
        left[burning] -= 1
        excess = int(burned.sum() + new.sum()) - target_cells
        if excess > 0:                                      # land exactly on the target area
            idx = np.flatnonzero(new)
            new.flat[rng.choice(idx, size=excess, replace=False)] = False
        burned |= new
        left[new] = burn_steps
        step_of[new] = step_no
    return (burned, step_of) if return_steps else burned


def snap_into_perimeter(geom_m, xy, inset: float = CELL_M):
    """Move a point that lies outside a fire perimeter onto its nearest edge, then `inset` metres
    toward the middle of the fire. Points already inside are returned unchanged."""
    from shapely.geometry import Point
    from shapely.ops import nearest_points

    point = Point(xy)
    if geom_m.contains(point):
        return tuple(xy)
    edge = nearest_points(geom_m, point)[0]
    cx, cy = geom_m.centroid.x, geom_m.centroid.y
    dx, dy = cx - edge.x, cy - edge.y
    length = math.hypot(dx, dy) or 1.0
    return (edge.x + inset * dx / length, edge.y + inset * dy / length)


def touches_edge(fire: np.ndarray) -> bool:
    """True if the fire reached the edge of the domain (it may have been cut off)."""
    return bool(fire[0].any() or fire[-1].any() or fire[:, 0].any() or fire[:, -1].any())


def circle_baseline(domain: Domain, centre_xy, target_cells: int) -> np.ndarray:
    """The target_cells cells closest to centre_xy: a round 'fire' of the same area."""
    xs, ys = domain.centres()
    dist = np.hypot(xs - centre_xy[0], ys - centre_xy[1]).ravel()
    out = np.zeros(domain.shape, dtype=bool)
    out.flat[np.argsort(dist, kind="stable")[:target_cells]] = True
    return out


def iou(a: np.ndarray, b: np.ndarray) -> float:
    """Overlap divided by combined area: 1 = identical, 0 = no overlap."""
    union = int((a | b).sum())
    return float((a & b).sum()) / union if union else 0.0
