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
2. Install the packages the scripts need: `pip install -r requirements.txt`
3. Get a FIRMS key and create `.env` (section 1).
4. Download the perimeter file into `data/raw/` (section 2).
5. Run the two test scripts above and check that they finish without errors.

## 4. Sentinel-2 surface reflectance (Google Earth Engine)

Used by: M1 (`forest_health` layer). Also useful to M2 for vegetation features.

What it is: ESA Sentinel-2 Level-2A surface reflectance, 10-20 m resolution, a new image about every 5 days. Earth Engine collection: `COPERNICUS/S2_SR_HARMONIZED`.

Access: a free Google Earth Engine account (noncommercial registration). The imagery is **not downloaded**; the calculations run in Earth Engine and only a small table comes back.

How M1 uses it:
- Summers 2022-2026 (1 June to 30 September), scenes with `CLOUDY_PIXEL_PERCENTAGE < 60`.
- Clouds, cloud shadow and cirrus are masked with the scene classification band (`SCL` classes 3, 8, 9, 10, 11), then a median composite is made for each summer.
- NDVI (B8, B4), NDMI (B8, B11) and NBR (B8, B12) are averaged over the forest pixels of each 500 m patch.
- Scene counts per summer: 2022: 83, 2023: 85, 2024: 92, 2025: 117, 2026: 113.

Scripts: `modules/forest_health/gee/01_data_checks.js` (sanity checks) and `modules/forest_health/gee/02_feature_table.js` (exports the table). The second script needs the team grid uploaded as an Earth Engine table asset; change `GRID_ASSET` to your own asset path.

Output (committed): `data/processed/m1_features_2022_2026.csv`, 10,305 rows (2,061 patches x 5 summers).

Notes:
- Summer medians hide changes within a summer.
- In the 2021-2024 check, 99.7% of forest pixels had cloud-free data.
- Acknowledgement: "Contains modified Copernicus Sentinel data."

---

## 5. ESA WorldCover v200 (tree-cover mask)

Used by: M1.

What it is: a 10 m global land-cover map for 2021. Earth Engine collection: `ESA/WorldCover/v200`.

How M1 uses it: class 10 ("tree cover") is the forest mask. Index values are averaged over tree pixels only. Patches with less than 20% tree cover are not scored. About 73% of the study area is tree cover.

Notes: it is a single-year map applied to all summers, so tree loss or growth after 2021 is not reflected.

---

## 6. MODIS burned area (MCD64A1)

Used by: M1 (burn context). May also help M4 and M3.

What it is: a monthly 500 m burned-area product. Earth Engine collection: `MODIS/061/MCD64A1`, band `BurnDate`.

How M1 uses it: any pixel with a burn date between 2015-01-01 and 2026-12-01 counts as burned. `burn_frac` is the share of each patch flagged burned. Patches with `burn_frac` above 0.50 are "mostly burned", below 0.05 are "unburned", and anything between is "partial". About 55% of the study area is flagged burned, mostly the 2020 Creek Fire.

Notes: coarse (500 m), so edges are rough. It could later be refined with the CAL FIRE perimeters in section 2.

---

## 7. USFS Insect and Disease Survey (IDS) damage areas

Used by: M1 (reference and validation only, not used for training). Possibly M2 (observed damage).

What it is: polygons drawn by Forest Service surveyors from aircraft around areas of tree damage, with the cause (for example fir engraver, western pine beetle, drought), host species, damage type and a damage level.

Source: USFS Enterprise Data Warehouse map service `EDW_InsectandDiseaseSurvey_01`, layer 1 ("IDS AREAS"):
https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_InsectandDiseaseSurvey_01/MapServer/1

Download from the repo root (no key needed):

```
python scripts/fetch_ids_labels.py
```

This saves `data/raw/ids_shaver_2021_2024.geojson` (not committed) and prints a summary.

What the study area contains (checked 2026-11-15): only 22 polygons for 2021-2024 (2 in 2021, 11 in 2022, 6 in 2023, 3 in 2024), about 4,900 acres. Causes: 19 fir engraver, 2 western pine beetle, 1 drought. Damage levels: 16 are "very light" or "light" (1-10% of trees), 5 moderate, 1 severe.

Notes:
- The polygons are sketch maps drawn from the air and are approximate. They can include healthy trees.
- No polygon does **not** mean the forest is healthy; it may simply not have been mapped.
- The service describes some data as generalized, which may not suit detailed analysis.
- Too few polygons to train a classifier, so M1 uses them only as a check on its index.