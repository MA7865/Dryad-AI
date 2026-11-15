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
- **USFS overlay (2022-2024, unburned patches):** 94 of 2,262 scored patch-years overlap a USFS damage polygon (10% or more of the patch covered). The same patches recur across years, so the effective sample is smaller. These patches score higher, not lower: mean Health Index 73 vs 42 for the rest (median 74 vs 38), 99% are Healthy, and the AUC for ranking them as more stressed is 0.18 (they rank as healthier about 82% of the time). **The index does not detect the surveyed damage.** Likely reason (not yet verified): the polygons lie in dense mid-elevation conifer forest, which is naturally greener and moister than much of the reference area, and most damage is light (1-10% of trees). The score therefore reflects forest type and density as much as condition.

### Limitations
- A low score means lower greenness and moisture than similar unburned forest, from any cause, including terrain, aspect and canopy type.
- USFS polygons are approximate aerial sketches and can include healthy trees.
- Burn flag is coarse (500 m). Forest mask is from 2021. Only 5 summers. Summer medians hide within-season change.
- Trend labels use a +/-1.5 points per year cutoff chosen as a first setting, not validated against ground truth. Over 5 points the trend is noisy.
- The 0-100 scale is relative: the score is not comparable with other regions without rebuilding the scale.

### Known leakage risks
None in the training sense (no training). The main risk is over-reading the USFS overlay: with few positives and polygons that are themselves approximate, results are indicative only.