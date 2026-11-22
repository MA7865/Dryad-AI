"""
Shared Open-Meteo weather client.

Usage:
    rows = get_forecast([(37.08, -119.38)], 48)
    history = get_history([(37.08, -119.38)], "2018-01-01", "2018-01-31")

The API is requested in UTC and wind speed is requested in m/s.
`wind_dir_deg` is meteorological FROM direction; `wind_toward_deg` is
`(wind_dir_deg + 180) % 360`, the TOWARD convention used by M4.

VPD is requested directly when an API response contains it. If unavailable,
VPD (kPa) is computed from temperature and relative humidity using:
    es = 0.6108 * exp(17.27 * T / (T + 237.3))
    vpd = es * (1 - RH / 100)
"""
import math
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

import pandas as pd
import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_gusts_10m",
    "wind_direction_10m",
    "precipitation",
    "vapour_pressure_deficit",
]


class WeatherError(RuntimeError):
    """The weather service could not provide usable data."""


def wind_toward_deg(wind_dir_deg: float | None) -> float | None:
    if wind_dir_deg is None:
        return None
    value = float(wind_dir_deg)
    if not math.isfinite(value):
        return None
    return (value + 180.0) % 360.0


def nearest_point_index(patch_centers: Iterable[tuple[float, float]], points: list[tuple[float, float]]) -> list[int]:
    """Assign each (lat, lon) patch center to the nearest coarse weather point."""
    import numpy as np

    pts = [(float(lat), float(lon)) for lat, lon in points]
    if not pts:
        raise ValueError("points must not be empty")
    out = []
    for lat, lon in patch_centers:
        distances = [(float(lat) - plat) ** 2 + (float(lon) - plon) ** 2 for plat, plon in pts]
        out.append(int(np.argmin(distances)))
    return out


def vpd_kpa(temp_c: float | None, rh_pct: float | None) -> float | None:
    if temp_c is None or rh_pct is None:
        return None
    temp_c, rh_pct = float(temp_c), float(rh_pct)
    if not (math.isfinite(temp_c) and math.isfinite(rh_pct)):
        return None
    saturation_kpa = 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    return round(saturation_kpa * (1.0 - max(0.0, min(100.0, rh_pct)) / 100.0), 3)


def _clean(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _request(url: str, params: dict, retries: int = 2, timeout: int = 60) -> dict:
    problem = "unknown problem"
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            problem = f"network problem ({type(exc).__name__})"
        else:
            if response.status_code == 200:
                data = response.json()
                if data.get("error"):
                    raise WeatherError(f"Open-Meteo reported an error: {data.get('reason', 'unknown')}")
                return data
            problem = f"HTTP {response.status_code}"
            if response.status_code not in (429,) and response.status_code < 500:
                break
        if attempt < retries:
            time.sleep(1.5 * (2 ** attempt))
    raise WeatherError(f"Weather request failed after {retries + 1} attempts: {problem}")


def _to_rows(data: dict, lat: float, lon: float) -> list[dict]:
    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    rows = []
    for index, time_text in enumerate(times):
        def at(name):
            values = hourly.get(name)
            return _clean(values[index]) if values is not None and index < len(values) else None

        temp = at("temperature_2m")
        rh = at("relative_humidity_2m")
        wind_from = at("wind_direction_10m")
        precip = at("precipitation")
        supplied_vpd = at("vapour_pressure_deficit")
        rows.append({
            "time": str(time_text).replace(" ", "T").rstrip("Z") + "Z",
            "lat": lat,
            "lon": lon,
            "temp_c": temp,
            "rh_pct": rh,
            "wind_speed_ms": at("wind_speed_10m"),
            "wind_gust_ms": at("wind_gusts_10m"),
            "wind_dir_deg": wind_from,
            "wind_toward_deg": wind_toward_deg(wind_from),
            "precip_mm": precip,
            "precip_24h_mm": None,
            "precip_7d_mm": None,
            "precip_30d_mm": None,
            "vpd_kpa": supplied_vpd if supplied_vpd is not None else vpd_kpa(temp, rh),
        })
    return _rolling_precipitation(rows)


def _rolling_precipitation(rows: list[dict]) -> list[dict]:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return rows
    frame["time"] = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    frame["precip_24h_mm"] = frame["precip_mm"].rolling(24, min_periods=24).sum().round(3)
    frame["precip_7d_mm"] = frame["precip_mm"].rolling(24 * 7, min_periods=24 * 7).sum().round(3)
    frame["precip_30d_mm"] = frame["precip_mm"].rolling(24 * 30, min_periods=24 * 30).sum().round(3)
    frame["time"] = frame["time"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return frame.where(pd.notna(frame), None).to_dict("records")


def get_forecast(points: list[tuple[float, float]], hours: int) -> list[dict]:
    """Fetch hourly forecast rows for each (lat, lon), with UTC ISO timestamps."""
    if hours < 1:
        raise ValueError("hours must be at least 1")
    if not points:
        raise ValueError("points must not be empty")
    forecast_days = max(1, math.ceil(hours / 24))
    result = []
    for lat, lon in points:
        data = _request(FORECAST_URL, {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(HOURLY),
            "wind_speed_unit": "ms",
            "timezone": "GMT",
            "forecast_days": forecast_days,
        })
        result.extend(_to_rows(data, lat, lon)[:hours])
    return result


def get_history(points: list[tuple[float, float]], start, end) -> list[dict]:
    """Fetch hourly ERA5/archive rows for each point; include 30-day precipitation lookback."""
    start_date = date.fromisoformat(str(start)) if not isinstance(start, date) else start
    end_date = date.fromisoformat(str(end)) if not isinstance(end, date) else end
    if start_date > end_date:
        raise ValueError("start must not be after end")
    if not points:
        raise ValueError("points must not be empty")

    archive_start = start_date - timedelta(days=30)
    result = []
    for lat, lon in points:
        data = _request(ARCHIVE_URL, {
            "latitude": lat,
            "longitude": lon,
            "start_date": archive_start.isoformat(),
            "end_date": end_date.isoformat(),
            "hourly": ",".join(HOURLY),
            "wind_speed_unit": "ms",
            "timezone": "GMT",
        })
        rows = _to_rows(data, lat, lon)
        result.extend([row for row in rows if start_date.isoformat() <= str(row["time"])[:10] <= end_date.isoformat()])
    return result
