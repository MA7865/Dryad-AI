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
