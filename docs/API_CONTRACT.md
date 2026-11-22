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

## M3 - Ignition risk and weather scenarios (PROPOSED, not yet agreed)

All map layers are GeoJSON FeatureCollections (EPSG:4326). Null means "not available" (never 0). The risk score is a relative model estimate for Shaver Lake patches; it is not a calibrated real-world probability, not a fire warning, and not a forecast of a specific fire. Errors use the standard `{"detail": ...}` shape.

### GET /api/v1/layers/ignition-risk?valid_at=<UTC ISO 8601>
- `valid_at` is optional (default: the current forecast window). The score applies to the next `window_hours` hours from `valid_at`.
- Properties: `feature_id, patch_id, row, col, center_lon, center_lat, layer_type, valid_at, window_hours, observed_at, generated_at, risk_score, risk_percentile, risk_band, top_drivers, model_status, model_note, model_version, source, data_kind, data_quality`.
- `layer_type` is `ignition_risk`. `data_kind` is `predicted`. `observed_at` is `null`.
- `risk_score` is 0 to 1, relative to the training region. `risk_percentile` ranks the patch within the 2,061 Shaver Lake patches; use it for map contrast when most patches fall in the lowest band.
- While the model is not trained, every feature has `risk_score: null`, `risk_band: "not_scored"`, `model_status: "not_trained"`, `data_quality: "stub"`.

### GET /api/v1/layers/ignition-risk/status
Build time of the current scores, the weather time they used, model version, `model_status`, and any refresh error.

### GET /api/v1/layers/ignition-risk/model-card
Training region and period, label definition, split, metrics (PR-AUC, calibration), feature importance, limitations. 404 if not built.

### GET /api/v1/patches/{patch_id}/ignition-risk
Click-panel data: score, percentile, band, `top_drivers`, the weather and terrain inputs used (with units), and notes. 404 for an unknown patch.

### GET /api/v1/weather/forecast?hours=48
Hourly numerical weather forecast for the study area (source: Open-Meteo). `data_kind` is `observed`; label it "weather forecast" in the UI. Fields per hour: `time, temp_c, rh_pct, wind_speed_ms, wind_gust_ms, wind_dir_deg, precip_mm, vpd_kpa`. Wind direction is the direction the wind blows FROM. 503 if the service is unreachable (never fabricated values).

### POST /api/v1/simulations/weather
Body: `delta_temp_c`, `delta_wind_pct`, `delta_precip_pct`, optional `valid_at`, optional `patch_ids` (null means all). Returns the same features as the risk layer with `data_kind: "scenario"` plus `baseline_risk_score`, `risk_change` and a `scenario` object echoing the inputs. Humidity is recomputed from the changed temperature, not set directly. 422 for out-of-range inputs.

Notes for the frontend:
- `model_status` is one of: scored, not_trained, missing_weather, missing_terrain, stale_weather.
- Scenario results must carry a visible SCENARIO badge and must not share a style with observed fire layers.
- Do not describe the scenario as a forecast, and do not say a change "causes" fire.
- Show `model_note` and `valid_at` with the layer. Show "Data unavailable" for null values.