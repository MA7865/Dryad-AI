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


---

## M2 — Vegetation Intelligence API

### Endpoint

`GET /api/v1/layers/vegetation`

Returns a GeoJSON FeatureCollection containing
LANDFIRE vegetation classifications, Sentinel-2
vegetation indices, historical anomaly measurements,
burn information, and exploratory anomaly detections.

**Current supported period:** Summer 2026.

**Coordinate reference system:** WGS84 (EPSG:4326).

**Grid:** 2,061 polygons from `data/grid.geojson`.

**Patch identifiers:** Shared `patch_id` values.

### Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `patch_id` | Repeated string | No | Filter by one or more patch IDs |
| `as_of` | String | No | Only `2026` is currently supported |

Examples:

- `/api/v1/layers/vegetation`
- `/api/v1/layers/vegetation?as_of=2026`
- `/api/v1/layers/vegetation?patch_id=P_r000_c023`

For multiple patches, repeat the parameter:

`?patch_id=P_r000_c023&patch_id=P_r000_c024`

### Response Format

HTTP 200 returns a GeoJSON FeatureCollection.

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": []
      },
      "properties": {
        "patch_id": "P_r000_c023",
        "vegetation_class": null,
        "NDVI": 0.5071,
        "NDMI": -0.0176,
        "anomaly_detected": null,
        "detection_status": "not_evaluated"
      }
    }
  ]
}
```

This example is abbreviated. Real responses contain
complete polygon coordinates and additional properties.

### Main Property Groups

**Vegetation classification**

- `vegetation_class`: LANDFIRE EVT class name or null
- `vegetation_code`: LANDFIRE EVT code or null
- `class_shares`: Vegetation class proportions
- `coverage_fraction`: Reference raster coverage
- `valid_pixel_count`: Number of valid reference pixels

**Satellite measurements**

- `NDVI`: Sentinel-2 greenness index
- `NDMI`: Sentinel-2 moisture index
- `obs_count`: Observation-count metric
- `year`: Satellite measurement year
- `window_start`: Acquisition period start
- `window_end`: Acquisition period end

**Historical change measurements**

- `ndvi_anomaly`: Adjusted NDVI change or null
- `ndmi_anomaly`: Adjusted NDMI change or null
- `anomaly_status`: Eligibility and exclusion context
- `anomaly_eligible`: Whether statistical detection is
  permitted for the patch

**Statistical anomaly detection**

- `anomaly_detected`: true, false, or null
- `detection_status`: Detection outcome
- `ndvi_flag`: NDVI negative-change flag or null
- `ndmi_flag`: NDMI negative-change flag or null
- `ndvi_threshold`: Historical class threshold or null
- `ndmi_threshold`: Historical class threshold or null
- `anomaly_method`: Statistical method identifier

`detection_status` has three possible values:

| Value | Interpretation |
|---|---|
| `negative_change_flagged` | Unusually negative NDVI and/or NDMI change |
| `not_flagged` | Evaluated; neither index crossed its threshold |
| `not_evaluated` | No reliable detection decision was produced |

When `detection_status` is `not_evaluated`,
`anomaly_detected` is JSON null, not false.

A negative-change flag is **not** a confirmed
disease diagnosis or verified forest disturbance.

**Burn and forest context**

- `burn_frac`: Fraction of patch classified as burned
- `forest_frac`: Fraction of patch classified as forest
- `burned_flag`: Burn-affected indicator
- `burn_status`: Burn category

**Quality indicators**

- `vegetation_data_quality`: LANDFIRE reference quality
- `satellite_data_quality`: Satellite measurement availability
- `anomaly_data_quality`: Historical anomaly quality
- `data_quality`: Combined backward-compatible quality label

**Provenance**

- `vegetation_source`: Reference vegetation dataset
- `satellite_source`: Satellite measurement source
- `anomaly_source`: Historical anomaly source
- `generated_at`: Layer generation timestamp
- `processing_version`: Pipeline processing identifier
- `prediction_kind`: Vegetation classification method
- `model_version`: Null; no trained M2 prediction model
- `damage_class`: Null; damage classification not implemented

### Anomaly Detection Method

The current detector is exploratory and statistical,
not a pretrained machine-learning model.

1. Historical NDVI and NDMI data come from the
   consistent M1 summer dataset for 2022–2026.
2. Historical baseline years precede the target year.
3. Anomaly values are adjusted using regional
   unburned, sufficiently forested reference patches.
4. Vegetation-specific negative-change thresholds
   are calibrated using 2024 and 2025 backtest values.
5. For 2026, a patch is flagged when NDVI or NDMI
   falls below its corresponding class threshold.
6. Burn-affected, unsuitable, missing-data, or
   unsupported vegetation-class patches are not
   evaluated.

Thresholds are provisional 5th-percentile cutoffs.

The current detector has not been independently
validated against confirmed disturbance labels.
Historical burn-mask timing may introduce leakage
into retrospective evaluation.

### Current 2026 Dataset Summary

| Result | Patches |
|---|---:|
| Total grid patches | 2,061 |
| Eligible for anomaly detection | 754 |
| Evaluated with calibrated class thresholds | 724 |
| Negative-change flagged | 93 |
| Evaluated, not flagged | 631 |
| Not evaluated | 1,337 |

These counts describe the current generated dataset,
not guaranteed values for future refreshed layers.

### HTTP Status Codes

| Status | Meaning |
|---|---|
| 200 | Successful GeoJSON response |
| 400 | Unsupported year or unknown patch ID |
| 422 | Invalid query parameter structure |
| 503 | Precomputed vegetation layer unavailable |

### Implementation

- API router: `backend/app/api/vegetation.py`
- Response schema: `backend/app/schemas/vegetation.py`
- Python interface: `modules/vegetation/vegetation.py`
- Anomaly calculations: `modules/vegetation/anomaly.py`
- Statistical detector: `modules/vegetation/detection.py`
- Layer builder: `scripts/m2_build_vegetation_layer.py`
- Output: `data/processed/vegetation/vegetation.geojson`

The endpoint serves precomputed GeoJSON. It does not
request fresh Google Earth Engine imagery on each call.
