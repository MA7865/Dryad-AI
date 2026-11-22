from fastapi import APIRouter, HTTPException
import math

from backend.app.schemas.ignition_risk import (
    RiskFeatureCollection,
    RiskFeatureProperties,
    RiskStatus,
    ScenarioInput,
)
from modules.ignition_risk import interface

router = APIRouter(prefix="/api/v1", tags=["ignition-risk"])

MODEL_NOTE = "The ignition-risk model is not yet trained. This stub is not a prediction or warning."


def _validate_scenario(body: ScenarioInput) -> None:
    values = (body.delta_temp_c, body.delta_wind_pct, body.delta_precip_pct)
    if not all(math.isfinite(value) for value in values):
        raise HTTPException(status_code=422, detail="scenario values must be finite numbers")
    if not -10 <= body.delta_temp_c <= 10:
        raise HTTPException(status_code=422, detail="delta_temp_c must be between -10 and 10")
    if not -50 <= body.delta_wind_pct <= 100:
        raise HTTPException(status_code=422, detail="delta_wind_pct must be between -50 and 100")
    if not -100 <= body.delta_precip_pct <= 100:
        raise HTTPException(status_code=422, detail="delta_precip_pct must be between -100 and 100")


@router.get(
    "/layers/ignition-risk",
    response_model=RiskFeatureCollection,
    summary="Get the M3 ignition-risk stub layer",
)
def ignition_risk_layer(valid_at: str | None = None) -> dict:
    try:
        return interface.get_risk_layer(valid_at)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Shared grid is not available")


@router.get(
    "/layers/ignition-risk/status",
    response_model=RiskStatus,
    summary="Get M3 ignition-risk status",
)
def ignition_risk_status() -> dict:
    return interface.get_status()


@router.get(
    "/patches/{patch_id}/ignition-risk",
    response_model=RiskFeatureProperties,
    summary="Get one patch's M3 ignition-risk stub",
)
def ignition_risk_patch(patch_id: str) -> dict:
    result = interface.get_patch_risk(patch_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown patch_id: {patch_id}")
    return result


@router.post(
    "/simulations/weather",
    response_model=RiskFeatureCollection,
    summary="Run a weather what-if scenario",
)
def weather_scenario(body: ScenarioInput) -> dict:
    _validate_scenario(body)
    return interface.run_scenario(
        body.delta_temp_c,
        body.delta_wind_pct,
        body.delta_precip_pct,
        body.valid_at,
        body.patch_ids,
    )
