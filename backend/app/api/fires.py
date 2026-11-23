from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.fire_spread import FireSpreadRequest
from modules.fire_monitoring import FirmsError, get_active_fires, get_perimeters, simulate_fire_spread

router = APIRouter(prefix="/api/v1", tags=["fire-monitoring"])

FirmsSource = Literal["VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT", "VIIRS_NOAA20_SP", "VIIRS_NOAA21_SP", "VIIRS_SNPP_SP"]


@router.get("/fires/active")
def active_fires(
    start: Optional[str] = Query(None, description="First day, YYYY-MM-DD (UTC). Default: yesterday."),
    end: Optional[str] = Query(None, description="Last day, YYYY-MM-DD (UTC). Default: today."),
    source: FirmsSource = Query("VIIRS_NOAA20_NRT", description="FIRMS source. Use an *_SP source for history."),
) -> dict:
    """Satellite thermal detections (NOT confirmed fires) as GeoJSON, layer_type "active_fire".
    An empty FeatureCollection is normal in quiet periods."""
    try:
        return get_active_fires(start=start, end=end, source=source)
    except ValueError as e:                      # bad dates
        raise HTTPException(status_code=422, detail=str(e))
    except FirmsError:                           # FIRMS unreachable or refused: not "no fires"
        raise HTTPException(status_code=502, detail="Fire data source (NASA FIRMS) is unavailable. Try again later.")


@router.post("/simulations/fire-spread")
def fire_spread(req: FireSpreadRequest) -> dict:
    """SIMULATED fire footprint on the 500 m patches, layer_type "fire_spread".
    simulation_step is the step a patch was first reached; a step is not real time."""
    try:
        return simulate_fire_spread(
            (req.ignition_lon, req.ignition_lat), req.target_area_km2,
            wind_dir_deg=req.wind_dir_deg, wind_k=req.wind_k, seed=req.seed)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/fires/perimeters")
def fire_perimeters(
    year_from: Optional[int] = Query(None, ge=1800, le=2100, description="First year to include"),
    year_to: Optional[int] = Query(None, ge=1800, le=2100, description="Last year to include"),
) -> dict:
    """HISTORICAL CAL FIRE perimeters (final burned areas) overlapping the study area.
    Not a live fire and not a fire's growth over time."""
    try:
        return get_perimeters(year_from=year_from, year_to=year_to)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Perimeter data not built yet (run scripts/build_perimeters.py).")
