from typing import Literal

from fastapi import APIRouter, HTTPException

from backend.app.schemas.forest_health import ForestHealthPatch
from modules.forest_health import interface, live_service

router = APIRouter(prefix="/api/v1", tags=["forest-health"])

live_service.ensure_fresh()     # start computing the live layer in the background at API start

SUMMER_HELP = ("Summer layer not built. Run: python -m modules.forest_health.build_summers "
               "then python -m modules.forest_health.build_outputs")


def _not_ready(exc: interface.LiveNotReady) -> HTTPException:
    return HTTPException(
        status_code=503, headers={"Retry-After": "60"},
        detail=f"Live layer is being computed from Earth Engine. Retry in about a minute. Status: {exc.status}")


@router.get("/layers/forest-health")
def forest_health_layer(period: Literal["summer", "live"] = "summer") -> dict:
    """All patches as GeoJSON. period=summer is the latest full summer, period=live the latest satellite window."""
    try:
        return interface.get_layer(period)
    except interface.LiveNotReady as exc:
        raise _not_ready(exc)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail=SUMMER_HELP)


@router.get("/layers/forest-health/status")
def forest_health_status() -> dict:
    """When each forest-health layer was built (for a 'last refresh' display)."""
    return interface.get_status()


@router.get("/patches/{patch_id}/forest-health", response_model=ForestHealthPatch)
def forest_health_patch(patch_id: str):
    """Everything the click panel needs for one patch."""
    try:
        result = interface.get_patch(patch_id)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail=SUMMER_HELP)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown patch_id: {patch_id}")
    return result