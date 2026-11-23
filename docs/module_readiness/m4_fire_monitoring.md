# M4 Module Readiness: Fire Monitoring + Fire Spread

Owner: Romaisa Kashif (M4)
Last updated: 2026-11-23
Study area and grid: see `docs/STUDY_AREA.md` (Shaver Lake, 500 m grid, `data/grid.geojson`).

Items marked `TODO` still need a value from the owner or a team decision.

## Status at a glance

| Part | Status |
|---|---|
| FIRMS access (key, request, sample saved) | Tested, works |
| FIRMS historical test (Goose fire, 2016) | Tested, works |
| CAL FIRE perimeters loaded and clipped to the study area | Tested, works |
| `get_active_fires(...)` and `active_fire` GeoJSON fixture | Done, tested (`tests/fixtures/active_fire.json`) |
| `get_perimeters(...)` (CAL FIRE perimeters, Shaver Lake) | Done, tested. Small file built by `scripts/build_perimeters.py` (100 fires). |
| Fire-spread simulation | Versions 0 (no wind), 1a (average wind), 1b (hourly wind) and 2 (slope) built and scored. 1a and 1b scored on Goose and on 12 other Sierra Nevada fires (tune/test split). Slope tested offline only. No fuel or moisture. |
| Multi-fire validation (12 fires) | Done. Wind adds about +0.06 IoU over a round fire (0.42 against 0.36); hourly wind and slope do not improve on that. See `docs/MODEL_EVALUATION.md`, Parts 2 to 4. |
| `simulate_fire_spread(...)` and `fire_spread` fixture | Done, tested (`tests/fixtures/fire_spread.json`). Area-matched, no real clock yet. |
| API endpoints (`/fires/active`, `/fires/perimeters`, `/simulations/fire-spread`) | Done, tested (`backend/app/api/fires.py`) |
| Routing (A* over OSM roads) | Not started (stretch goal) |

---

## 1. Datasets / APIs / models

| Name | Use | Link |
|---|---|---|
| NASA FIRMS Area API (VIIRS) | Satellite thermal detections (`active_fire` layer) | https://firms.modaps.eosdis.nasa.gov/api/ |
| CAL FIRE California Fire Perimeters (all) | Historical perimeters, validation ground truth | https://www.lab.data.ca.gov/dataset/california-fire-perimeters-all |
| Open-Meteo historical weather | Hourly wind, humidity, temperature for the Goose test | https://open-meteo.com/ |
| Pyretechnics (planned upgrade) | Fire-behaviour engine for spread | Not tested yet |
| OSM roads (planned, stretch) | Routing | Not tested yet |

FIRMS sources used (availability checked 2026-11-10):

| Need | Source | Covers |
|---|---|---|
| Live monitoring | `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT` | NOAA-20 from 2026-08-01, NOAA-21 from 2024-01-17, up to today |
| History 2018 onward | `VIIRS_NOAA20_SP`, `VIIRS_NOAA21_SP` | up to 2026-07-31 |
| History before 2018 | `VIIRS_SNPP_SP` | 2012-01-20 to 2026-07-31 |

Suomi NPP stopped delivering new observations on 2 November 2026, so it is used for archive data only.

Setup steps are in `docs/DATA_SOURCES.md`.

## 2. Prediction target and label definition

M4 has two parts with different targets.

**Monitoring (`active_fire`) is an observation, not a prediction.**
- Each feature is one satellite thermal detection (a VIIRS pixel, about 375 m wide).
- There is no label. Wording in the app: "satellite thermal detection", never "confirmed fire".

**Fire spread (`fire_spread`) is a simulation.**
- Target (proposed): the burned footprint of a historical fire, produced from an ignition point plus wind (so far), and later slope, fuel and fuel moisture.
- Ground truth: the CAL FIRE perimeter of the same fire.
- Metric: IoU = area(simulated ∩ real) / area(simulated ∪ real), computed on a 90 m grid.
- Test case: **Goose fire, 2016** (alarm 2016-07-30, contained 2016-08-09, 9.07 km², 1,122 cells at 90 m).
- TODO: confirm with the team that IoU on the final perimeter is the agreed spread metric.

## 3. Sample input and output

**Input (FIRMS area request):**
```
GET /api/area/csv/{MAP_KEY}/{SOURCE}/{west,south,east,north}/{DAY_RANGE}/{START_DATE}
example: VIIRS_SNPP_SP, -119.50,37.00,-119.25,37.20, 5 days, 2016-07-29
```
One request allows 1 to 5 days.

**Raw output (CSV columns):** `latitude, longitude, bright_ti4, scan, track, acq_date, acq_time, satellite, instrument, confidence, version, bright_ti5, frp, daynight`

Known values from one real Goose detection (checked on the map): acquired 2016-08-01 at 09:12 UTC, confidence `n`, FRP 9.61.

**Target output (`active_fire` feature, shape from the shared contract):**
```json
{
  "type": "Feature",
  "geometry": {"type": "Point", "coordinates": [TODO_lon, TODO_lat]},
  "properties": {
    "feature_id": "TODO",
    "patch_id": "TODO (patch containing the point)",
    "layer_type": "active_fire",
    "observed_at": "2016-08-01T09:12:00Z",
    "generated_at": "TODO (UTC ISO 8601)",
    "model_version": "m4-firms-0.1",
    "source": "VIIRS_SNPP_SP",
    "data_quality": "ok",
    "detection_id": "TODO",
    "confidence": "n",
    "detection_time": "2016-08-01T09:12:00Z",
    "satellite_source": "VIIRS_SNPP_SP"
  }
}
```
The real fixture is `tests/fixtures/active_fire.json` (8 detections per date, Goose 2016). TODO: replace the placeholders in the example above with the first feature of that file. To print it: `python -c "import json;print(json.dumps(json.load(open('tests/fixtures/active_fire.json'))['features'][0],indent=2))"`.

**Spread input and output (Version 1a, current prototype):**
- Input to `simulate_fire_spread`: ignition (lon, lat), `target_area_km2`, `wind_dir_deg` (direction the wind blows **FROM**, team convention; converted to "toward" inside the function), `wind_k`, `seed`. Hourly wind (1b) and slope (2) exist in `spread_v0.simulate` but are not exposed here, because neither improved on the average-wind model in the 12-fire test.
- Output: GeoJSON FeatureCollection, one feature per 500 m patch reached, `layer_type: "fire_spread"`, `data_kind: "simulated"`, `simulation_step` (step the fire first entered the patch; not real time), `burned_fraction`. `perimeter_time` and `observed_at` are `null` because the model has no real clock yet.
- Fixture: `tests/fixtures/fire_spread.json` (Goose-sized fire, wind from 272 deg, k = 2, seed 0).

## 4. Input/output fields, units and coordinate system

**FIRMS detection fields**

| Field | Meaning | Unit / values |
|---|---|---|
| `latitude`, `longitude` | Centre of the satellite pixel | degrees, WGS84 |
| `acq_date`, `acq_time` | Acquisition date and time | `YYYY-MM-DD`, `HHMM`, **UTC** |
| `bright_ti4`, `bright_ti5` | Brightness temperature (two heat channels) | kelvin |
| `scan`, `track` | Pixel size across and along the scan | km |
| `frp` | Fire radiative power | megawatts |
| `confidence` | Detection confidence (VIIRS) | `l` low, `n` nominal, `h` high |
| `daynight` | Day or night pass | `D` / `N` |
| `satellite`, `instrument` | Source satellite and sensor | text |

Note: MODIS confidence is a different scale from VIIRS confidence.

**CAL FIRE perimeter fields used:** `FIRE_NAME`, `YEAR_`, `ALARM_DATE`, `CONT_DATE`, `CAUSE`, `GIS_ACRES`, polygon geometry. In the file the CRS is EPSG:3857 and there are 23,334 features; many older fires have no name or dates.

**Weather fields (Open-Meteo, hourly):** time (UTC), temperature (C), relative humidity (%), precipitation (mm), wind speed and gusts at 10 m (m/s), wind direction (degrees). Resolution is roughly 10 km.

**Wind direction convention:** Open-Meteo's documentation (checked 2026-11-23) does not say whether `wind_direction_10m` is the direction the wind comes from or blows toward. We assume the usual meteorological convention (FROM, 0 = north, clockwise). Evidence from our own data supports this: in the 12-fire direction scan, the direction computed under that assumption was within 30 deg of the best-scoring direction on 8 of 12 fires. With the opposite convention it would be about 180 deg off. The assumption is therefore well supported but not confirmed by Open-Meteo.

**Terrain (slope tests only):** AWS Terrain Tiles (Terrarium format, zoom 12, about 30 m), averaged to 90 m. Used offline by `scripts/run_validation_slope.py`, cached in `data/raw/terrain/` (not committed).

**Coordinate systems:**
- GeoJSON and API output: EPSG:4326
- Distance, area and grid work: EPSG:32611 (UTM 11N)
- Timestamps: UTC, ISO 8601

## 5. Test results and baseline

| Test | Result |
|---|---|
| FIRMS access with MAP_KEY | Works. Availability table returned. |
| Quiet-period request (`VIIRS_NOAA20_NRT`, last 3 days, run 2026-11-10) | 0 detections. Valid empty response with all columns. |
| Live call, `get_active_fires()` (last 2 days, NOAA-20) | 2 detections, contract-shaped. |
| Goose fire, `VIIRS_SNPP_SP`, 2016-07-29 to 2016-08-10 | 69 detections (60 on 2016-07-31, 9 on 2016-08-01), all in 43 patches. |
| Detections vs real perimeter | 69 of 69 within 375 m of the CAL FIRE Goose perimeter (9.07 km2). |
| Open-Meteo historical weather for Goose (hourly wind) | Works. Grid point 37.0123, -119.4459, about 10 km resolution. |
| CAL FIRE perimeters built for the study box (`build_perimeters.py`) | 100 fires overlap the box. All 100 have a year, area and agency; 52 have an alarm date. File size 886 KB. |
| Unit tests | 78 pass on the author's copy (FIRMS client, contract, simulation, wind schedule, slope, terrain, perimeters, API endpoints). TODO: confirm the count from your own `python -m pytest tests -v`. |
| Spread simulation, Version 0 (no wind), western-tip start | IoU 0.106 |
| Spread simulation, Version 1a (wind from dry hours, k = 2), western-tip start | **IoU 0.487** (Goose only; k tuned on Goose) |
| Multi-fire validation, 12 Sierra Nevada fires, k chosen on 6 tune fires (k = 1) | Test fires: wind 0.398, no wind 0.370, round baseline 0.373. All 12: wind 0.416, round baseline 0.356. Wind beats the round baseline on 7 of 12. |
| Hourly wind (Version 1b), same 12 fires | Test 0.456 against 0.398 for 1a, but tune 0.388 against 0.433. All 12: 0.422 against 0.416. No clear improvement. |
| Slope (Version 2), same 12 fires | Wind + slope: no gain (b = 0 chosen on tune fires). Slope only: 0.372 against 0.353 without slope (exploratory). |

**Baseline for spread:** a round fire of the same area, centred on the same start point: IoU **0.108**. Wind from the weather data raises it to 0.487. The full tables, method and limitations are in `docs/MODEL_EVALUATION.md`.

**Start-point sensitivity (wind, k = 2, 10 runs per start):** moving the start up to 600 m north, east or west of the snapped western tip leaves IoU at 0.44 to 0.51 (centre 0.502; batch-to-batch noise 0.451 to 0.510). Moving it south lowers IoU to 0.36 to 0.42 at 300 m and 0.27 to 0.34 at 600 m. Starts outside the real perimeter still score about 0.49, so IoU cannot pin down the ignition location. See Table 4 in `docs/MODEL_EVALUATION.md`.

**Multi-fire validation (summary):** the Goose result (0.49 against 0.11) does not carry over. On 12 other fires, tuned on 6 and tested on 6, the best wind strength is k = 1, and wind from the 10 km weather data adds only about +0.06 IoU over a round fire of the same area, with large differences between fires. With the best of 12 directions the model reaches about 0.50, so most of the possible gain is lost through direction error, not model structure. Hourly wind (1b) and slope (2) did not improve on average wind. Full tables, protocol and limitations are in `docs/MODEL_EVALUATION.md`, Parts 2 to 4.

Caveat: the area is given to the model, ignition points are estimated, the wind is a 10 km reanalysis, and there is no real clock. Quote the 12-fire numbers, not the Goose number.

## 6. Run time, memory and API limits

- Run time: 90 spread simulations take 0.6 s on a laptop (Python 3.14.4). The unit tests run in a few seconds. Memory not measured.
- Validation scripts (author's laptop): `run_validation_slope.py` took 47 to 489 s per fire (9 fires in about 28 minutes, including terrain tile downloads); results are cached per fire, so a re-run takes seconds. TODO: time `run_validation.py` and `run_validation_1b.py` the same way.
- Run time of the data scripts (`fetch_firms_sample.py`, `fetch_goose_firms.py`, `list_fires_in_box.py`): TODO (time them).
- Perimeter file: about 249.5 MB. The scripts read only the features near the study area, not the whole file.
- Grid file: about 880 KB (2,061 cells).
- Small perimeter file (`data/processed/fire_perimeters_shaver.geojson`): 886 KB, 100 fires, outlines simplified by 10 m. The backend reads this file, never the 249.5 MB raw download. A call to `/fires/perimeters` without a year filter returns about that much.
- FIRMS limits (NASA pages, checked 2026-11-23): "MAP_KEY limit is 5000 transactions / 10-minute interval", and larger requests (for example 7 days) may count as more than one transaction. The Area API page now documents a day range of 1 to 10; our client still requests at most 5 days at a time, which is within it. The maximum bounding box is the whole world. The validation downloads (many fires, 7 days each) stayed within the limit; the client retries on failure.
- Open-Meteo (terms checked 2026-11-23): free API, no key, for non-commercial use (educational use and public research are listed as allowed). Limits: fewer than 10,000 calls per day, 5,000 per hour and 600 per minute. Data are under CC BY 4.0: credit Open-Meteo and link to it wherever the data are shown. Our project makes a few dozen calls, far below the limits. The wind-direction convention is not stated in their documentation (see section 4).

## 7. Known issues and fallback decision

**Known issues**
1. A FIRMS detection is a satellite thermal anomaly. It can be a non-fire hot surface, and clouds can hide real fires.
2. Empty results are normal in quiet periods and must not be treated as an error.
3. The Goose test has detections on only two days (31 July and 1 August 2016), although the fire was contained on 9 August. Hour-by-hour growth cannot be validated, so validation rests on the final perimeter and a rough check against the 31 July / 1 August detections.
4. Goose covers only about 36 cells at 500 m. IoU at that resolution is very coarse. The simulation runs on a finer internal 90 m grid, then will be aggregated to the shared 500 m patches.
5. The CAL FIRE polygon is usually the final footprint, not the fire's shape over time.
6. Other fires in the study area since 2018 are tiny (mostly under 1 km²). The Creek fire (2020) is far larger than the study box.
7. Perimeter dates arrive as GMT text strings and must be parsed.
8. Detection times are UTC; the Goose 1 August detection at 09:12 UTC is an overnight local pass.
9. CAL FIRE's published Goose ignition point lies 725 m outside the perimeter, so the ignition location is uncertain. The score depends on it most in Version 0 (no wind: published point 0.059, snapped inside 0.106, perimeter centre 0.514). With wind it is robust to the start within about 600 m, except to the south (issue 14).
10. Wind data is about 10 km resolution. Direction is usable, speed is probably underestimated.
11. The result is very sensitive to wind direction (90 deg gives 0.51, 120 deg gives 0.15).
12. The model is given the real fire area and has no real clock, so it shows shape and direction, not fire size or timing.
13. The wind-strength parameter k was tuned on the same fire it is scored on, and the dry-hours wind filter (humidity below 25 %) was chosen after seeing results.
14. IoU on the final shape does not identify the ignition point. Starts up to 600 m north, east or west of the snapped tip score about the same (0.44 to 0.51), including starts outside the real perimeter. Starts to the south score lower (0.27 to 0.42).
15. 48 of the 100 perimeters in the study box have no alarm date, so `alarm_date`, `observed_at` and `perimeter_time` are `null` for them. All 100 have a year.
16. The 2020 Creek fire (153,717 ha) overlaps the box but is far larger than it. Its outline is not clipped, so the response contains polygon parts far outside the study area.
17. `cause` is passed through as CAL FIRE stores it (possibly a numeric code). TODO: decide whether to translate the codes.
18. For a fire started at Goose's western tip, about 2 % of burned cells fall west of the grid and are dropped, so the patch totals come to about 8.7 km2 instead of 9.07.
19. The 12-fire result is modest: wind adds about +0.06 IoU, inconsistently (beats the round baseline on 7 of 12 fires). The main limit is wind direction error from 10 km weather data, not the spread rule.
20. Ignition points in the 12-fire test are estimated from the first 6 hours of detections and can lie thousands of metres from the real start on large fires, so scores for large fires mostly measure area and shape.
21. Hourly wind (1b) uses time proportional to area burned, not a real clock. It was worse than 1a on all five steady-wind fires and mixed on the others. Not exposed in the API.
22. Slope is a simple exp(b x rise/run) rule. On top of wind it adds nothing; alone it gives a small gain whose best setting (b = 4) is the largest value tried. Not exposed in the API. Fuel and moisture are not modelled.
23. The 12 validation fires were chosen with a hand-drawn Sierra Nevada outline and favour fires with many detections, so small or short fires are under-represented.

**Fallback decision (proposed)**
- Result of the evaluation: the spread simulation beats the round-fire baseline only modestly (0.42 against 0.36 over 12 fires), so it is shipped as a clearly labelled **simulated what-if layer**, not as a prediction. Observed layers (detections, perimeters) stay the main content.
- Fallback kept in case the team wants it: **historical event playback** (Goose perimeter plus detections by date, with a timestamp slider), labelled as observed history.
- Routing is a stretch goal and starts only after spread is validated.
- Simulated outputs are always labelled separately from observed detections.

TODO: team to confirm this decision (simulation shown as what-if, with the 12-fire result in the app's "about" text).

## 8. Shared function and endpoints

Endpoints (from the team contract):
- `GET /api/v1/fires/active`
- `GET /api/v1/fires/perimeters`
- `POST /api/v1/simulations/fire-spread` (optional)

Functions (all exist in `modules/fire_monitoring/` and have tests):
```python
get_active_fires(bbox, start, end, source) -> dict   # layer_type "active_fire", data_kind "observed". Keeps VIIRS confidence n and h, drops l.
get_perimeters(year_from, year_to) -> dict           # layer_type "fire_perimeter", data_kind "observed". Shaver Lake only.
simulate_fire_spread(ignition, target_area_km2, wind_dir_deg, wind_k, seed) -> dict   # layer_type "fire_spread", data_kind "simulated", with simulation_step
```
Wind direction crossing any module or API boundary is the direction the wind blows FROM (`wind_dir_deg`). The conversion to "toward" happens once, inside `simulate_fire_spread`.

Differences from `FIRE_SENTINEL_M3_M4_ALIGNMENT.md` (agreed to keep for now, see `docs/M4_STATUS_FOR_M3.md`):
- Spread is area-matched with no real clock, so the 1, 3 and 6 hour polygons are not available yet (planned after the hourly-wind version).
- `get_active_fires` takes `start`, `end` and `source`, not `hours`. Confidence is kept as VIIRS letters. No `metadata` block yet. The older contract fields (`layer_type`, `feature_id`, `model_version`) are kept next to `data_kind`.
- TODO: align function names and signatures with the notes of the planning deck (slide 14) if they differ.

## Attribution

Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0). Link it wherever Open-Meteo data or results derived from it are shown.

Terrain tiles (slope tests, offline only): AWS Terrain Tiles. TODO: check the data-source attribution at https://registry.opendata.aws/terrain-tiles/ before showing anything derived from them.

We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS), part of NASA's Land, Atmosphere Near real-time Capability for Earth observations (LANCE).
