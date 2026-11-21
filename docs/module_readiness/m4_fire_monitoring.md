# M4 Module Readiness: Fire Monitoring + Fire Spread

Owner: Romaisa Kashif (M4)
Last updated: 2026-11-18 (Week 2)
Study area and grid: see `docs/STUDY_AREA.md` (Shaver Lake, 500 m grid, `data/grid.geojson`).

Items marked `TODO` still need a value from the owner or a team decision.

## Status at a glance

| Part | Status |
|---|---|
| FIRMS access (key, request, sample saved) | Tested, works |
| FIRMS historical test (Goose fire, 2016) | Tested, works |
| CAL FIRE perimeters loaded and clipped to the study area | Tested, works |
| `get_active_fires(...)` and `active_fire` GeoJSON fixture | Done, tested (`tests/fixtures/active_fire.json`) |
| Fire-spread simulation | Version 0 (no wind) and Version 1a (wind) prototyped and scored on Goose. No slope or fuel yet. |
| `fire_spread` fixture and `simulate_fire_spread(...)` | TODO (next) |
| `get_fire_perimeters(...)` | TODO |
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
    "data_quality": "good",
    "detection_id": "TODO",
    "confidence": "n",
    "detection_time": "2016-08-01T09:12:00Z",
    "satellite_source": "VIIRS_SNPP_SP"
  }
}
```
The real fixture is `tests/fixtures/active_fire.json` (8 detections per date, Goose 2016). TODO: replace the placeholders in the example above with the first feature of that file.

**Spread input and output (Version 1a, current prototype):**
- Input: perimeter polygon (for the target area), ignition point, wind direction (degrees, direction the wind blows toward), wind strength k, random seed.
- Output: set of burned 90 m cells. Not yet in the shared GeoJSON format (`simulate_fire_spread` will do that conversion).

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
| Unit tests | 31 pass (FIRMS client, contract, simulation, wind). |
| Spread simulation, Version 0 (no wind), western-tip start | IoU 0.106 |
| Spread simulation, Version 1a (wind from dry hours, k = 2), western-tip start | **IoU 0.487** |

**Baseline for spread:** a round fire of the same area, centred on the same start point: IoU **0.108**. Wind from the weather data raises it to 0.487. The full tables, method and limitations are in `docs/MODEL_EVALUATION.md`.

Caveat: k was tuned on Goose, and the area is given to the model. This is one fire, so it shows the idea can reproduce Goose, not that it generalises.

## 6. Run time, memory and API limits

- Run time: 90 spread simulations take 0.6 s on a laptop (Python 3.14.4). The 31 unit tests run in about 1.1 s. Memory not measured.
- Run time of the data scripts (`fetch_firms_sample.py`, `fetch_goose_firms.py`, `list_fires_in_box.py`): TODO (time them).
- Perimeter file: about 249.5 MB. The scripts read only the features near the study area, not the whole file.
- Grid file: about 880 KB (2,061 cells).
- FIRMS limits: one area request covers 1 to 5 days. Third-party FIRMS tool documentation reports a budget of 5,000 transactions per 10 minutes and a cap of 500 hotspots per point query. TODO: confirm both on NASA's API page.
- Open-Meteo: free, no key. TODO: check its usage limits and terms, and confirm the wind-direction convention ("from" or "toward") in its documentation.

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
9. CAL FIRE's published Goose ignition point lies 725 m outside the perimeter, so the ignition location is uncertain. The score depends on it most in Version 0 (no wind). With wind it is robust to the start within about 600 m, except to the south (issue 14).
10. Wind data is about 10 km resolution. Direction is usable, speed is probably underestimated.
11. The result is very sensitive to wind direction (90 deg gives 0.51, 120 deg gives 0.15).
12. The model is given the real fire area and has no real clock, so it shows shape and direction, not fire size or timing.
13. The wind-strength parameter k was tuned on the same fire it is scored on, and the dry-hours wind filter (humidity below 25 %) was chosen after seeing results.
14. IoU on the final shape does not identify the ignition point. Starts up to 600 m north, east or west of the snapped tip score about the same (0.44 to 0.51), including starts outside the real perimeter. Starts to the south score lower (0.27 to 0.42).

**Fallback decision (proposed)**
- If the spread simulation cannot beat the baseline on IoU by the end of Week 4's evaluation, ship **historical event playback**: Goose perimeter plus detections by date, with a timestamp slider, clearly labelled as observed history.
- Routing is a stretch goal and starts only after spread is validated.
- Simulated outputs are always labelled separately from observed detections.

TODO: team to confirm the Week 4 decision point.

## 8. Shared function and endpoints

Endpoints (from the team contract):
- `GET /api/v1/fires/active`
- `GET /api/v1/fires/perimeters`
- `POST /api/v1/simulations/fire-spread` (optional)

Functions. TODO: align `get_fire_perimeters` and `simulate_fire_spread` with the signatures in the notes of the planning deck (slide 14) before merging.
```python
get_active_fires(bbox, start, end, source) -> dict      # EXISTS in modules/fire_monitoring/. GeoJSON FeatureCollection, layer_type "active_fire"
get_fire_perimeters(bbox, start, end) -> dict           # TO DO. GeoJSON FeatureCollection of historical perimeters
simulate_fire_spread(ignition, start_time, hours, weather) -> dict   # TO DO. layer_type "fire_spread", with simulation_step
```
Each returns a validated dictionary matching the shared GeoJSON schema, with a fixture in `tests/fixtures/`. Only `active_fire.json` exists so far.

## Attribution

We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS), part of NASA's Land, Atmosphere Near real-time Capability for Earth observations (LANCE).