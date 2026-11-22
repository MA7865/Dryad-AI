# API Contract

All endpoints are under `/api/v1`. Responses are JSON. Map layers are GeoJSON FeatureCollections in EPSG:4326. Timestamps are UTC (ISO 8601). Patch IDs come from `data/grid.geojson`.

---

## M1 - Forest health

All map layers are GeoJSON FeatureCollections (EPSG:4326). Null means "not available" (never 0). The score is relative; it is not a probability and not a diagnosis.

### GET /api/v1/layers/forest-health?period=summer|live
- `summer` (default): latest full summer. `live`: latest 30-day satellite window plus the model score. While the live layer is first being computed the API returns 503 with a retry hint.
- Properties (summer): `patch_id, row, col, center_lon, center_lat, year, period, health_index, health_band, ndvi, ndmi, trend_slope, trend_label, years_used, burn_status, burn_frac, forest_frac, data_quality, model_version, source, data_kind`.
- Properties (live), in addition: `window_start, window_end, observed_at, n_scenes, obs_count, mortality_likelihood, mortality_percentile, mortality_band, model_status, mortality_model_version, mortality_model_window, mortality_climate_year`.
- Colour by `health_band`, `trend_label`, or the continuous `mortality_likelihood` / `mortality_percentile`. Against Sierra-wide cutoffs most Shaver Lake patches are "Lower", so use the continuous value or the percentile for contrast. About 60% of patches are burned and not scored by the model (`model_status`).

### GET /api/v1/layers/forest-health/status
Build times of the summer and live layers, live refresh state (`refreshing`, `error`, `age_minutes`) and the live window.

### GET /api/v1/layers/forest-health/model-card
Training data, evaluation, bands, calibration, feature importance, limitations. 404 if not built.

### GET /api/v1/patches/{patch_id}/forest-health
Click-panel data: summer index, `history` (five summers), trend, and a `live` block (index for the live window plus `mortality_*` fields and notes). 404 for an unknown patch.

Notes for the frontend:
- `mortality_likelihood` is relative to surveyed Sierra forest, not a real-world probability; show the `model_note` text.
- `model_status` is one of: scored, burned_not_scored, too_little_forest, missing_data, too_few_observations.
- Climate inputs use the latest year TerraClimate has (`mortality_climate_year`); show it.
- "Post-fire recovery" means more than half of the patch burned since 2015; it reflects regrowth, not disease. Use a colour different from the stress colours.
- Trend labels are context only; do not present them as damage warnings.