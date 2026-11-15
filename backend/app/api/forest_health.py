from fastapi import APIRouter, HTTPException

from backend.app.schemas.forest_health import ForestHealthPatch
from modules.forest_health import interface

router = APIRouter(prefix="/api/v1", tags=["forest-health"])


@router.get("/layers/forest-health")
def forest_health_layer() -> dict:
    """All patches as GeoJSON, latest summer. Colour the map with properties.health_band."""
    return interface.get_layer()


@router.get("/patches/{patch_id}/forest-health", response_model=ForestHealthPatch)
def forest_health_patch(patch_id: str):
    """Everything the click panel needs for one patch."""
    result = interface.get_patch(patch_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown patch_id: {patch_id}")
    return result