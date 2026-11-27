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
- Terrain and climate alone nearly match the full model. In whole-block testing, satellite features add about +0.01 AUC (0.764 to 0.776; interval +0.008 to +0.016). In the strictest test (new places and a new year; 2,049 patches, 364 damaged) the two models cannot be told apart (0.72 environment-only vs 0.68 with satellite; difference interval -0.09 to +0.02), and the sign changed between two software environments, so no satellite gain is claimed there.
- Shaver Lake, never seen: AUC 0.71 (683 patches, 99 damaged).
- Calibration within about 0.02 per decile. Bands: High = 10% of patches with 69% damaged; High + Elevated = 30% of patches, about 50% damaged, catching about 60% of mapped damage.
- Importance: elevation, climatic water deficit and tree cover dominate; satellite features add about +0.01 AUC.
- At Shaver Lake the mean predicted likelihood for labelled patch-years was 0.154 against an observed damage rate of 0.145, and observed damage rose across thirds of the score (2.6%, 16.7%, 24.1%). Year-level intensity is not captured: 2021 and 2024 were over-predicted (0.17 vs 0.03 and 0.07 vs 0.01) and 2023 under-predicted (0.13 vs 0.19). Use the model to rank patches, not to forecast how much damage a given year will bring.

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

---

## M4 - Fire spread simulation

### Summary

- **What it does:** given an ignition point, a final burned area and the wind, a grid model draws the shape of the burned area. The area is given to the model, so it shows shape and direction, not fire size or timing. It has no real clock.
- **Evidence:** 13 past fires (Goose, plus 12 Sierra Nevada fires with a tune/test split). Metric: IoU against the CAL FIRE perimeter, compared with a round fire of the same area.
- **Result:** on the 12 fires, a round fire scores 0.36 on average, wind from the weather data 0.42 (Version 1a, average wind) and 0.42 (Version 1b, hourly wind). Slope alone scores 0.37, and slope on top of wind adds nothing (Part 4). The wind gain is about +0.06 and inconsistent between fires. Goose (0.49 against 0.11) was one fire with k tuned on it and should not be quoted as the model's accuracy.
- **Main limitation found:** the direction of the wind. With the best of 12 directions the model reaches about 0.50, so most of the possible gain is lost through direction error from 10 km weather data.
- **Not yet done:** fuel, moisture, a real clock. This is a research prototype, not a prediction or an alert system.

### Part 1. Prototype on the Goose fire (2016)

Status: research prototype (Week 2). One fire, one tuned parameter. Not validated for prediction.

#### Question

Given where the Goose fire started and the weather, can a simple grid model reproduce the shape of the area that burned?

#### Test case

- **Fire:** Goose, Fresno County. Started 2016-07-30 at about 16:40 local time (23:40 UTC), contained 2016-08-09 (CAL FIRE).
- **Ground truth:** CAL FIRE perimeter, 9.07 km2 = 1,122 cells on a 90 m grid.
- **Start point:** CAL FIRE's published point (37.01591, -119.50507) lies 725 m *outside* the perimeter, so it is approximate. We use the nearest point inside the perimeter (the western tip, about 2.8 km from the perimeter centre). The fire.ai point (37.01355, -119.46717) is 1 m from the perimeter centre, so it is the centre of the outline, not an ignition location.
- **Weather:** Open-Meteo historical weather (reanalysis, roughly 10 km pixels). Grid point used: 37.0123, -119.4459, elevation 675 m. Hourly 10 m wind.

#### Method

- **Grid:** 90 m cells in UTM 11N (EPSG:32611), aligned to multiples of 90 m (3 x 30 m, so it lines up with LANDFIRE later). Row 0 is south.
- **Version 0 (no wind):** cellular automaton. A burning cell ignites each of its 8 neighbours at every step with probability p = 0.4 (orthogonal) or p / sqrt(2) (diagonal). A cell burns for 3 steps. If the fire goes out early, the edge of the burned area smoulders on.
- **Version 1a (wind):** each neighbour's probability is multiplied by exp(k * (cos(theta) - 1)), where theta is the angle between the direction of spread and the direction the wind blows toward. Spread is unchanged straight downwind, weaker across the wind, weakest against it. k = 0 gives exactly Version 0.
- **Stopping rule:** the run stops when the simulated fire has burned as many cells as the real fire. **The area is given to the model.** A step is not a unit of real time.
- **Randomness:** 30 runs (seeds 0 to 29) for Version 0, 20 runs (seeds 0 to 19) for Version 1a. Tables show the mean.

#### Metric

IoU = overlap area / combined area, computed on the 90 m grid (a cell counts if its centre is inside the polygon). 1 is a perfect match, 0 is no overlap.

**Baseline:** a round fire of the same area centred on the same start point.

#### Results

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

#### What the results show

- From the same start point, wind taken from the weather data raises IoU from 0.11 (no wind) to 0.49 (k = 2), about 4.5 times.
- The score is very sensitive to wind direction: 90 deg gives 0.51, 120 deg gives 0.15, 60 deg gives 0.26.
- Averaging all hours gives 108 deg, which includes calm northerly nights when the fire was probably barely spreading. Averaging only the dry hours gives 92 deg, close to the best-scoring direction.
- At ignition (23:00 UTC on 30 Jul, 16:00 local) the wind was from the west at 2.0 m/s with gusts of 8.5 m/s, 38.3 C and 11 % relative humidity.
- The FIRMS detection centre moved 2,043 m east and 75 m south between 31 Jul and 1 Aug, consistent with a fire still active at its eastern end on the second day.

#### Limitations

- **One fire, one tuned parameter.** k was tuned on Goose itself. The result shows the idea can reproduce this fire, not that it generalises.
- **The dry-hours filter was chosen after seeing the direction scan.** It has a physical reason (fires spread most when the air is hot and dry), and the 25 % humidity cut-off is our own choice. It has not been checked independently.
- **The area is given.** The model is told how big the fire was, so it shows shape and direction, not fire size or timing.
- **No real clock.** Steps are not hours, so the output cannot yet be compared with satellite passes.
- **Start point is an estimate** (the published point is outside the perimeter). Start-point sensitivity tested (Table 4): robust within 600 m north, east and west, weaker to the south, and IoU cannot pin down the ignition location.
- **Coarse wind.** The weather data is roughly 10 km. It cannot capture canyon or valley winds. We trust it for direction, not for speed.
- **Hole artefacts.** The random growth rule leaves unburned speckles inside the simulated fire, which lower IoU.
- **Edge warnings.** 33 to 35 runs at high k (3 and 4) touched the edge of the simulation area. Treat the k = 3 and k = 4 rows as unreliable.
- **No slope or fuel yet.** The real fire bends north-east in a way an east wind alone does not produce.

#### Model checklist (deck slide 26)

| Check | Status |
|---|---|
| Input compatibility | Done. Inputs: perimeter, start point, hourly wind. |
| Baseline comparison | Done (round fire, same start). |
| Held-out evaluation | Not done on Goose itself (one fire, k tuned on it). See Part 2 for 12 other fires with a tune/test split. |
| Class imbalance | Not applicable. |
| Calibration | Not applicable. Output is a shape, not a probability. |
| Spatial / temporal transfer | Part 2 tests other Sierra Nevada fires, 2013 to 2024. Not tested outside California. |
| Resource requirements | 90 simulations take 0.6 s on a laptop. Memory not measured. |
| Licence | Own code. Data terms: NASA FIRMS acknowledgement, CAL FIRE open data. TODO: check Open-Meteo terms and attribution. |

#### Reproduce

```
python scripts/fetch_goose_firms.py "data/raw/<perimeter file>"
python scripts/fetch_goose_weather.py
python scripts/run_spread_v0.py
python scripts/run_spread_wind.py --max-rh 25
python -m pytest tests -v
```

#### Next

Done since this part was written: multi-fire validation (Part 2) and hourly wind, Version 1b (Part 3). Slope (Version 2) is Part 4. Still to do: fuel, moisture and water barriers.


### Part 2. Multi-fire validation of the wind model (Version 1a)

Status: exploratory. 12 Sierra Nevada fires, one tuned parameter, rough ignition estimates. Not a validated prediction.

#### Question

The Goose result in Part 1 (IoU 0.49 against a round-fire baseline of 0.11) used one fire, with the wind strength k tuned on that same fire. Does the same wind rule work on other fires?

#### Protocol (fixed before any model score was looked at)

1. **Candidate fires** (`scripts/list_validation_candidates.py`): CAL FIRE perimeters whose centre lies inside a hand-drawn outline of the Sierra Nevada (edges good to about 10 km), years 2012 to 2025, alarm date known, area 5 to 150 km2. Result: 99 fires (34 round, 54 medium, 11 long; elongation = length / width of the minimum rotated rectangle, round < 1.5, long >= 2.5).
2. **Eligible and selected** (`scripts/count_candidate_detections.py`): VIIRS detections (`VIIRS_SNPP_SP`, confidence n and h only) within 375 m of the perimeter, first 7 days from the day before the alarm date. Eligible = at least 15 detections on at least 2 days (62 fires). Selected = up to 4 per shape class, most detections first (12 fires). The Goose fire is not in this set (it was used to build the model).
3. **Split** (`scripts/run_validation.py`): within each shape class, fires sorted by year then name are assigned tune, test, tune, ... (6 tune, 6 test).
4. **Ignition point (estimated):** mean position of the detections in the first 6 hours after the first detection, moved just inside the perimeter if outside.
5. **Wind:** Open-Meteo hourly wind at the fire's centre for the 48 hours from the first detection. Hours with relative humidity below 25 % are averaged as vectors; if fewer than 6 such hours exist, all 48 are used. Same rule for every fire.
6. **Model:** Version 1a (cellular automaton with the wind multiplier), area given to the model, k in {0, 0.5, 1, 2, 3, 4}, mean IoU over 10 random seeds.
7. **k is chosen on the tune fires only.** The test fires are then scored at that k, next to k = 0 and the round-fire baseline from the same start.

#### Table 5. Results

**Tune fires: mean IoU by wind strength k**

| k | 0 | 0.5 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|---|
| Mean IoU | 0.336 | 0.401 | **0.433** | 0.261 | 0.107 | 0.118 |

Round-fire baseline (same start): 0.338. Chosen k = 1. At k = 2, the value that worked on Goose, the tune fires score below the baseline.

**Test fires, scored at k = 1**

| Fire | Year | Shape | km2 | Round baseline | No wind (k = 0) | Wind (k = 1) |
|---|---|---|---|---|---|---|
| French | 2014 | medium | 56.0 | 0.361 | 0.357 | 0.246 |
| Caples | 2019 | long | 13.9 | 0.476 | 0.470 | 0.301 |
| Slink | 2020 | round | 108.3 | 0.272 | 0.273 | 0.252 |
| Tiltill | 2021 | long | 9.5 | 0.250 | 0.254 | 0.505 |
| Oak | 2022 | round | 76.8 | 0.488 | 0.487 | 0.551 |
| Fresno June Lightning Complex | 2024 | medium | 43.1 | 0.392 | 0.381 | 0.535 |

Mean IoU on the test fires: wind 0.398, no wind 0.370, round baseline 0.373. Wind beats the round baseline on 3 of 6 fires and beats no wind on 3 of 6. By shape class (mean IoU, wind / no wind / baseline): long 0.403 / 0.362 / 0.362, medium 0.390 / 0.369 / 0.376, round 0.401 / 0.380 / 0.380.

**Table 5b. Inputs per fire**

| Fire | Split | km2 | Wind toward (deg) | Mean speed (m/s) | Steadiness | Hours used | Start to perimeter centre (m) |
|---|---|---|---|---|---|---|---|
| Aspen 2013 | tune | 92.8 | 68 | 1.5 | 0.44 | all | 4,782 |
| French 2014 | test | 56.0 | 21 | 1.4 | 0.10 | all | 2,926 |
| Washington 2015 | tune | 72.0 | 52 | 4.1 | 0.99 | dry | 6,409 |
| Cedar 2016 | tune | 117.7 | 29 | 1.8 | 0.63 | dry | 5,033 |
| Creek 2017 | tune | 7.1 | 296 | 1.8 | 0.38 | all | 806 |
| Caples 2019 | test | 13.9 | 263 | 7.0 | 1.00 | dry | 445 |
| Fork 2020 | tune | 6.8 | 257 | 5.9 | 0.91 | dry | 1,266 |
| Slink 2020 | test | 108.3 | 126 | 2.2 | 0.62 | dry | 5,086 |
| French 2021 | tune | 107.4 | 356 | 3.0 | 0.38 | dry | 2,862 |
| Tiltill 2021 | test | 9.5 | 50 | 3.5 | 0.97 | dry | 2,154 |
| Oak 2022 | test | 76.8 | 54 | 2.2 | 0.68 | dry | 2,552 |
| Fresno June Lightning 2024 | test | 43.1 | 106 | 3.0 | 0.89 | dry | 1,987 |

#### Table 6. Is the problem the wind data or the model? (direction scan at k = 1, every 30 deg)

| Fire | Weather direction | Best direction | Long axis | IoU, weather direction | IoU, best direction | Weather vs best (deg) |
|---|---|---|---|---|---|---|
| Aspen | 68 | 60 | 46 | 0.48 | 0.50 | 8 |
| French 2014 | 21 | 330 | 161 | 0.25 | 0.47 | 51 |
| Washington | 52 | 30 | 32 | 0.46 | 0.42 | 22 |
| Cedar | 29 | 0 | 107 | 0.59 | 0.64 | 29 |
| Creek | 296 | 270 | 62 | 0.29 | 0.29 | 26 |
| Caples | 263 | 210 | 67 | 0.30 | 0.40 | 53 |
| Fork | 257 | 270 | 70 | 0.42 | 0.41 | 13 |
| Slink | 126 | 210 | 153 | 0.25 | 0.59 | 84 |
| French 2021 | 356 | 300 | 39 | 0.36 | 0.61 | 56 |
| Tiltill | 50 | 60 | 29 | 0.51 | 0.49 | 10 |
| Oak | 54 | 30 | 21 | 0.55 | 0.60 | 24 |
| Fresno June Lightning | 106 | 120 | 166 | 0.54 | 0.55 | 14 |

The weather direction is within 30 deg of the best-scoring direction on 8 of 12 fires. Mean IoU is 0.416 with the weather direction and 0.497 with the best direction. For the 8 elongated fires (elongation >= 1.5), both the best direction and the weather direction lie within 30 deg of the long axis on 5 of 8.

#### What the results show

- A single wind strength tuned on one fire does not transfer. Tuned on 6 fires, the best k is 1, not 2, and the average gain over the round baseline on the test fires is small (+0.025 over no wind), within the noise of 6 fires and 10 runs.
- The effect varies a lot by fire: wind adds +0.25 on Tiltill, +0.15 on Fresno June Lightning and +0.06 on Oak, and removes 0.17 on Caples, 0.11 on French 2014 and 0.02 on Slink.
- With the best of 12 directions the model reaches about 0.50 against a baseline of about 0.35, so the idea works when the direction is right. Most of the possible gain is lost through direction error.
- Direction misses are not explained by wind steadiness alone. Two misses have low steadiness (French 2014 at 0.10 and French 2021 at 0.38), but Caples (1.00) and Slink (0.62) have steady wind and still miss by more than 50 deg.
- The scan gives no support for the idea that terrain steers fires along their long axis where the weather data misses. Slope has not been tested.

#### Limitations

- 12 fires, 6 of them test fires, 10 random seeds per setting. Differences below about 0.05 are within noise.
- The ignition point is a crude estimate (centre of the first 6 hours of detections). On large fires it lies thousands of metres from the real start (Table 5b), so scores for large fires mostly measure the area and shape, not the location.
- The best-direction score is the maximum over 12 noisy scores, so it is somewhat optimistic.
- The final area is given to the model, and there is no real clock.
- The wind is a coarse (about 10 km) reanalysis at one point, averaged over 48 hours. Its direction convention ("from") is assumed but not yet confirmed in Open-Meteo's documentation.
- The Sierra Nevada outline used to choose candidates is hand-drawn; the fire areas were computed in UTM 11N, which distorts distances slightly west of 120 deg W (a few tenths of a percent at most).
- The selection favoured fires with many detections, so very small or short fires are under-represented.
- Runs at k = 3 and 4 often touched the edge of the simulation area. Treat those values as unreliable. No run at k = 1 in the direction scan did.
- No slope, fuel or moisture yet.

#### Reproduce

```
python scripts/list_validation_candidates.py "data/raw/<perimeter file>"
python scripts/count_candidate_detections.py "data/raw/<perimeter file>"
python scripts/run_validation.py "data/raw/<perimeter file>"
python scripts/run_validation_directions.py "data/raw/<perimeter file>"
```

#### Next

Done: Version 1b (Part 3), tested on the same 12 fires with the same split.

### Part 3. Hourly wind (Version 1b), same 12 fires and split

**Table 7. Version 1b: wind that changes hour by hour**

Version 1b replaces the single averaged wind direction of Version 1a with the hourly wind in time order. The model has no clock, so time is taken to be proportional to the area burned: the first 1/H of the final area grows under the first hour's wind, the next 1/H under the second hour's, and so on (H = number of hours in the sequence). The strength in each hour is k times that hour's wind speed divided by the mean speed over the sequence, so calm hours push the fire less.

Rules fixed before any 1b score was looked at:
- **Primary arm:** only hours with relative humidity below 25 %, in order (all 48 hours if fewer than 6 are dry). Same hour selection as Version 1a.
- **Secondary arm (exploratory):** all 48 hours in order.
- k chosen on the tune fires only, separately for each arm.

**Tune fires: mean IoU by k**

| k | 0 | 0.5 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|---|
| 1b primary (dry hours in order) | 0.336 | 0.376 | **0.388** | 0.282 | 0.247 | 0.280 |
| 1b secondary (all 48 hours) | 0.336 | **0.357** | 0.334 | 0.241 | 0.219 | 0.246 |
| 1a (average wind), for reference | 0.336 | 0.401 | 0.433 | 0.261 | 0.107 | 0.118 |

Round-fire baseline on the tune fires: 0.338.

**Test fires** (primary arm at its chosen k = 1)

| Fire | Year | Shape | Round baseline | 1a (average wind, k = 1) | 1b (dry hours in order, k = 1) |
|---|---|---|---|---|---|
| French | 2014 | medium | 0.361 | 0.246 | 0.373 |
| Caples | 2019 | long | 0.476 | 0.301 | 0.269 |
| Slink | 2020 | round | 0.272 | 0.252 | 0.450 |
| Tiltill | 2021 | long | 0.250 | 0.505 | 0.491 |
| Oak | 2022 | round | 0.488 | 0.551 | 0.648 |
| Fresno June Lightning Complex | 2024 | medium | 0.392 | 0.535 | 0.507 |

Mean IoU on the test fires: 1b 0.456, 1a 0.398, round baseline 0.373. 1b beats 1a on 3 of 6 test fires and beats the round baseline on 5 of 6 (1a: 3 of 6). The secondary arm (all 48 hours, k = 0.5) scores 0.394 on the test fires, no better than 1a.

**Table 7b. All 12 fires, Version 1a against Version 1b (both at k = 1; the six tune fires were used to choose k)**

| Fire | Year | Split | Wind steadiness | Round baseline | 1a (average wind) | 1b (hourly, dry hours) | 1b minus 1a |
|---|---|---|---|---|---|---|---|
| Aspen | 2013 | tune | 0.44 | 0.298 | 0.475 | 0.436 | -0.039 |
| French | 2014 | test | 0.10 | 0.361 | 0.246 | 0.373 | +0.127 |
| Washington | 2015 | tune | 0.99 | 0.153 | 0.455 | 0.355 | -0.100 |
| Cedar | 2016 | tune | 0.63 | 0.307 | 0.592 | 0.459 | -0.133 |
| Creek | 2017 | tune | 0.38 | 0.426 | 0.291 | 0.246 | -0.045 |
| Caples | 2019 | test | 1.00 | 0.476 | 0.301 | 0.269 | -0.032 |
| Fork | 2020 | tune | 0.91 | 0.377 | 0.418 | 0.302 | -0.116 |
| Slink | 2020 | test | 0.62 | 0.272 | 0.252 | 0.450 | +0.198 |
| French | 2021 | tune | 0.38 | 0.470 | 0.365 | 0.531 | +0.165 |
| Tiltill | 2021 | test | 0.97 | 0.250 | 0.505 | 0.491 | -0.014 |
| Oak | 2022 | test | 0.68 | 0.488 | 0.551 | 0.648 | +0.097 |
| Fresno June Lightning Complex | 2024 | test | 0.89 | 0.392 | 0.535 | 0.507 | -0.028 |

Mean IoU over the 12 fires: round baseline 0.356, Version 1a 0.416, Version 1b 0.422. Version 1a beats the round baseline on 7 of 12 fires, Version 1b on 9 of 12.

#### What the 1b results show

- **No clear improvement over Version 1a.** 1b is better on the test fires (0.456 against 0.398) but worse on the tune fires (0.388 against 0.433). Over all 12 fires the means are 0.422 and 0.416. Both add about 0.06 to the round-fire baseline.
- **Steady wind: 1b is worse on all five fires** with steadiness of 0.89 or more (differences of -0.014 to -0.116, mean about -0.06). With a steady direction the hourly sequence should resemble the single average, so the difference is not about direction. A possible cause is the speed scaling: hours with wind much above the mean get a strength well above k, and in the 1a tune results strengths of 2 or more scored worse than 1. This explanation has not been tested.
- **Changing wind: mixed.** The hourly sequence scored higher on 4 of the 7 fires with steadiness below 0.7 (+0.10 to +0.20) and lower on the other 3 (-0.04 to -0.13). The sequence helps on some fires with changing wind but not consistently.
- **Humid hours matter.** Using all 48 hours (arm "all") does no better than 1a, so restricting to dry hours was important. That restriction was first chosen for Goose after seeing results, and was then applied unchanged to every fire.
- **The tune curves are noisy** (non-monotonic at k = 2 to 4, with edge-touching runs at high k). Differences of a few hundredths should not be interpreted.

#### Limitations specific to 1b

- Time is proportional to area burned. Real fires grow faster in some hours than others, so the hours are not tied to real clock times, and the model cannot yet be compared with satellite pass times or the contract's 1, 3 and 6 hour horizons.
- Same 12 fires, 10 seeds, rough ignition estimates and 10 km wind as in the multi-fire section.
- 72 runs touched the edge of the simulation area, mostly at k = 3 and 4.

#### Reproduce

```
python scripts/run_validation_1b.py "data/raw/<perimeter file>"
```

### Part 4. Slope (Version 2), same 12 fires and split

Slope makes fire spread faster uphill and slower downhill. Fire moving from one 90 m cell to a neighbour is multiplied by exp(b x rise / run), where rise / run is the elevation gain divided by the distance between cell centres, capped at +-1 (a 45 degree slope). b = 0 is exactly Version 1a. Elevation comes from AWS terrain tiles (Terrarium, zoom 12, about 30 m), averaged onto the 90 m grid.

Rules fixed before any slope score was looked at:
- **Primary arm "wind + slope":** Version 1a wind (average of the dry hours) with k fixed at 1, the value chosen on the tune fires in Part 2. b in {0, 1, 2, 3, 4}.
- **Secondary arm "slope only" (exploratory):** no wind (k = 0), same b values.
- b is chosen on the tune fires only, separately for each arm. The test fires are reported at that b next to b = 0 and the round-fire baseline.
- Same 12 fires, same tune/test split, 10 random seeds per setting. Check: with b = 0 the wind + slope arm reproduces the Part 2 scores at k = 1 exactly.

**Table 8. Tune fires: mean IoU by slope strength b**

| b | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| Wind + slope (k = 1) | **0.433** | 0.428 | 0.422 | 0.402 | 0.366 |
| Slope only (k = 0) | 0.336 | 0.340 | 0.342 | 0.345 | **0.347** |

Round-fire baseline on the tune fires: 0.338. Chosen b: 0 for wind + slope, 4 for slope only (the largest value tried).

**Test fires**

| Fire | Year | Shape | Mean slope (deg) | Round baseline | Slope only, b = 0 | Slope only, b = 4 | Wind (k = 1), b = 0 | Wind + slope, b = 0 (chosen) |
|---|---|---|---|---|---|---|---|---|
| French | 2014 | medium | 17.1 | 0.361 | 0.357 | 0.350 | 0.246 | 0.246 |
| Caples | 2019 | long | 14.2 | 0.476 | 0.470 | 0.470 | 0.301 | 0.301 |
| Slink | 2020 | round | 16.5 | 0.272 | 0.273 | 0.305 | 0.252 | 0.252 |
| Tiltill | 2021 | long | 18.2 | 0.250 | 0.254 | 0.328 | 0.505 | 0.505 |
| Oak | 2022 | round | 13.2 | 0.488 | 0.487 | 0.508 | 0.551 | 0.551 |
| Fresno June Lightning Complex | 2024 | medium | 13.9 | 0.392 | 0.381 | 0.421 | 0.535 | 0.535 |

Mean IoU on the test fires: wind + slope 0.398 (identical to Version 1a, because b = 0 was chosen); slope only 0.397 against 0.370 with no slope and 0.373 for the round baseline.

**Table 8b. All 12 fires (mean IoU)**

| Fire | Year | Split | Relief (m) | Mean slope (deg) | Round baseline | Wind b0 | Wind b2 | Wind b4 | Slope-only b0 | Slope-only b2 | Slope-only b4 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Aspen | 2013 | tune | 2,015 | 18.5 | 0.298 | 0.475 | 0.445 | 0.417 | 0.303 | 0.295 | 0.302 |
| French | 2014 | test | 1,454 | 17.1 | 0.361 | 0.246 | 0.259 | 0.283 | 0.357 | 0.348 | 0.350 |
| Washington | 2015 | tune | 1,204 | 17.1 | 0.153 | 0.455 | 0.464 | 0.382 | 0.157 | 0.140 | 0.131 |
| Cedar | 2016 | tune | 1,643 | 17.7 | 0.307 | 0.592 | 0.571 | 0.413 | 0.308 | 0.316 | 0.321 |
| Creek | 2017 | tune | 422 | 12.7 | 0.426 | 0.291 | 0.288 | 0.295 | 0.408 | 0.418 | 0.421 |
| Caples | 2019 | test | 653 | 14.2 | 0.476 | 0.301 | 0.282 | 0.263 | 0.470 | 0.469 | 0.470 |
| Fork | 2020 | tune | 480 | 9.1 | 0.377 | 0.418 | 0.406 | 0.387 | 0.373 | 0.384 | 0.396 |
| Slink | 2020 | test | 1,368 | 16.5 | 0.272 | 0.252 | 0.292 | 0.313 | 0.273 | 0.286 | 0.305 |
| French | 2021 | tune | 1,195 | 15.9 | 0.470 | 0.365 | 0.355 | 0.304 | 0.468 | 0.499 | 0.513 |
| Tiltill | 2021 | test | 851 | 18.2 | 0.250 | 0.505 | 0.519 | 0.428 | 0.254 | 0.296 | 0.328 |
| Oak | 2022 | test | 753 | 13.2 | 0.488 | 0.551 | 0.531 | 0.443 | 0.487 | 0.502 | 0.508 |
| Fresno June Lightning Complex | 2024 | test | 862 | 13.9 | 0.392 | 0.535 | 0.538 | 0.527 | 0.381 | 0.403 | 0.421 |
| **Mean** | | | | | **0.356** | **0.416** | **0.413** | **0.371** | **0.353** | **0.363** | **0.372** |

#### What the slope results show

- **On top of wind, slope adds nothing.** The tune score falls steadily as b rises (0.433 to 0.366), so b = 0 was chosen and the test result equals Version 1a. Over all 12 fires the mean is 0.416 at b = 0, 0.413 at b = 2 and 0.371 at b = 4. Slope at b = 2 beats b = 0 on 5 of 12 fires.
- **Alone, slope helps a little.** With no wind the tune score rises slightly with b (0.336 to 0.347). On the test fires, slope only (b = 4) scores 0.397 against 0.370 with no slope, and beats no slope on 5 of 6 test fires (9 of 12 fires overall). The largest gains are Tiltill (+0.074), French 2021 (+0.045), Fresno June Lightning (+0.040) and Slink (+0.032).
- **That gain is small and weakly supported.** The tune-set rise (+0.011) is within noise, the best b is the largest value tried (b > 4 was not tested), and this arm was exploratory. Over all 12 fires slope only (0.372) is about the same as the round baseline (0.356) plus noise, and well below wind (0.416).
- **The gain does not track steepness.** Across the 12 fires the correlation between the slope-only gain and mean slope is about -0.05, and with relief about -0.27. The fires with the largest gains are not the steepest.
- **Wind carries most of the usable signal.** Wind alone adds about +0.06 over a round fire. Slope alone adds about +0.02. Together they are no better than wind alone. A possible reason is that the weather direction already captures what slope would add, but this was not tested.

#### Limitations specific to slope

- The slope rule is a simple exponential in rise / run, not a physical fire-behaviour model, and b is a tuning knob. Fuel, moisture and canopy are not modelled, and steep terrain in the Sierra Nevada also changes the local wind, which the 10 km weather data cannot see.
- b was tried only at 0, 1, 2, 3 and 4. Values above 4 and other forms of the rule (for example a different cap) were not tried.
- Elevation is averaged to 90 m, which smooths steep, narrow terrain.
- Same 12 fires, 10 seeds, rough ignition estimates and given final area as in Parts 2 and 3. Differences below about 0.05 are within noise.

#### Reproduce

```
python scripts/run_validation_slope.py "data/raw/<perimeter file>"
```

### Overall: what to claim and what not to claim

- Claim: a simple wind-biased grid model reproduces the shape of some past fires better than a round fire of the same area (7 to 9 of 12), with a small average gain.
- Do not claim: that it predicts how a new fire will spread, that k = 2 is a good setting (it was tuned on Goose only), that 1b is better than 1a, or that slope improves the model (on top of wind it did not; alone the gain was small and exploratory).
- Everything above uses the final area, estimated ignition points and 10 km weather. Fuel and moisture are not modelled, and slope is a simple rule.
