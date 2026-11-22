"""
firms_client.py -- talks to the NASA FIRMS Area API and nothing else.

It knows how to ask FIRMS for detections and how to fail clearly. It does not know about
GeoJSON, grids or patch IDs (that is active_fire.py).
"""
import os
import time
from datetime import date, timedelta
from io import StringIO

import pandas as pd
import requests
from dotenv import load_dotenv

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api"
MAX_DAYS_PER_REQUEST = 5          # the Area API accepts 1-5 days per request


class FirmsError(RuntimeError):
    """FIRMS could not be reached or returned something unusable.
    Messages never contain the MAP_KEY."""


def get_key() -> str:
    load_dotenv()
    key = os.getenv("FIRMS_MAP_KEY")
    if not key:
        raise FirmsError("FIRMS_MAP_KEY is not set. Put it in your .env file.")
    return key


def date_chunks(start: date, end: date) -> list:
    """Split [start, end] (both included) into (first_day, n_days) pieces of at most 5 days."""
    chunks, day = [], start
    while day <= end:
        n_days = min(MAX_DAYS_PER_REQUEST, (end - day).days + 1)
        chunks.append((day, n_days))
        day += timedelta(days=n_days)
    return chunks


def _request(url: str, key: str, retries: int, backoff: float) -> str:
    """One HTTP GET with retries for temporary problems. Never puts the URL in an error."""
    problem = "unknown problem"
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, timeout=60)
        except requests.RequestException as exc:
            problem = f"network problem ({type(exc).__name__})"
        else:
            if resp.status_code == 200:
                return resp.text
            problem = f"HTTP {resp.status_code}"
            temporary = resp.status_code >= 500 or resp.status_code == 429
            if not temporary:        # e.g. bad key: retrying will not help
                raise FirmsError(f"FIRMS answered with {problem}: {resp.text[:200]}".replace(key, "***"))
        if attempt < retries:
            time.sleep(backoff * 2 ** attempt)
    raise FirmsError(f"FIRMS request failed after {retries + 1} attempts: {problem}")


def fetch_detections(bbox, start: date, end: date, source: str, *, retries: int = 2,
                     backoff: float = 1.0, pause: float = 0.5, key: str = None) -> pd.DataFrame:
    """Download detections for bbox=(west, south, east, north) between start and end (UTC dates).

    Returns a DataFrame with FIRMS's own columns, or an empty DataFrame if there were none
    (an empty result is normal in quiet periods, not an error).
    """
    key = key or get_key()
    west, south, east, north = bbox
    area = f"{west},{south},{east},{north}"
    parts = []
    for first_day, n_days in date_chunks(start, end):
        url = f"{BASE_URL}/area/csv/{key}/{source}/{area}/{n_days}/{first_day.isoformat()}"
        text = _request(url, key, retries, backoff).strip()
        if text:
            if "latitude" not in text.splitlines()[0]:
                raise FirmsError(f"Unexpected reply from FIRMS: {text[:200]}".replace(key, "***"))
            df = pd.read_csv(StringIO(text))
            if not df.empty:
                parts.append(df)
        time.sleep(pause)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True).drop_duplicates()
