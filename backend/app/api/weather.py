from fastapi import APIRouter, HTTPException

from modules.ignition_risk import interface
from modules.shared.weather import WeatherError

router = APIRouter(prefix="/api/v1", tags=["weather"])


@router.get("/weather/forecast")
def weather_forecast(hours: int = 48) -> dict:
    if hours < 1 or hours > 384:
        raise HTTPException(status_code=422, detail="hours must be between 1 and 384")
    try:
        return interface.get_forecast(hours)
    except WeatherError as exc:
        raise HTTPException(status_code=503, detail=str(exc), headers={"Retry-After": "60"})
