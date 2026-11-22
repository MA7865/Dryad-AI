from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from modules.ignition_risk import interface
from modules.shared.weather import WeatherError

router = APIRouter(prefix="/api/v1", tags=["weather"])


class HourlyWeather(BaseModel):
    time: str
    lat: float
    lon: float
    temp_c: float | None
    rh_pct: float | None
    wind_speed_ms: float | None
    wind_gust_ms: float | None
    wind_dir_deg: float | None
    wind_toward_deg: float | None
    precip_mm: float | None
    precip_24h_mm: float | None
    precip_7d_mm: float | None
    precip_30d_mm: float | None
    vpd_kpa: float | None


class WeatherForecast(BaseModel):
    data_kind: str
    source: str
    generated_at: str
    timezone: str
    hourly: list[HourlyWeather]


@router.get(
    "/weather/forecast",
    response_model=WeatherForecast,
    summary="Get the Open-Meteo hourly weather forecast",
)
def weather_forecast(hours: int = 48) -> dict:
    if hours < 1 or hours > 384:
        raise HTTPException(status_code=422, detail="hours must be between 1 and 384")
    try:
        return interface.get_forecast(hours)
    except WeatherError as exc:
        raise HTTPException(status_code=503, detail=str(exc), headers={"Retry-After": "60"})
