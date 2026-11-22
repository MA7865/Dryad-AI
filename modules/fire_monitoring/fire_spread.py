"""
fire_spread.py -- M4's shared function: run the spread simulation, return contract-shaped GeoJSON.

    from modules.fire_monitoring import simulate_fire_spread
    fc = simulate_fire_spread((-119.505, 37.016), target_area_km2=9.07,
                              wind_toward_deg=92, wind_k=2.0, seed=0)

Output is a SIMULATION, not an observation. One feature per 500 m patch the simulated fire reached.
`simulation_step` is the step at which the fire first entered the patch. A step is NOT a unit of real
time (the model has no clock yet), so `perimeter_time` is None and `observed_at` is None.
The model is told the final fire area (see docs/MODEL_EVALUATION.md); it predicts shape, not size.
"""
import math
from datetime import datetime, timezone

import geopandas as gpd
import numpy as np
from shapely.geometry import Point

from . import spread_v0 as sv
from .active_fire import STUDY_BBOX, load_grid

LAYER_TYPE = "fire_spread"
MODEL_VERSION = "m4-spread-0.1"
SOURCE = "simulation:ca-v1a"
PATCH_AREA_M2 = 500.0 * 500.0


def simulate_fire_spread(ignition, target_area_km2: float, wind_toward_deg: float = None,
                         wind_k: float = 0.0, seed: int = 0, p: float = 0.4,
                         burn_steps: int = 3, generated_at: str = None) -> dict:
    """Simulate one fire and aggregate it to the shared 500 m patches.

    ignition:           (lon, lat) in EPSG:4326, inside the study area.
    target_area_km2:    final burned area the fire is grown to (e.g. 9.07 for Goose).
    wind_toward_deg:    compass direction the wind blows TOWARD (0 = north, 90 = east); None = no wind.
    wind_k:             wind strength (0 = none; 2 worked best on Goose; above 3 may hit the domain edge).
    seed:               random seed; the same inputs and seed always give the same output.
    """
    lon, lat = float(ignition[0]), float(ignition[1])
    west, south, east, north = STUDY_BBOX
    if not (west <= lon <= east and south <= lat <= north):
        raise ValueError(f"ignition must lie inside the study area {STUDY_BBOX}")
    if not target_area_km2 > 0:
        raise ValueError("target_area_km2 must be positive")

    ix, iy = gpd.GeoSeries([Point(lon, lat)], crs=sv.CRS_LL).to_crs(sv.CRS_M).iloc[0].coords[0]
    target_cells = max(1, round(target_area_km2 * 1e6 / sv.CELL_M ** 2))
    radius = math.sqrt(target_area_km2 * 1e6 / math.pi)
    domain = sv.make_domain(Point(ix, iy).buffer(2.5 * radius), (ix, iy), margin=500.0)

    burned, step_of = sv.simulate(domain, (ix, iy), target_cells, p=p, burn_steps=burn_steps, seed=seed,
                                  wind_toward_deg=wind_toward_deg, wind_k=wind_k, return_steps=True)

    # Cells -> patches (a cell belongs to the patch that contains its centre).
    xs, ys = domain.centres()
    rows, cols = np.nonzero(burned)
    cells = gpd.GeoDataFrame(
        {"step": step_of[rows, cols]},
        geometry=gpd.points_from_xy(xs[rows, cols], ys[rows, cols]), crs=sv.CRS_M)
    grid_m = load_grid().to_crs(sv.CRS_M)
    joined = gpd.sjoin(cells, grid_m, how="inner", predicate="within")
    agg = joined.groupby("patch_id").agg(n=("step", "size"), first=("step", "min"))

    generated_at = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    geoms = load_grid().set_index("patch_id").geometry
    features = []
    for patch_id, r in agg.sort_values(["first"]).iterrows():
        features.append({
            "type": "Feature",
            "geometry": geoms[patch_id].__geo_interface__,
            "properties": {
                "feature_id": f"{LAYER_TYPE}:{patch_id}",
                "patch_id": patch_id,
                "layer_type": LAYER_TYPE,
                "observed_at": None,
                "generated_at": generated_at,
                "model_version": MODEL_VERSION,
                "source": SOURCE,
                "data_quality": "simulated",
                "simulation_step": int(r["first"]),
                "perimeter_time": None,
                # share of the patch covered by simulated burned 90 m cells (approximate at the edges)
                "burned_fraction": round(min(1.0, r["n"] * sv.CELL_M ** 2 / PATCH_AREA_M2), 3),
            },
        })
    return {"type": "FeatureCollection", "features": features}
