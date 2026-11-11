# Data Sources

Raw data is **not stored in the repo** (it is large, and `data/raw/` is in `.gitignore`).
Each team member downloads it once, following the steps below, so everyone works from the same inputs.

Study area and grid rules are in `docs/STUDY_AREA.md`.

---

## 1. NASA FIRMS (satellite fire detections)

Used by: M4 (`active_fire` layer; also useful to M3 as a check on risk predictions).

**Each person needs their own key. Never share it or commit it.**

1. Request a free MAP_KEY: https://firms.modaps.eosdis.nasa.gov/api/map_key/ (an email address is enough).
2. Copy `.env.example` to `.env` in the repo root and set:
   ```
   FIRMS_MAP_KEY=your_key_here
   ```
3. Check that `.env` is listed in `.gitignore` before you save the key.

Test your setup from the repo root:

```
python scripts/fetch_firms_sample.py
```

This prints the data-availability table and saves a small sample to `data/samples/firms_sample.csv`.

### Which satellite source to use

| Need | Source | Covers (checked 2026-11-10) |
|---|---|---|
| Live / recent monitoring | `VIIRS_NOAA20_NRT` or `VIIRS_NOAA21_NRT` | NOAA-20 from 2026-08-01, NOAA-21 from 2024-01-17, up to today |
| History, 2018 to mid-2026 | `VIIRS_NOAA20_SP` / `VIIRS_NOAA21_SP` | NOAA-20 from 2018-04-01, NOAA-21 from 2023-03-01, up to 2026-07-31 |
| History before 2018 (e.g. the 2016 Goose fire) | `VIIRS_SNPP_SP` | 2012-01-20 to 2026-07-31 |

Notes:
- Suomi NPP (SNPP) stopped delivering new observations on 2 November 2026. Do not use SNPP for live data. Its archive (`_SP`) is still the right source for older fires.
- One area request covers 1 to 5 days, so longer periods need several requests.
- Detections are **satellite thermal detections, not confirmed fires**. FIRMS warns of false alarms from hot surfaces such as bright roofs.
- `confidence` for VIIRS is `l`, `n` or `h` (low, nominal, high). It is not the same scale as MODIS confidence.
- Acknowledgement (required by NASA when using the data): "We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS), part of NASA's Land, Atmosphere Near real-time Capability for Earth observations (LANCE)."

Availability can change. Re-run `scripts/fetch_firms_sample.py` to print the current table.

---

## 2. CAL FIRE historical fire perimeters

Used by: M4 (historical layer, time-slider playback, validation of fire spread), and M3 (fire labels).

What it is: polygons outlining the area each fire burned, with fire name, year, alarm date, containment date, cause and acres.

**Download once into `data/raw/`:**

1. Source: California Fire Perimeters (all), https://www.lab.data.ca.gov/dataset/california-fire-perimeters-all
   geojson format file was downloaded
2. File used by the team so far: `California_Historic_Fire_Perimeters_-4891938132824355098` (about 249.5 MB).
3. Save it in `data/raw/` without renaming it, so scripts and notes refer to the same name.

Known properties of this file (from our first run):
- Coordinate system: EPSG:3857 (the scripts convert it to EPSG:4326 / UTM 11N as needed).
- 23,334 features, with fields including `YEAR_`, `FIRE_NAME`, `ALARM_DATE`, `CONT_DATE`, `CAUSE`, `GIS_ACRES`.
- Many older fires have no name or dates, so always check for missing values.
- The polygon is usually the **final** burned area, not the fire's shape hour by hour.

List the fires that touch the study area:

```
python scripts/list_fires_in_box.py "data/raw/California_Historic_Fire_Perimeters_-4891938132824355098"
```

This writes `data/processed/fires_in_box.csv`. Do not commit the raw file.

---

## 3. Shared grid (committed to the repo)

`data/grid.geojson` is built by `scripts/make_grid.py` and **is** in the repo. Everyone loads this file; nobody builds their own grid. See `docs/STUDY_AREA.md`.

---

## Setup checklist for a new team member

1. Clone the repo and create a virtual environment (`.venv/`, not committed).
2. Install the packages the scripts need: `pip install requests pandas python-dotenv geopandas pyogrio shapely pyproj`
3. Get a FIRMS key and create `.env` (section 1).
4. Download the perimeter file into `data/raw/` (section 2).
5. Run the two test scripts above and check that they finish without errors.