# Data Dictionary

Coordinates: EPSG:4326 in all GeoJSON. Distances and areas are computed in EPSG:32611. Timestamps: UTC, ISO 8601. Missing values are `null` (never 0).

---

## M1 - Forest health

| Field | Type | Meaning |
|---|---|---|
| `patch_id`, `row`, `col`, `center_lon`, `center_lat` | | Shared grid identifiers |
| `layer_type`, `data_kind`, `model_version`, `source`, `generated_at` | string | `forest_health`; `derived_index`; index version; datasets; build time |
| `year`, `period` | | Summer shown (June-September); live layer: `window_start`/`window_end` (end exclusive), `observed_at` (newest scene date) |
| `health_index` | integer 0-100, or null | Relative condition score (greenness and moisture versus unburned forest). Null when not scored |
| `health_band` | string | Healthy, Moderate stress, High stress, Post-fire recovery, Not scored |
| `ndvi`, `ndmi` | number or null | Mean over tree pixels (-1 to 1) |
| `trend_slope`, `trend_label` | number, string | Change per year in the score relative to similar patches over five summers; Improving vs peers, Stable vs peers, Declining vs peers, Recovering, Not enough data. Context only |
| `burn_status`, `burn_frac` | string, 0-1 | unburned / partial / mostly_burned; share burned since 2015 (MODIS, 500 m) |
| `forest_frac`, `obs_count` | | Tree-cover share; clear observations per pixel in the window |
| `data_quality` | string | good, limited, not_scored |
| `mortality_likelihood` | 0-1, or null | Model output: relative likelihood that USFS aerial surveys would map tree mortality in the patch |
| `mortality_percentile` | 1-100, or null | Rank of the likelihood among scored patches |
| `mortality_band` | string or null | Lower (below 0.305), Elevated (0.305 up to 0.567), High (0.567 or more); cutoffs from the model card |
| `model_status` | string | scored, burned_not_scored, too_little_forest, missing_data, too_few_observations |
| `mortality_model_version`, `mortality_model_window`, `mortality_climate_year` | | Model version; June-September window scored; climate year used |

### Calculations
- Condition index: NDVI and NDMI of tree pixels are each rescaled between the 5th and 95th percentile of unburned patches (values saved in `data/processed/m1_reference_bounds.json`), then averaged (x100). Bands use the 10% and 30% points of the unburned reference. The live layer is scored against the unburned patches in the same window.
- Mortality likelihood: gradient-boosted trees on 16 features: elevation, slope, aspect (sine, cosine), tree cover, climatic water deficit (water year and previous), summer drought index, NDVI, NDMI, NBR, spread of NDVI and NDMI inside the patch, and the change of NDVI, NDMI and NBR since the previous summer.
- Trend: the score minus the same-year median of unburned patches, a straight-line fit over the latest five summers; labels use +/-1.5 points per year.