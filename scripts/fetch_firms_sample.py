"""
fetch_firms_sample.py -- first contact with the NASA FIRMS API (Week 1, M4).

What it does:
  1. Checks your MAP_KEY works by asking FIRMS which data sources exist and
     which dates each one covers (printed as a table).
  2. Requests the last few days of hotspots over the Shaver Lake box and
     saves them to data/samples/firms_sample.csv.

Run from the repo root:   python scripts/fetch_firms_sample.py
Install once:             pip install requests pandas python-dotenv

Needs a .env file in the repo root containing:   FIRMS_MAP_KEY=your_key_here
"""
import os
import sys
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

BASE = "https://firms.modaps.eosdis.nasa.gov/api"
BBOX = "-119.50,37.00,-119.25,37.20"   # west,south,east,north (same as docs/STUDY_AREA.md)
SOURCE = "VIIRS_NOAA20_NRT"            # NOAA-20 satellite, near-real-time (SNPP has been retired)
DAYS = 3                               # one request allows 1-5 days
OUT_FILE = Path("data/samples/firms_sample.csv")


def get_text(url: str) -> str:
    """GET a URL and return its text. Never prints the URL: it contains your key."""
    try:
        resp = requests.get(url, timeout=60)
    except requests.RequestException as exc:
        sys.exit(f"Network problem: {type(exc).__name__}")
    if resp.status_code != 200:
        sys.exit(f"FIRMS answered with HTTP {resp.status_code}: {resp.text[:200]}")
    return resp.text


def main() -> None:
    load_dotenv()
    key = os.getenv("FIRMS_MAP_KEY")
    if not key:
        sys.exit("FIRMS_MAP_KEY not found. Check your .env file is in the repo root.")

    # --- Step 1: which sources exist, and what dates do they cover? ---------
    text = get_text(f"{BASE}/data_availability/csv/{key}/ALL")
    availability = pd.read_csv(StringIO(text))
    print("=== Data availability (copy this table back to Claude) ===")
    print(availability.to_string(index=False))

    # --- Step 2: hotspots over the study area -------------------------------
    text = get_text(f"{BASE}/area/csv/{key}/{SOURCE}/{BBOX}/{DAYS}")
    detections = pd.read_csv(StringIO(text))
    if "latitude" not in detections.columns:
        # FIRMS reports some errors as plain text with HTTP 200.
        sys.exit(f"Unexpected reply from FIRMS: {text[:300]}")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    detections.to_csv(OUT_FILE, index=False)

    print(f"\n=== {SOURCE}, last {DAYS} days, Shaver Lake box ===")
    print(f"Detections found: {len(detections)}")
    print(f"Columns: {list(detections.columns)}")
    if len(detections):
        print(detections.head().to_string(index=False))
    else:
        print("No detections. This is normal for a quiet 22 km box.")
    print(f"Saved {OUT_FILE}")


if __name__ == "__main__":
    main()
