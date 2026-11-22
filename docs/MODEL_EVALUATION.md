## M4: Fire spread prototype (Goose fire, 2016)

Status: research prototype (Week 2). One fire, one tuned parameter. Not validated for prediction.

### Question

Given where the Goose fire started and the weather, can a simple grid model reproduce the shape of the area that burned?

### Test case

- **Fire:** Goose, Fresno County. Started 2016-07-30 at about 16:40 local time (23:40 UTC), contained 2016-08-09 (CAL FIRE).
- **Ground truth:** CAL FIRE perimeter, 9.07 km2 = 1,122 cells on a 90 m grid.
- **Start point:** CAL FIRE's published point (37.01591, -119.50507) lies 725 m *outside* the perimeter, so it is approximate. We use the nearest point inside the perimeter (the western tip, about 2.8 km from the perimeter centre). The fire.ai point (37.01355, -119.46717) is 1 m from the perimeter centre, so it is the centre of the outline, not an ignition location.
- **Weather:** Open-Meteo historical weather (reanalysis, roughly 10 km pixels). Grid point used: 37.0123, -119.4459, elevation 675 m. Hourly 10 m wind.

### Method

- **Grid:** 90 m cells in UTM 11N (EPSG:32611), aligned to multiples of 90 m (3 x 30 m, so it lines up with LANDFIRE later). Row 0 is south.
- **Version 0 (no wind):** cellular automaton. A burning cell ignites each of its 8 neighbours at every step with probability p = 0.4 (orthogonal) or p / sqrt(2) (diagonal). A cell burns for 3 steps. If the fire goes out early, the edge of the burned area smoulders on.
- **Version 1a (wind):** each neighbour's probability is multiplied by exp(k * (cos(theta) - 1)), where theta is the angle between the direction of spread and the direction the wind blows toward. Spread is unchanged straight downwind, weaker across the wind, weakest against it. k = 0 gives exactly Version 0.
- **Stopping rule:** the run stops when the simulated fire has burned as many cells as the real fire. **The area is given to the model.** A step is not a unit of real time.
- **Randomness:** 30 runs (seeds 0 to 29) for Version 0, 20 runs (seeds 0 to 19) for Version 1a. Tables show the mean.

### Metric

IoU = overlap area / combined area, computed on the 90 m grid (a cell counts if its centre is inside the polygon). 1 is a perfect match, 0 is no overlap.

**Baseline:** a round fire of the same area centred on the same start point.

### Results

**Table 1. Version 0 (no wind): where the fire starts**

| Start point | Simulation | Round baseline |
|---|---|---|
| CAL FIRE point, as published (725 m outside) | 0.059 | 0.060 |
| CAL FIRE point, snapped inside (western tip) | 0.106 | 0.108 |
| Perimeter centre (reference only; a fire cannot start here) | 0.514 | 0.523 |

Version 0 is equivalent to the round baseline, as expected: with no wind, slope or fuel the fire is a round blob. 0.52 is roughly the most a round fire can score on Goose, if it is placed perfectly.

**Table 2. Version 1a: wind strength k** (start: western tip unless noted)

Wind windows (31 Jul 00:00 to 1 Aug 23:00 UTC):

| Window | Blows toward | Mean speed | Steadiness |
|---|---|---|---|
| All 48 hours | 108 deg (ESE) | 1.6 m/s | 0.68 |
| Dry hours only (humidity below 25 %, 21 h) | 92 deg (E) | 2.3 m/s | 0.88 |
| Local 12:00 to 20:00 (18 h) | 89 deg (E) | 2.4 m/s | 0.96 |

| k | Tip, all-hours wind (108 deg) | Tip, dry-hours wind (92 deg) | Centre, dry-hours wind (92 deg) |
|---|---|---|---|
| 0 (no wind) | 0.107 | 0.107 | 0.524 |
| 0.5 | 0.154 | 0.164 | 0.497 |
| 1 | 0.261 | 0.321 | 0.337 |
| 2 | 0.320 | **0.487** | 0.182 |
| 3 | 0.143 | 0.363 | 0.108 |
| 4 | 0.091 | 0.232 | 0.106 |

Round baseline from the western tip: 0.108.

**Table 3. Wind direction scan** (start: western tip, k = 2, directions are where the wind blows toward)

| Toward (deg) | 0 | 30 | 60 | 90 | 120 | 150 | 180 | 210 | 240 | 270 | 300 | 330 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Mean IoU | 0.002 | 0.053 | 0.256 | **0.507** | 0.151 | 0.015 | 0.011 | 0.007 | 0.003 | 0.001 | 0.000 | 0.000 |

Best-scoring direction: 90 deg. Wind direction from the dry hours of the weather data: 92 deg.

### What the results show

- From the same start point, wind taken from the weather data raises IoU from 0.11 (no wind) to 0.49 (k = 2), about 4.5 times.
- The score is very sensitive to wind direction: 90 deg gives 0.51, 120 deg gives 0.15, 60 deg gives 0.26.
- Averaging all hours gives 108 deg, which includes calm northerly nights when the fire was probably barely spreading. Averaging only the dry hours gives 92 deg, close to the best-scoring direction.
- At ignition (23:00 UTC on 30 Jul, 16:00 local) the wind was from the west at 2.0 m/s with gusts of 8.5 m/s, 38.3 C and 11 % relative humidity.
- The FIRMS detection centre moved 2,043 m east and 75 m south between 31 Jul and 1 Aug, consistent with a fire still active at its eastern end on the second day.

### Limitations

- **One fire, one tuned parameter.** k was tuned on Goose itself. The result shows the idea can reproduce this fire, not that it generalises.
- **The dry-hours filter was chosen after seeing the direction scan.** It has a physical reason (fires spread most when the air is hot and dry), and the 25 % humidity cut-off is our own choice. It has not been checked independently.
- **The area is given.** The model is told how big the fire was, so it shows shape and direction, not fire size or timing.
- **No real clock.** Steps are not hours, so the output cannot yet be compared with satellite passes.
- **Start point is an estimate** (the published point is outside the perimeter). Start-point sensitivity tested (Table 4): robust within 600 m north, east and west, weaker to the south, and IoU cannot pin down the ignition location.
- **Coarse wind.** The weather data is roughly 10 km. It cannot capture canyon or valley winds. We trust it for direction, not for speed.
- **Hole artefacts.** The random growth rule leaves unburned speckles inside the simulated fire, which lower IoU.
- **Edge warnings.** 33 to 35 runs at high k (3 and 4) touched the edge of the simulation area. Treat the k = 3 and k = 4 rows as unreliable.
- **No slope or fuel yet.** The real fire bends north-east in a way an east wind alone does not produce.

### Model checklist (deck slide 26)

| Check | Status |
|---|---|
| Input compatibility | Done. Inputs: perimeter, start point, hourly wind. |
| Baseline comparison | Done (round fire, same start). |
| Held-out evaluation | Not done. One fire, k tuned on it. |
| Class imbalance | Not applicable. |
| Calibration | Not applicable. Output is a shape, not a probability. |
| Spatial / temporal transfer | Not tested. |
| Resource requirements | 90 simulations take 0.6 s on a laptop. Memory not measured. |
| Licence | Own code. Data terms: NASA FIRMS acknowledgement, CAL FIRE open data. TODO: check Open-Meteo terms and attribution. |

### Reproduce

```
python scripts/fetch_goose_firms.py "data/raw/<perimeter file>"
python scripts/fetch_goose_weather.py
python scripts/run_spread_v0.py
python scripts/run_spread_wind.py --max-rh 25
python -m pytest tests -v
```

### Next

Start-point sensitivity, hourly wind on a real clock (Version 1b), slope (Version 2), then fuel and water barriers.


**Table 4. Start-point sensitivity** (wind from dry hours, 92 deg, k = 2, 10 runs per start; centre = snapped western tip; offsets in metres)

| North offset \ East offset | -600 | -300 | 0 | +300 | +600 |
|---|---|---|---|---|---|
| +600 | 0.468* | 0.488* | 0.498* | 0.491* | 0.487* |
| +300 | 0.444* | 0.483* | 0.483* | 0.508 | 0.511 |
| 0 | 0.440* | 0.470* | **0.502** | 0.473 | 0.500 |
| -300 | 0.355* | 0.389* | 0.419 | 0.382 | 0.365* |
| -600 | 0.266* | 0.344* | 0.335* | 0.327* | 0.337* |

`*` = start point outside the real perimeter. Batch-to-batch noise at the centre: 0.451 to 0.510 (3 batches of 10 runs), so differences below about 0.05 are chance.

Reading: moving the start up to 600 m north, east or west leaves IoU at 0.44 to 0.51, within noise of the centre. Moving it south lowers IoU to 0.36 to 0.42 (300 m) and 0.27 to 0.34 (600 m). Starts outside the real perimeter, including the whole +600 m north row, still score about 0.49. So IoU on the final shape does not identify the ignition location: with the area given and the wind blowing east, any nearby start grows a similar oval that overlaps the elongated Goose perimeter. The 0.49 result is robust to the start point, but this test does not validate the start point.
# Model Evaluation

---

## M1 - Forest health

### Prediction target
A 500 m patch is positive in a year if USFS aerial-survey mortality polygons cover at least 10% of it. The model outputs a likelihood and a band; it does not diagnose a cause.

### Why this target
USFS polygons are the only independent labels. The Sierra Nevada has 15,457 polygons for 2021-2024 (98% mortality, 68% fir engraver), enough to train and test, unlike the 22 polygons in the Shaver Lake box.

### Data and split design (fixed before looking at results)
- Positives: at least 10% covered. Negatives: unburned cells within 3 km of a polygon of that year and under 1% covered (no flight-coverage layer exists). Ambiguous cells (1-10%) are dropped. Burned (over 5% since 2015) and low-forest (under 20%) patches are excluded.
- 31,940 sampled 500 m cells (all 2,061 Shaver Lake patches plus 30,000 random cells near polygons), summers 2020-2024; 51,641 labelled patch-years outside Shaver Lake.
- Tests: whole 20 km blocks held out; new blocks and a new year (2024); Shaver Lake, never used in training.
- Baselines: environment only (terrain, tree cover, climate) versus environment plus satellite features.
- Intervals: resampling whole blocks.

### Results (full tables: docs/M1_MODEL_CARD.md)
- Whole blocks held out: AUC 0.78 (95% 0.77-0.80); top 10% flagged: 69% damaged versus 25% overall.
- By year: AUC 0.72 (2021), 0.77 (2022), 0.80 (2023), 0.79 (2024).
- Strictest test (new blocks and 2024): AUC about 0.73; the satellite gain over environment-only is not demonstrable (interval includes 0).
- Shaver Lake, never seen: AUC 0.71 (683 patches, 99 damaged).
- Calibration within about 0.02 per decile. Bands: High = 10% of patches with 69% damaged; High + Elevated = 30% of patches, about 50% damaged, catching about 60% of mapped damage.
- Importance: elevation, climatic water deficit and tree cover dominate; satellite features add about +0.01 AUC.

### Other checks
- Condition index: AUC 0.18 against the 22 Shaver polygons (damaged patches are denser, greener forest), so it is described as relative greenness, not damage.
- 5-summer trend: AUC 0.54 before the survey year, 0.61 including it: context only.
- Training/serving parity: features recomputed through the live code path match the training table to 5 decimals.

### Limitations and leakage risks
- Polygons are approximate aerial sketches, partly generalized, with no accuracy assessment.
- Neighbouring cells are correlated; whole-block holdout addresses this. The same polygons feed several years' cells.
- The sample is drawn near polygons, so its damage rate (25%) is higher than the whole Sierra's; band cutoffs come from out-of-fold predictions on this sample.
- The 10% coverage threshold, 3 km rule and band cutoffs were fixed before testing. Several tests were run and all are reported.
- Climate inputs for the latest summers use the latest year available (2024), not the scoring year.
- Shaver Lake results rest on 99 damaged patches and have no confidence interval.