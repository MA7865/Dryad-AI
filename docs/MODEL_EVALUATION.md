# Model Evaluation

---

## M1 - Forest health

### Prediction target
M1 does not predict a labelled class. It outputs a **relative condition index** (0-100) and a band, built from Sentinel-2 NDVI and NDMI and compared with unburned forest in the same area. No cause (insects, drought, disease) is inferred.

### Why there is no trained classifier
The only reference labels are USFS aerial-survey damage polygons: 22 in the study area for 2021-2024 (2, 11, 6 and 3 per year), about 4,900 acres. 19 are fir engraver, 16 are "very light" or "light" damage (1-10% of trees), and 11 of the 22 are in 2022. That is too few, too weak and too uneven to train and fairly test a classifier. A "no polygon" patch is not necessarily healthy, so the other class would be noisy.

### Data
Sentinel-2 SR Harmonized summer composites 2022-2026, ESA WorldCover (tree mask), MODIS burned area (burn context), USFS IDS polygons (check only). Details in `DATA_SOURCES.md`.

### Train/test split and baseline
Not applicable: nothing is trained, and the scale is fixed from the unburned reference (`m1_reference_bounds.json`). Reference scale and band cutoffs are fitted on the same data they score, so they describe this area only.

### Checks performed
- **Band split:** among 754 scored unburned patches (2026), 12% High stress, 23% Moderate, 65% Healthy, close to the intended 10/20/70 split.
- **Burned patches:** 1,068 scored, mostly burned patches are labelled Post-fire recovery. 813 of 1,132 mostly burned patches show an improving trend, consistent with regrowth after the 2020 Creek Fire.
- **Trend sanity:** slopes for unburned patches centre near zero (median 0.1 points per year), so the shared weather trend is removed. 590 of 754 are "Stable vs peers".
- **USFS overlay (exploratory, 2022-2024, unburned patches):** 94 of 2,262 scored patch-years overlap a USFS damage polygon (10% or more of the patch covered). The same patches recur across years and neighbouring polygons overlap in space, so the effective sample is smaller than it looks.
  - *The score level does not detect damage.* These patches score higher, not lower: mean Health Index 73 vs 42 for the rest, AUC 0.18 for ranking them as more stressed. They sit in denser forest (NDVI 0.63 vs 0.53, tree cover 84% vs 74%). Against unlabelled patches within 2.5 km they score 3.5 points higher on average and only 42% are lower, so there is no local signal either.
  - *The change in relative score from 2022 to 2024 carries a modest signal.* Ranking the 754 patches by how much their score fell gives an AUC of 0.75 (bootstrap 95% interval 0.70-0.81; 84 patches with a polygon). Polygon patches start higher, so part of this could be regression to the mean. After adjusting for the starting level (fitted on patches without polygons) the AUC is 0.66 (0.60-0.72). The bootstrap treats patches as independent, so the interval is probably too narrow.
  - *M1's own 5-summer trajectory does not show this signal.* AUC 0.42 (754 patches, 84 with a polygon): no evidence that the trend labels track the surveyed damage.
  - *Status: exploratory.* The 2022-2024 window was examined after the first check failed, so 0.66 is probably optimistic. It needs an independent test (for example 2025 survey polygons).

### Limitations
- A low score means lower greenness and moisture than similar unburned forest, from any cause, including terrain, aspect and canopy type.
- USFS polygons are approximate aerial sketches and can include healthy trees.
- Burn flag is coarse (500 m). Forest mask is from 2021. Only 5 summers. Summer medians hide within-season change.
- Trend labels use a +/-1.5 points per year cutoff chosen as a first setting, not validated against ground truth. Over 5 points the trend is noisy.
- The 0-100 scale is relative: the score is not comparable with other regions without rebuilding the scale.

### Known leakage risks
None in the training sense (no training). The main risk is over-reading the USFS overlay: with few positives and polygons that are themselves approximate, results are indicative only.
- The change measure and window were chosen after looking at the same 84 labelled patches, and several checks were tried (level, neighbours, change). Treat the results as hypothesis-generating, not confirmed.