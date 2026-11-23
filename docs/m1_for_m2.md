# M1 (Forest Health) - handoff note for M2 (updated)

Written by M1 for M2, so you can reuse what works and avoid what cost us time.
Status: [branch m1/forest-health, pull request OPEN / MERGED - fill in]. Last updated: [date].

## 1. What M1 has built (working today)

- **Condition index per patch** (0-100, relative to unburned forest), a band (Healthy / Moderate stress / High stress / Post-fire recovery / Not scored), NDVI, NDMI and a 5-summer trend (2022-2026).
- **Live layer:** the latest 30 days of Sentinel-2, computed from Google Earth Engine in the background (refreshed every 6 hours) and served from memory. Nothing generated is stored in Git.
- **Mortality-likelihood model (new):** a gradient-boosted model trained on 15,457 USFS survey polygons across the Sierra Nevada (2021-2024). It scores each unburned Shaver Lake patch with a likelihood and a band (Lower / Elevated / High), using features computed live from Earth Engine for the latest completed summer.
- **API** (try at `/docs` after `uvicorn backend.app.main:app --reload`):
  - `GET /api/v1/layers/forest-health?period=summer|live`
  - `GET /api/v1/layers/forest-health/status`
  - `GET /api/v1/layers/forest-health/model-card` (training data, metrics, calibration, limits)
  - `GET /api/v1/patches/{patch_id}/forest-health` (click panel: index, history, trend, live block with the model score)
- **Tests:** `python -m pytest` (the live Earth Engine test runs only with `M1_LIVE_TEST=1`).

## 2. Results so far
Details: `docs/M1_MODEL_CARD.md`. Labels: USFS mortality polygons (15,457, 2021-2024); Shaver Lake never used in training.
- Held-out 20 km blocks: AUC 0.78 (0.77-0.80). Top 10% of patches flagged: 69% damaged vs 25% overall.
- Shaver Lake never seen: AUC 0.71 (683 patches, 99 damaged).
- Terrain and climate give most of the skill; satellite features add about +0.01 AUC.
- The condition index does not flag surveyed damage (AUC 0.18 in the small Shaver box); the 5-summer trend is weak (AUC 0.54 / 0.61). Treat both as context.
- Climate inputs use the latest year TerraClimate has (2024); the API reports it.
- Prithvi-EO-2.0 loads and runs fast; no comparison was run.

## 3. What you can reuse

| Piece | Where | Use |
|---|---|---|
| One definition of the satellite/terrain/climate features | `modules/forest_health/features_gee.py` (`cell_features`) | One row per cell for any year; keep training and serving identical |
| Live window features per patch | `modules/forest_health/live_gee.py` | NDVI/NDMI/NBR, tree share, burn share, clear observations |
| Live-refresh pattern | `live_service.py`, `refresh.py` | Background refresh, in-memory cache, retry pause |
| Summer feature table 2022-2026 (Shaver) | `data/processed/m1_features_summers.csv` (committed) | Ready-made inputs |
| Sierra-wide training sample and features | `data/training/` (**not** in Git) | Regenerate: `scripts/fetch_ids_sierra.py`, `make_training_cells.py`, `extract_training_features.py` (about 30 minutes) |
| Label counts and downloads | `scripts/count_ids_sierra.py`, `scripts/fetch_ids_sierra.py` | USFS survey polygons; download once and share |
| Model and card | `models/m1_mortality_hgb.joblib`, `data/processed/m1_model_card.json` | Pin scikit-learn (see requirements.txt) |

Conventions: patch IDs from `data/grid.geojson`; GeoJSON in EPSG:4326; `layer_type`, `model_version`, `data_kind` and `generated_at` in outputs; null (never 0) when missing.

## 4. Setup on Windows

1. Python 3.11 or 3.12 is safer than 3.10.0.
2. `pip install -r requirements.txt`
3. Earth Engine: `python -c "import ee; ee.Authenticate()"`, set `EE_PROJECT` to your own project.
4. Build the summer layer: `python -m modules.forest_health.build_outputs`
5. Run: `uvicorn backend.app.main:app --reload`, open http://127.0.0.1:8000/docs
6. Without Earth Engine access the API serves the summer layer; the live layer returns a 503 message. `M1_LIVE=off` disables live calls.

## 5. Lessons (please read before building your layer)

1. **Burned areas dominate everything** (about 55% of the Shaver box burned since 2015). Keep a burn flag; treat burned patches separately.
2. **Forest type confounds greenness.** Compare like with like; add terrain and climate as inputs.
3. **Test on places and years the model has not seen.** Random splits leak: neighbouring cells look alike. We held out whole 20 km blocks.
4. **A terrain-and-climate-only baseline is essential.** It showed that satellite features add little at 500 m.
5. **All summers rise together** (fire recovery plus weather); measure trends relative to same-year peers.
6. **Season matters.** Autumn and winter scenes are not comparable with summer composites.
7. **"Valid pixel share" misleads for median composites;** use the number of clear observations.
8. **USFS survey caveats:** aerial sketches, partly generalized, no accuracy assessment, **no layer showing where aircraft flew**, 2025 incomplete. Sierra-wide 2021-2024: 15,457 polygons, 68% fir engraver, 98% mortality.
9. **The burn flag is coarse** (MODIS 500 m); CAL FIRE perimeters would be sharper.
10. **Practical:** no generated files in Git (use `data/cache/`); a root `conftest.py` lets `pytest` import the project; use `python -m scripts.xxx`; on Windows avoid backslashes in Python path strings.

## 6. Where M1 and M2 may overlap (please agree)

- **Trajectory / change over time:** M1 serves a 5-summer trend per patch. If M2 also does change over time, decide who owns it.
- **Anomaly flag:** M2's. M1 does not produce one.
- **Observed damage layer:** M1 uses the USFS polygons for training and validation. Download once and share the file.
- **Vegetation type:** M1 only uses a tree/no-tree mask.
- **Naming:** "Health Index" may be renamed "Relative Condition Index", because it is not validated as health.

## 7. Known limits

- The model score applies to the latest completed summer; the live index uses the last 30 days. They are not comparable.
- The likelihood is relative to surveyed forest, not a real-world probability. Burned and low-forest patches are not scored.
- Climate inputs arrive weeks late (TerraClimate).

## 8. Contact

[M1 name/contact]. Ask before duplicating work: Earth Engine setup, the grid, label sources.