# API Contract

All endpoints are under `/api/v1`. Responses are JSON. Map layers are GeoJSON FeatureCollections in EPSG:4326. Timestamps are UTC (ISO 8601). Patch IDs come from `data/grid.geojson`.

---

## M1 - Forest health

Data kind: **derived index from observed satellite data**. It is not a model prediction, and it has no probabilities.

### GET /api/v1/layers/forest-health
All 2,061 patches for the latest summer (currently 2026), for colouring the map.

- **Inputs:** none.
- **Response:** GeoJSON FeatureCollection. Each feature is the patch polygon with these properties: `patch_id`, `row`, `col`, `center_lon`, `center_lat`, `layer_type`, `year`, `period`, `observed_at`, `generated_at`, `model_version`, `source`, `data_kind`, `health_index`, `health_band`, `ndvi`, `ndmi`, `trend_slope`, `trend_label`, `years_used`, `burn_status`, `burn_frac`, `forest_frac`, `data_quality`. Field meanings are in `DATA_DICTIONARY.md`.
- **Colour by:** `health_band`.
- **Missing values:** `health_index`, `ndvi`, `ndmi` and `trend_slope` are `null` when `health_band` is "Not scored". Show "Data unavailable", not zero.

### GET /api/v1/patches/{patch_id}/forest-health
Everything the click panel needs for one patch, including its score for each summer.

- **Inputs:** `patch_id` in the path, for example `P_r000_c024`.
- **Response 200:**
```json
{
  "patch_id": "P_r000_c024",
  "year": 2026,
  "period": "2026-06-01/2026-09-30",
  "health_index": 33,
  "health_band": "Healthy",
  "ndvi": 0.513,
  "ndmi": -0.005,
  "trend_label": "Stable vs peers",
  "trend_slope": -0.7,
  "burn_status": "unburned",
  "data_quality": "good",
  "explanation": "Greenness and moisture are within the normal range of unburned forest in this area (not among the lowest 30%). The score is relative to unburned forest in the Shaver Lake area, not an absolute measure of tree health.",
  "model_version": "m1-index-v1",
  "source": "Sentinel-2 SR Harmonized; ESA WorldCover v200; MODIS MCD64A1",
  "data_kind": "derived_index",
  "history": [
    {"year": 2022, "health_index": 27, "health_band": "Healthy", "ndvi": 0.488, "ndmi": -0.02},
    {"year": 2023, "health_index": 55, "health_band": "Healthy", "ndvi": 0.571, "ndmi": 0.086},
    {"year": 2024, "health_index": 47, "health_band": "Healthy", "ndvi": 0.544, "ndmi": 0.054},
    {"year": 2025, "health_index": 44, "health_band": "Healthy", "ndvi": 0.534, "ndmi": 0.049},
    {"year": 2026, "health_index": 33, "health_band": "Healthy", "ndvi": 0.513, "ndmi": -0.005}
  ]
}
```
- **Response 404:** `{"detail": "Unknown patch_id: NOPE"}`
- **Response 422:** standard FastAPI validation error.

### Notes for the frontend
- The score is **relative** to unburned forest in this area. Do not label it a probability or an absolute health measure.
- "Post-fire recovery" means more than half the patch burned since 2015. The score reflects regrowth, not disease. Use a colour different from the stress colours.
- Data is rebuilt offline (`python -m modules.forest_health.build_outputs`), so values change only when the outputs are regenerated.
- Trend labels describe change relative to similar patches. They have not been shown to track surveyed damage, so do not present them as disease or decline warnings.

