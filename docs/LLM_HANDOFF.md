# Dryad-AI / AI Forest Sentinel: LLM Handoff

## Purpose

This repository is a research prototype for an interactive, four-module
wildfire/forest-monitoring application. It is not an emergency alert system.
The study area is Shaver Lake, California.

This document gives a future LLM all context needed to continue work without
assuming previous conversation state.

## Module ownership

- **M1 - Forest Health:** implemented.
- **M2 - Vegetation:** may not have implementation; no `modules/vegetation/`
  directory exists on the current M3 branch/main snapshot.
- **M3 - Ignition Risk:** owned by the current work. Phase 1 is complete.
- **M4 - Fire Monitoring:** active-fire and spread prototype code exists.

Do not modify M1, M2, or M4 source code without explicit permission and an
explanation. M3 may share code only through new files under `modules/shared/`.
Do not regenerate or renumber `data/grid.geojson`.

## Repository state

The current M3 branch is `m3-ignition-risk`. Its upstream is
`origin/m3-ignition-risk`.

Recent M3 commits:

- `3fc3870` - M3 Phase 1 ignition-risk scaffold
- `bd7735d` - LANDFIRE patch static features

Both commits are pushed to `origin/m3-ignition-risk`.

Main branch tip is the M1 merge commit `65149fd`.

Preserve these existing uncommitted or untracked files unless the user
explicitly asks otherwise:

- Modified: `docs/API_CONTRACT.md`
- Untracked: `docs/module_readiness/FIRE_SENTINEL_M3_M4_ALIGNMENT.md`
- Untracked: `docs/module_readiness/M3_AGENT_BRIEF.md`
- Untracked: `docs/module_readiness/M4_STATUS_FOR_M3.md`

Do not commit `.env`, `data/raw/`, `data/training/`, or `data/cache/`.

## Study area and shared conventions

The shared study area is the bounding box:

- West: `-119.50`
- South: `37.00`
- East: `-119.25`
- North: `37.20`

The shared grid is `data/grid.geojson`:

- 2,061 permanent patches
- 500 m x 500 m patches
- Patch IDs use `P_rNNN_cNNN`
- Example: `P_r012_c034`
- Grid/patch IDs must never be renumbered or regenerated

Coordinate conventions:

- GeoJSON/API coordinates: EPSG:4326
- Distance, area, slope and raster aggregation: EPSG:32611 for grid work
- LANDFIRE rasters: EPSG:5070 / NAD83 Albers
- Timestamps: UTC ISO 8601 ending in `Z`
- Missing values: JSON `null` / Python `None`, never zero or NaN
- JSON/Python names: `snake_case`

Every GeoJSON feature should carry:

- `feature_id`
- `patch_id`
- `layer_type`
- `observed_at`
- `generated_at`
- `model_version`
- `source`
- `data_quality`
- `data_kind`

Allowed `data_kind` values:

- `observed`
- `derived`
- `predicted`
- `scenario`
- `simulated`

Do not use a top-level `metadata` block for M3. Do not add a custom error
`code` field. FastAPI errors use `HTTPException(detail="...")`.

## M1 context

M1 is implemented in `modules/forest_health/` and
`backend/app/api/forest_health.py`.

M1 public pattern:

- `get_layer()`
- `get_patch()`
- `get_status()`
- `get_model_card()`
- `reload_data()`
- `lru_cache`
- disk/in-memory caches
- public interface used by the backend

M1 has summer and live forest-health layers. It uses a trained
HistGradientBoosting mortality-likelihood model. The mortality score is
relative to surveyed Sierra forest and must not be presented as a calibrated
probability or diagnosis.

M1 is already registered in the FastAPI app:

- `GET /api/v1/layers/forest-health`
- `GET /api/v1/layers/forest-health/status`
- `GET /api/v1/layers/forest-health/model-card`
- `GET /api/v1/patches/{patch_id}/forest-health`

No M1 code should be changed unless a user explicitly approves it and the
handoff explains why.

## M2 context

M2 is vegetation/disease analysis.

- No `modules/vegetation/` folder exists in the current snapshot.
- `docs/module_readiness/m2.md` is empty.
- M2's remote branch `origin/m2-vegetation` only contained a grid setup in the
  inspected snapshot.

Do not assume M2 has implemented endpoints or interfaces. Ask for the M2
branch/status before integrating M2 output.

## M4 context

M4 code lives in `modules/fire_monitoring/`:

- `get_active_fires(...)`
- `simulate_fire_spread(...)`
- `FirmsError`
- FIRMS download and retry logic
- 90 m cellular-automata fire spread prototype

M4 conventions:

- Active fires are satellite heat detections, not confirmed fires.
- FIRMS confidence is `l`, `n`, or `h`.
- The M4 review asks M3 to use only `n` and `h` for future labels/map filters.
- Dates and acquisition times are UTC.
- Wind direction crossing module/API boundaries is FROM.
- M4 spread converts FROM direction to TOWARD internally using:
  `toward = (from + 180) mod 360`
- Spread output is an area-matched simplified simulation with no real clock.
- `observed_at` and `perimeter_time` are currently `null`.
- M4 output must be visibly separate from observed detections.

M4 fire-spread code and tests are not to be changed in M3 work.

## Current M3 implementation

### Branch and commits

Branch:

- `m3-ignition-risk`
- Tracks `origin/m3-ignition-risk`

Phase 1 commits:

- `3fc3870`: M3 scaffold, shared grid, shared weather client, API stubs
- `bd7735d`: LANDFIRE static table generation and backend/schema updates

### M3 files

Backend:

- `backend/app/api/ignition_risk.py`
- `backend/app/api/weather.py`
- `backend/app/schemas/ignition_risk.py`
- `backend/app/main.py` registers the M3 routers

M3 interface:

- `modules/ignition_risk/interface.py`
- `modules/ignition_risk/features.py`
- `modules/ignition_risk/scenario.py`
- `modules/ignition_risk/__init__.py`

Shared M3 code:

- `modules/shared/grid.py`
- `modules/shared/weather.py`
- `modules/shared/__init__.py`

Static data:

- `scripts/build_patch_static_features.py`
- `data/processed/patch_static_features.csv`

Tests:

- `tests/test_m3_contracts.py`
- `tests/fixtures/open_meteo_forecast.json`

Documentation:

- `docs/module_readiness/m3.md`
- `docs/module_readiness/M3_AGENT_BRIEF.md`
- `docs/module_readiness/FIRE_SENTINEL_M3_M4_ALIGNMENT.md`
- `docs/module_readiness/M4_STATUS_FOR_M3.md`
- `docs/DATA_SOURCES.md`

### Public M3 interface

`modules/ignition_risk/interface.py` provides:

- `get_risk_layer(valid_at=None)`
- `get_patch_risk(patch_id)`
- `run_scenario(...)`
- `get_forecast(hours=48)`
- `get_status()`
- `reload_data()`

Route handlers should remain thin. Business logic belongs in
`modules/ignition_risk/interface.py`, not in the route files.

### M3 API endpoints

- `GET /api/v1/layers/ignition-risk`
- `GET /api/v1/layers/ignition-risk/status`
- `GET /api/v1/patches/{patch_id}/ignition-risk`
- `GET /api/v1/weather/forecast?hours=48`
- `POST /api/v1/simulations/weather`

Pydantic schemas are in `backend/app/schemas/ignition_risk.py`.

The ignition-risk API is a stub, not a trained model:

- `risk_score`: `null`
- `risk_percentile`: `null`
- `risk_band`: `not_scored`
- `top_drivers`: `null`
- `model_status`: `not_trained`
- `model_version`: `m3-stub`
- `data_quality`: `stub`
- `data_kind`: `predicted` for baseline or `scenario` for what-if
- `observed_at`: `null`
- `model_note`: explains that no model is trained

The scenario endpoint expects:

- `delta_temp_c`
- `delta_wind_pct`
- `delta_precip_pct`
- optional `valid_at`
- optional `patch_ids`

Proposed/alignment ranges:

- Temperature: `-10` to `10` C
- Wind: `-50%` to `100%`
- Precipitation: `-100%` to `100%`

Invalid values return HTTP 422 with a plain `detail` message.

## Shared grid behavior

`modules/shared/grid.py`:

- loads `data/grid.geojson`
- sorts by `patch_id`
- caches with `lru_cache`
- exposes `load_grid()`
- exposes `point_to_patch_id(lon, lat)`

Point lookup matches M4 behavior:

- spatial join predicate: `intersects`
- point exactly on an edge may match two patches
- the first alphabetically sorted patch ID wins

Do not rewrite M4's grid lookup; M4 may later switch to this shared helper.

## Shared weather client

`modules/shared/weather.py` fetches Open-Meteo:

- Forecast endpoint: `https://api.open-meteo.com/v1/forecast`
- Archive/ERA5 endpoint:
  `https://archive-api.open-meteo.com/v1/archive`

Requested data:

- `temp_c`
- `rh_pct`
- `wind_speed_ms`
- `wind_gust_ms`
- `wind_dir_deg`
- `wind_toward_deg`
- `precip_mm`
- `vpd_kpa`
- `precip_24h_mm`
- `precip_7d_mm`
- `precip_30d_mm`

Exact units:

- Temperature: C
- Relative humidity: %
- Wind: m/s at 10 m
- Precipitation: mm
- VPD: kPa

Wind direction:

- `wind_dir_deg` is FROM
- `wind_toward_deg = (wind_dir_deg + 180) mod 360`

Open-Meteo documentation was checked for the parameter names, wind speed unit,
UTC timezone, VPD, and wind direction. VPD is requested directly and falls back
to this standard formula if missing:

- `es = 0.6108 * exp(17.27 * T / (T + 237.3))`
- `vpd = es * (1 - RH / 100)` kPa

`WeatherError` is the custom failure class. Network failures, HTTP failures,
retry exhaustion, and unusable Open-Meteo responses must raise it rather than
return fabricated weather.

Offline tests use `tests/fixtures/open_meteo_forecast.json`.
The live weather test is optional and disabled unless explicitly enabled.

## Static terrain and fuel data

LANDFIRE rasters are now downloaded under `data/raw/landfire/`. This directory
is gitignored and must not be committed.

One folder per layer:

- `LF2020_Elev_CONUS`
- `LF2020_SlpD_CONUS`
- `LF2020_Asp_CONUS`
- `LF2025_FBFM40_CONUS`
- `LF2025_CC_CONUS`
- `LF2025_CH_CONUS`
- `LF2025_CBH_CONUS`
- `LF2025_CBD_CONUS`

All eight clipped rasters share:

- CRS EPSG:5070
- 30 m pixels
- same dimensions and extent
- native bounds matching the study area

Each downloaded layer folder contains:

- `.tif`
- `.tif.vat.dbf` for raster attribute values
- `metadata.xml`
- `output_parameters.txt`
- local GIS sidecars (`.dbf`, `.prj`, `.shp`, `.shx`, `.tfw`, `.ovr`,
  `.GeoJSON`) as produced by the viewer/download

Observed folder sizes are approximately:

- `LF2020_Elev_CONUS`: 3.80 MB
- `LF2020_SlpD_CONUS`: 3.42 MB
- `LF2020_Asp_CONUS`: 3.44 MB
- `LF2025_FBFM40_CONUS`: 3.47 MB
- `LF2025_CC_CONUS`: 3.44 MB
- `LF2025_CH_CONUS`: 3.46 MB
- `LF2025_CBH_CONUS`: 3.57 MB
- `LF2025_CBD_CONUS`: 3.48 MB

These raw files are local-only. Do not add `data/raw/landfire/` to Git.

The static table currently uses:

- Elevation = LF2020 Elevation mean in metres
- Slope = LF2020 Slope Degrees mean in degrees
- Aspect = LF2020 Aspect circular mean, excluding `-1` flat pixels
- Fuel = most common LF2025 FBFM40 numeric code

Source/version/licensing:

- LF2020 Elevation/Slope/Aspect: USGS/LANDFIRE LF 2020
- Elevation DOI: `10.5066/P1LJEZ3G`
- LF2025 FBFM40: USGS/LANDFIRE LF 2025
- FBFM40 DOI: `10.5066/P1MAAYLC`
- LF2025 metadata says Creative Commons CC0 1.0 / public domain

The generated table is:

- `data/processed/patch_static_features.csv`
- 2,061 rows
- exactly 2,061 unique patch IDs
- columns:
  `patch_id, elev_m, slope_deg, aspect_deg, fuel_model, fuel_source`
- 10 patches have `aspect_deg = null` because no valid directed aspect pixels
  were found

Rebuild command:

```bash
python scripts/build_patch_static_features.py
```

The script can also accept explicit:

- `--dem`
- `--slope`
- `--aspect`
- `--landfire`

Raster aggregation:

- Elevation: mean valid-pixel elevation
- Slope: mean valid-pixel slope
- Aspect: circular mean of `0` to `359`; `-1` is flat and excluded
- Fuel: most common FBFM40 code
- No valid aspect: `null`
- Missing values: `null`

The canopy and extra FBFM40 rasters are downloaded but are not yet incorporated
into the static table.

## Static raster encodings

Elevation:

- valid range observed: 275–2346 m
- nodata: `-9999`

Slope:

- observed valid clipped values: `0–65`
- values are degrees
- TIFF metadata has a signed-16/unsigned-16 ambiguity for nodata
- script masks `32767`, `65535`, and Rasterio nodata

Aspect:

- valid range: `-1` through `359`
- `-1`: flat
- `0`: north
- `90`: east
- `180`: south
- `270`: west
- nodata: `-9999`

FBFM40:

- numeric Scott and Burgan fuel-model codes
- clipped common values include 91/93/98/99/101/102/121/122/141/142/144/145
- TIFF nodata: `32767`
- DBF Fill-NoData: `-9999`
- Names include NB, GR, GS, SH, TU, TL, and SB classes

Canopy rasters:

- CC `0` = non-forested
- CH `0` = non-forested
- CBH `0` = non-forested
- CBD `0` = non-forested
- TIFF nodata: `32767`
- DBF Fill-NoData: `-9999`

## Dependencies

The project requirement file is `requirements.txt`.

It includes:

- geopandas
- pyogrio
- shapely
- pyproj
- pandas
- numpy
- requests
- python-dotenv
- fastapi
- uvicorn
- httpx
- pytest
- ipykernel
- matplotlib
- earthengine-api
- scikit-learn pinned to `1.9.1`
- joblib pinned to `1.6.0`
- rasterio pinned as `rasterio>=1.4.3`

A virtual environment exists at `.venv/`.

- Python executable: `.venv/Scripts/python.exe`
- Python: 3.14.2
- Base interpreter: `C:\Users\ADMIN\AppData\Local\Programs\Python\Python314\python.exe`
- The venv is isolated: `include-system-site-packages = false`
- Rasterio: 1.5.2
- GeoPandas: 1.2.0
- Pandas: 3.1.1
- NumPy: 2.5.5
- PyProj: 3.8.0
- Shapely: 2.2.0
- FastAPI: 0.165.0
- Pydantic: 2.14.4
- Pytest: 9.2.0

The venv successfully opens and processes the LANDFIRE rasters with Rasterio.
It is recommended for rebuilding the static table:

```powershell
.venv\Scripts\python.exe scripts\build_patch_static_features.py
```

On this Windows machine, Pydantic DLL loading in the venv was blocked once by
application control during test collection. The system Python remains available
for FastAPI/test validation if the venv shows the same environment-specific
block.

No XGBoost dependency is currently added. It is Phase 2 only.

## Tests

Run:

```bash
python -m pytest tests -v
```

Before the static-table work, validation reached 67 passed and 5 skipped.
After static-table generation and M3 contract updates, validation reached
68 passed and 5 skipped.

M3 tests cover:

- shared grid matches M4 grid
- shared point lookup
- FROM/TOWARD wind conversion
- nearest-point assignment
- offline weather fixture
- 2,061 M3 stub features
- patch IDs exist in grid
- stub values remain null
- scenario 422 ranges
- scenario patch filtering
- static table has 2,061 unique patch IDs
- static slope/aspect ranges
- no known nodata sentinels

## Work completed

1. Created branch `m3-ignition-risk`.
2. Created shared grid and weather modules.
3. Created M3 interface/scenario feature placeholders.
4. Registered M3 FastAPI routers.
5. Added Pydantic schemas and response models.
6. Added explicit M3 stub endpoints.
7. Added offline weather fixture and tests.
8. Inspected all downloaded LANDFIRE rasters.
9. Added and ran static-feature builder.
10. Generated `data/processed/patch_static_features.csv`.
11. Updated M3 readiness and data-source documentation.
12. Pushed both M3 commits to origin.

## Known conflicts and unresolved decisions

These conflicts are intentionally not silently resolved:

- Alignment/M4 status propose top-level metadata and custom error `code` fields.
  The brief and existing M1/M4 code win: M3 uses feature properties and plain
  `HTTPException(detail=...)`, without those fields.
- Alignment/M4 status mention M4 API routes in `backend/app/api/fires.py`, but
  that file was not present in the inspected snapshot. Do not assume M4 APIs
  exist unless verified in the current branch.
- `docs/API_CONTRACT.md` has a local M3 addition, but it remains a local edit
  and not a committed M3 change.
- The alignment status calls the model XGBoost/LightGBM, while the M1 pattern
  uses HistGradientBoosting. Phase 2 must compare and wait for owner approval.
- The exact DEM source/license/resolution was selected by the M4-style handoff
  as Elevation, not an external DEM. The static table now uses the LANDFIRE
  LF2020 Elevation raster.
- The FBFM40 table is currently used only as the numeric fuel class. CANOPY
  CC/CH/CBH/CBD are not included in the static table.
- Fire labels, training region, split, positive/negative sampling, calibration,
  and FIRMS request limits remain undecided.
- 1/3/6 hour spread horizons and scenario carry-over to M4 spread are out of
  Phase 1 scope.

## Phase 2: what an LLM must do next

Do not start Phase 2 until explicitly instructed.

Before downloading/training:

1. Re-read the M3 agent brief.
2. Propose a Sierra Nevada training bounding box.
3. Define label rules.
4. Define positive and negative sampling.
5. Estimate full FIRMS request volume and confirm NASA limits.
6. Propose time splits.
7. Propose metrics and baselines.
8. Wait for owner approval.

Phase 2 will require:

- training scripts analogous to M1
- historical FIRMS labels
- no random split
- class weights
- baselines before model comparison
- PR-AUC, precision/recall, calibration
- model card JSON
- live risk API wiring
- humidity/VPD recomputation for scenarios
- honest M3 model evaluation documentation

## Manual owner actions

- No FIRMS key is needed for completed Phase 1 work.
- M3 Phase 2 will need `FIRMS_MAP_KEY` in `.env`.
- Keep `.env` local and gitignored.
- Raw perimeter/FIRMS data belongs under `data/raw/` or `data/training/`.
- The LANDFIRE data is already present locally; do not commit it.
- The 2025 canopy rasters are already downloaded but have no integration task
  until explicitly assigned.
- Owner approval is needed before:
  - changing M1/M2/M4 code
  - committing or using a historical training label dataset
  - adding XGBoost
  - running a large multi-year FIRMS download
  - selecting the final model

## Safe first prompt for a future LLM

Use this prompt:

> Read `docs/LLM_HANDOFF.md`, `docs/STUDY_AREA.md`,
> `docs/module_readiness/M3_AGENT_BRIEF.md`,
> `docs/module_readiness/FIRE_SENTINEL_M3_M4_ALIGNMENT.md`, and
> `docs/module_readiness/M4_STATUS_FOR_M3.md`. Work on
> `m3-ignition-risk`. Do not modify M1/M2/M4 code. Do not download or train
> in Phase 2 without explicit approval. Preserve uncommitted local files.
