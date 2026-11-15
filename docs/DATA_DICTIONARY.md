# Data Dictionary

Coordinates: EPSG:4326 in all GeoJSON. Distances and areas are computed in EPSG:32611. Timestamps: UTC, ISO 8601. Missing values are `null` (never 0).

---

## M1 - Forest health

| Field | Type | Meaning |
|---|---|---|
| `patch_id` | string | Patch ID from the shared grid, e.g. `P_r012_c034` |
| `row`, `col` | integer | Grid row (0 = south) and column (0 = west) |
| `center_lon`, `center_lat` | number | Patch centre, degrees |
| `layer_type` | string | Always `forest_health` |
| `year` | integer | Summer the values describe (latest: 2026) |
| `period` | string | Date range of the summer composite, 1 June to 30 September |
| `observed_at` | string | Nominal end date of the composite (30 September, 00:00 UTC). Not a single acquisition time |
| `generated_at` | string | When the file was built, UTC |
| `model_version` | string | `m1-index-v1` |
| `source` | string | Datasets used |
| `data_kind` | string | `derived_index` (calculated from observed satellite data) |
| `health_index` | integer 0-100, or null | Relative condition score. Higher = greener and moister compared with unburned forest in this area. Null when not scored |
| `health_band` | string | `Healthy`, `Moderate stress`, `High stress`, `Post-fire recovery` or `Not scored` |
| `ndvi` | number, or null | Mean NDVI (B8, B4) over the patch's tree pixels. Range -1 to 1 |
| `ndmi` | number, or null | Mean NDMI (B8, B11) over tree pixels. Related to canopy moisture. Range -1 to 1 |
| `trend_slope` | number, or null | Change in `health_index` per year relative to similar patches, over the latest 5 summers (needs at least 4). Unit: points per year |
| `trend_label` | string | `Improving vs peers`, `Stable vs peers`, `Declining vs peers`, `Recovering` or `Not enough data` |
| `years_used` | integer | Number of summers used for the trend |
| `burn_status` | string | `unburned` (burn_frac up to 0.05), `partial`, or `mostly_burned` (above 0.50) |
| `burn_frac` | number 0-1 | Share of the patch flagged burned 2015-2026 (MODIS MCD64A1, 500 m) |
| `forest_frac` | number 0-1 | Share of the patch that is tree cover (ESA WorldCover v200) |
| `data_quality` | string | `good`, `limited` (under 90% cloud-free pixels or under 50% tree cover) or `not_scored` |

### How `health_index` is calculated
1. Take the patch's mean NDVI and mean NDMI over tree pixels for the summer.
2. Rescale each linearly to 0-1 between the 5th and 95th percentile of **unburned** patches (all five summers pooled), clipping at 0 and 1. Saved values: NDVI 0.397 to 0.713, NDMI -0.104 to 0.236 (`data/processed/m1_reference_bounds.json`).
3. Average the two and multiply by 100.

### How bands are assigned
- Not scored: under 20% tree cover or missing indices.
- Post-fire recovery: `burn_status` is `mostly_burned` (the score is still shown).
- Otherwise by the unburned reference: High stress below 6 (lowest 10%), Moderate stress 6 to under 21 (next 20%), Healthy 21 and above. The bands are relative, not validated thresholds.

### How `trend_slope` is calculated
Each patch's `health_index` minus the same-year median of unburned patches, then a straight-line fit over the latest 5 summers. Subtracting the median removes the shared year-to-year (weather) trend. Labels use +/-1.5 points per year as the cutoff.