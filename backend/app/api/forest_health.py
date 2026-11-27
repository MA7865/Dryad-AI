from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.forest_health import ForestHealthPatch
from modules.forest_health import interface, live_service

router = APIRouter(prefix="/api/v1", tags=["forest-health"])

live_service.ensure_fresh()     # start computing the live layer in the background at API start

SUMMER_HELP = ("Summer layer not built. Run: python -m modules.forest_health.build_outputs")


def _not_ready(exc: interface.LiveNotReady) -> HTTPException:
    return HTTPException(
        status_code=503, headers={"Retry-After": "60"},
        detail=f"Live layer is being computed from Earth Engine. Retry in about a minute. Status: {exc.status}")


@router.get("/layers/forest-health")
def forest_health_layer(
    period: Literal["summer", "live"] = "summer",
    frame: str | None = Query(None, description="Frame id from /timeline, for example 2023-summer"),
    year: int | None = Query(None, ge=2000, le=2100, description="Shortcut for frame={year}-summer"),
) -> dict:
    """All patches as GeoJSON. period=summer (default latest summer, or a past frame) or period=live."""
    if period == "summer" and frame is None and year is not None:
        frame = f"{year}-summer"
    try:
        return interface.get_layer(period, frame)
    except interface.LiveNotReady as exc:
        raise _not_ready(exc)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail=SUMMER_HELP)
    except KeyError:
        raise HTTPException(status_code=404,
                            detail=f"Unknown frame '{frame}'. See /api/v1/layers/forest-health/timeline for the list.")


@router.get("/layers/forest-health/timeline")
def forest_health_timeline() -> dict:
    """Frames (summers, and seasons if built) plus per-patch series, for animations. One call."""
    try:
        return interface.get_timeline()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail=SUMMER_HELP)


@router.get("/layers/forest-health/status")
def forest_health_status() -> dict:
    """When each forest-health layer was built (for a 'last refresh' display)."""
    return interface.get_status()


@router.get("/layers/forest-health/model-card")
def forest_health_model_card() -> dict:
    """Training data, metrics, calibration and limits of the mortality-likelihood model."""
    try:
        return interface.get_model_card()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Model card not built. Run: python -m scripts.train_final")


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


@router.get("/patches/{patch_id}/forest-health/timeline")
def forest_health_patch_timeline(patch_id: str) -> dict:
    """One patch across all frames (index, band, NDVI, NDMI, mortality likelihood)."""
    try:
        result = interface.get_patch_timeline(patch_id)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail=SUMMER_HELP)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown patch_id: {patch_id}")
    return result