# M1 mortality-likelihood model card

Model `m1-mortality-hgb-v1` - HistGradientBoostingClassifier (scikit-learn 1.9.1). Generated 2026-11-22T07:09:03Z by `python -m scripts.train_final`. **This file is generated; do not edit it by hand** (run `python -m scripts.make_model_card_md`).

## What it predicts

A 500 m patch is positive in a year if USFS aerial-survey MORTALITY polygons cover at least 10% of it that year.

It estimates where USFS aerial surveys would map tree mortality. It is not a general forest-health measure, and the likelihood is relative to surveyed forest, not a real-world probability.

## Training data

- 51,641 labelled patch-years (12,859 positive), 2021-2024, 238 spatial blocks of 20 km.
- Negatives: cells within 3 km of a survey polygon of that year and under 1% covered.
- Excluded: burned (more than 5% since 2015); tree cover under 20%; fewer than 3 clear observations; 1-10% polygon coverage (ambiguous).
- Shaver Lake in training: no (never used).

## Evaluation

| Test | Cells | Positives | Base rate | AUC (95% interval) | PR-AUC | Precision, top 10% |
|---|---|---|---|---|---|---|
| Whole 20 km blocks held out (out-of-fold, deployed features) | 51,641 | 12,859 | 24.9% | 0.783 (0.766-0.796) | 0.566 | 68.7% |
| ... of which year 2021 | 11,132 | 2,069 | 18.6% | 0.718 | 0.339 | 39.4% |
| ... of which year 2022 | 15,628 | 4,709 | 30.1% | 0.768 | 0.583 | 70.6% |
| ... of which year 2023 | 14,144 | 4,161 | 29.4% | 0.801 | 0.651 | 79.6% |
| ... of which year 2024 | 10,737 | 1,920 | 17.9% | 0.794 | 0.493 | 57.8% |
| Experiment 1: blocks held out 2021-2023: environment only | 40,904 | 10,939 | 26.7% | 0.764 (0.745-0.779) | 0.567 | 70.9% |
| Experiment 1: blocks held out 2021-2023: environment + satellite | 40,904 | 10,939 | 26.7% | 0.776 (0.759-0.790) | 0.584 | 72.0% |
| Experiment 2: new blocks AND new year 2024: environment only | 2,049 | 364 | 17.8% | 0.718 (0.662-0.776) | 0.320 | 33.3% |
| Experiment 2: new blocks AND new year 2024: environment + satellite | 2,049 | 364 | 17.8% | 0.683 (0.622-0.746) | 0.283 | 28.9% |
| Experiment 3: Shaver Lake never seen: environment only | 683 | 99 | 14.5% | 0.634 | 0.209 | 27.9% |
| Experiment 3: Shaver Lake never seen: environment + satellite | 683 | 99 | 14.5% | 0.632 | 0.217 | 27.9% |
| **Deployed model on Shaver Lake (never seen)** | 683 | 99 | 14.5% | 0.709 | 0.251 | 29.4% |

- AUC gain of satellite features over environment only (blocks held out): 95% interval +0.008 to +0.016.
- AUC gain of satellite features over environment only (new blocks and 2024): 95% interval -0.085 to +0.020.

## Bands

Cutoffs come from the out-of-fold score distribution: High at or above 0.567, Elevated at or above 0.305, Lower below.

| Band | Share of patches | Observed damage rate |
|---|---|---|
| High | 10.0% | 68.7% |
| Elevated | 20.0% | 41.0% |
| Lower | 70.0% | 14.0% |

High alone catches about 27.6% of all mapped damage. High plus Elevated flags 30.0% of patches, 50.2% of them damaged, and catches about 60.5% of all mapped damage.

## Calibration (out-of-fold, by decile of predicted likelihood)

| Decile | Mean predicted | Observed rate | Patches |
|---|---|---|---|
| 1 | 0.030 | 0.035 | 5,165 |
| 2 | 0.059 | 0.067 | 5,164 |
| 3 | 0.085 | 0.100 | 5,164 |
| 4 | 0.116 | 0.122 | 5,164 |
| 5 | 0.154 | 0.170 | 5,164 |
| 6 | 0.202 | 0.214 | 5,164 |
| 7 | 0.266 | 0.276 | 5,164 |
| 8 | 0.353 | 0.354 | 5,164 |
| 9 | 0.482 | 0.466 | 5,164 |
| 10 | 0.702 | 0.687 | 5,164 |

## What the model relies on (AUC drop when a feature is shuffled)

| Feature | Meaning | AUC drop |
|---|---|---|
| elev | Elevation (m), SRTM | 0.1567 |
| def_wy | Climatic water deficit summed over the water year Oct-Sep (TerraClimate, raw units) | 0.1099 |
| forest_frac | Share of the patch that is tree cover (ESA WorldCover 2021) | 0.0282 |
| NDVI | Mean NDVI of tree pixels, June-September median composite (Sentinel-2) | 0.0197 |
| pdsi_jjas | Palmer Drought Severity Index, mean June-September (TerraClimate, raw units, scale 0.01) | 0.0190 |
| def_wy_prev | Same, for the previous water year | 0.0175 |
| NDVI_sd | Spread of NDVI inside the patch (patchy dieback raises it) | 0.0082 |
| NDMI_sd | Spread of NDMI inside the patch | 0.0071 |
| dNBR | NBR minus the previous summer | 0.0043 |
| dNDVI | NDVI minus the previous summer | 0.0038 |

## Limitations

- Trained on where USFS aerial surveyors mapped tree mortality (mostly fir engraver and other bark beetles; 98% of polygons are mortality). It is not a general forest-health measure.
- Most of the skill comes from terrain, forest cover and climate. Satellite features add a small gain in whole-block testing and no demonstrable gain in the strict new-places-and-year test.
- Negatives are cells within 3 km of a survey polygon in the same year, because the survey service has no layer showing where aircraft flew. A cell with no polygon may simply not have been flown.
- The likelihood is relative to surveyed forest. The training sample had a much higher damage rate than the whole Sierra, so do not read it as a real-world probability.
- Burned patches (more than 5% burned since 2015) and patches with under 20% tree cover are not scored.
- Satellite features use June-September composites. The app applies the model to the latest completed summer.
- USFS polygons are approximate aerial sketches, some data is generalized, and the Forest Service has not assessed their accuracy.
- Performance at Shaver Lake is lower than the Sierra-wide figure and has no confidence interval (few cells). Terrain and climate vary less inside a small area, which may limit any such model (not verified).

## Sources

- USFS Insect and Disease Survey (damage areas, 2021-2024)
- Sentinel-2 SR Harmonized (Google Earth Engine)
- ESA WorldCover v200
- SRTM elevation
- MODIS MCD64A1 burned area
- TerraClimate
