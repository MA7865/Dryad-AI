"""
fetch_goose_weather.py -- hourly weather for the Goose fire (30 July - 1 August 2016).

Asks Open-Meteo's historical weather service (free, no key) for wind, temperature, humidity and
rain at the Goose fire, saves it, and shows which way the wind blew while the fire was growing.

Run from the repo root:
    python scripts/fetch_goose_weather.py
Install once:  pip install requests pandas geopandas

Wind direction convention: Open-Meteo reports the direction the wind comes FROM, in degrees
(270 = from the west, so it blows toward the east). This script also prints the direction the wind
blows TOWARD, because that is the direction a fire is pushed. Check the convention on Open-Meteo's
documentation page for the historical weather API before relying on it.
"""
import argparse
import math
import sys
import time
from pathlib import Path

import pandas as pd
import requests

# Documented archive address first; the second is a fallback some tools use.
URLS = ["https://archive-api.open-meteo.com/v1/archive", "https://api.open-meteo.com/v1/archive"]
HOURLY = ["temperature_2m", "relative_humidity_2m", "precipitation",
          "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"]
START_DATE, END_DATE = "2016-07-30", "2016-08-01"
IGNITION_UTC = "2016-07-30 23:40"          # CAL FIRE: 4:40 PM local time (PDT = UTC-7)
SHOW_FROM, SHOW_TO = "2016-07-30 18:00", "2016-08-01 23:00"   # rows printed (UTC)
CAL_FIRE_POINT = (37.01591, -119.50507)    # fallback location if the perimeter file is missing
OUT_CSV = Path("data/samples/goose_weather_2016.csv")
COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def compass(deg: float) -> str:
    return COMPASS[int((deg % 360) / 22.5 + 0.5) % 16]


def toward(from_deg):
    """Direction the wind blows toward, given the direction it comes from."""
    return (from_deg + 180) % 360


def mean_wind(speed, from_deg):
    """Average several hourly winds as vectors. Returns (toward_deg, mean_speed, steadiness).

    steadiness is 1.0 if the wind never changed direction and near 0 if it swung all around."""
    u = [-s * math.sin(math.radians(d)) for s, d in zip(speed, from_deg)]   # eastward part
    v = [-s * math.cos(math.radians(d)) for s, d in zip(speed, from_deg)]   # northward part
    mu, mv = sum(u) / len(u), sum(v) / len(v)
    mean_speed = sum(speed) / len(speed)
    return math.degrees(math.atan2(mu, mv)) % 360, mean_speed, (math.hypot(mu, mv) / mean_speed if mean_speed else 0.0)


def goose_location(perimeter_path: str):
    try:
        import geopandas as gpd
        g = gpd.read_file(perimeter_path).to_crs("EPSG:32611").geometry.union_all().centroid
        c = gpd.GeoSeries([g], crs="EPSG:32611").to_crs("EPSG:4326").iloc[0]
        return c.y, c.x, "centre of the Goose perimeter"
    except Exception:
        return CAL_FIRE_POINT[0], CAL_FIRE_POINT[1], "CAL FIRE published point (perimeter file not found)"


def fetch(lat: float, lon: float, retries: int = 2) -> dict:
    params = {"latitude": round(lat, 4), "longitude": round(lon, 4), "start_date": START_DATE,
              "end_date": END_DATE, "hourly": ",".join(HOURLY), "wind_speed_unit": "ms", "timezone": "UTC"}
    problem = "unknown problem"
    for url in URLS:
        for attempt in range(retries + 1):
            try:
                resp = requests.get(url, params=params, timeout=60)
            except requests.RequestException as exc:
                problem = f"network problem ({type(exc).__name__})"
            else:
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("error"):
                        sys.exit(f"Open-Meteo reported an error: {data.get('reason')}")
                    return data
                problem = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if resp.status_code < 500 and resp.status_code != 429:
                    break                              # not temporary: try the next address
            time.sleep(1.5 * 2 ** attempt)
    sys.exit(f"Could not get weather data ({problem}). Tell Claude exactly what the message says.")


def to_frame(data: dict) -> pd.DataFrame:
    h = data["hourly"]
    df = pd.DataFrame({
        "time_utc": pd.to_datetime(h["time"]),
        "temperature_c": h["temperature_2m"],
        "rh_pct": h["relative_humidity_2m"],
        "precip_mm": h["precipitation"],
        "wind_ms": h["wind_speed_10m"],
        "gust_ms": h["wind_gusts_10m"],
        "wind_from_deg": h["wind_direction_10m"],
    })
    df["wind_toward_deg"] = df["wind_from_deg"].apply(lambda d: toward(d) if pd.notna(d) else float("nan"))
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--perimeter", default="data/processed/goose_2016_perimeter.geojson")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    a = ap.parse_args()

    if a.lat is not None and a.lon is not None:
        lat, lon, where = a.lat, a.lon, "given on the command line"
    else:
        lat, lon, where = goose_location(a.perimeter)
    print(f"Location: {lat:.4f}, {lon:.4f} ({where})")

    data = fetch(lat, lon)
    print(f"Open-Meteo grid point used: {data.get('latitude')}, {data.get('longitude')}, "
          f"elevation {data.get('elevation')} m  (the data is coarse, roughly 10 km pixels)")
    df = to_frame(data)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    shown = df[(df.time_utc >= SHOW_FROM) & (df.time_utc <= SHOW_TO)].copy()
    shown["local_PDT"] = shown.time_utc.dt.tz_localize("UTC").dt.tz_convert("America/Los_Angeles").dt.strftime("%d %H:%M")
    shown["from"] = shown.wind_from_deg.apply(lambda d: compass(d) if pd.notna(d) else "")
    shown["toward"] = shown.wind_toward_deg.apply(lambda d: compass(d) if pd.notna(d) else "")
    print(f"\n=== Hourly weather (ignition about {IGNITION_UTC} UTC) ===")
    cols = ["time_utc", "local_PDT", "wind_ms", "gust_ms", "wind_from_deg", "from", "toward",
            "temperature_c", "rh_pct", "precip_mm"]
    table = shown[cols].copy()
    num = ["wind_ms", "gust_ms", "wind_from_deg", "temperature_c", "rh_pct", "precip_mm"]
    table[num] = table[num].round(1)
    print(table.to_string(index=False))

    print("\n=== Average wind (vector average) ===")
    for label, lo, hi in [("first day after ignition (31 Jul, UTC)", "2016-07-31 00:00", "2016-07-31 23:00"),
                          ("second day (1 Aug, UTC)", "2016-08-01 00:00", "2016-08-01 23:00")]:
        w = df[(df.time_utc >= lo) & (df.time_utc <= hi)].dropna(subset=["wind_ms", "wind_from_deg"])
        if w.empty:
            print(f"{label}: no data")
            continue
        t, s, steady = mean_wind(w.wind_ms.tolist(), w.wind_from_deg.tolist())
        print(f"{label}: blowing toward {t:.0f} deg ({compass(t)}), mean speed {s:.1f} m/s, "
              f"steadiness {steady:.2f} (1 = never changes direction)")
    print("\nGoose ran from its western tip toward the east, so a wind blowing toward about 90 deg (E) would fit.")
    print(f"Saved {OUT_CSV}")


if __name__ == "__main__":
    main()
