# AI Forest Sentinel — Frontend Product Specification

## 1. Product overview

Build a polished, responsive web application called **AI Forest Sentinel**, an AI-assisted forest monitoring and wildfire decision-support prototype for a selected study region in California's Sierra Nevada.

The application combines four independently developed intelligence layers:

1. Forest health and stress classification
2. Vegetation classification and supported damage observations
3. Weather forecasts and wildfire ignition-risk scenarios
4. Active-fire monitoring, historical perimeters and optional simulated spread

The central experience is an interactive map. Users should be able to explore a forest patch, enable or disable layers, inspect predictions, view weather information and compare a baseline forecast with a hypothetical weather scenario.

This is a research prototype, not an operational emergency alert system.

## 2. Technology requirements

- Use React and TypeScript.
- Use MapLibre GL JS for the interactive map.
- Use FastAPI as the backend.
- Obtain actual data through documented backend API endpoints.
- Use reusable components and a consistent design system.
- Keep frontend presentation separate from model logic.
- Do not fabricate predictions or use hard-coded numbers as if they came from real models.
- If an endpoint is unavailable during development, allow clearly labelled mock data for development purposes.
- Use environment variables for the backend base URL; do not hard-code deployment addresses throughout the application.

## 3. Visual design

Create a professional geospatial intelligence interface rather than a generic dashboard.

Design direction:
- Dark charcoal or deep forest-green navigation and map controls.
- Light, readable content panels.
- Restrained green, amber, orange and red accents for layer symbology.
- Clear contrast and accessible text sizes.
- Compact cards and charts; the map should remain the main focus.
- Subtle transitions when opening panels or enabling layers.
- Avoid excessive gradients, oversized metric cards and decorative elements that reduce map space.

The application should look suitable for a university research demonstration or an environmental monitoring product.

## 4. Main application layout

### Header
Display:
- AI Forest Sentinel logo/wordmark.
- Current study region.
- Current data mode: Live Forecast, Historical or Scenario.
- Last successful data refresh time.
- A compact data-status indicator.

### Left sidebar — Layer control
Provide independent toggles for:
- Forest Health
- Vegetation Type
- Observed Forest Damage
- Ignition Risk
- Weather
- Active Fire Detections
- Historical Fire Perimeters
- Simulated Fire Spread, when available

Each layer should have:
- A clear name.
- An information icon or short explanation.
- A matching legend.
- Loading, unavailable and error states.
- A visible indication of whether it shows observations, model predictions or simulations.

Do not display a layer as active if its data has failed to load.

### Central map
Use MapLibre with:
- A suitable terrain or satellite basemap.
- The selected study-area boundary.
- Layer toggles and legends.
- Zoom, pan, reset-view and fullscreen controls.
- Clickable forest patches.
- Distinct symbology for polygon patches, active-fire points and fire perimeters.
- A date/time control where historical data supports it.
- A map legend that changes with the active layer.

Use polygon fill colours for patch-based model outputs. Use distinct symbols for point detections and line/fill styling for historical or simulated fire boundaries. Keep layer opacity adjustable where overlapping layers would otherwise obscure one another.

### Right sidebar — Selected patch
When a user clicks a forest patch, display:
- Patch ID and location.
- Forest health/stress prediction and class probabilities, if available.
- Vegetation class and supporting source.
- Observed damage information, if available.
- Current weather and forecast valid time.
- Estimated ignition risk and model version, if available.
- Data coverage and prediction limitations.
- A short explanation of the model's supported input factors.

If a value is missing, show “Data unavailable” rather than zero.

### Bottom panel — Time and comparison
Provide a collapsible panel for:
- Historical observation timeline.
- Forecast timeline.
- Historical fire-perimeter playback.
- Baseline versus scenario comparison.
- Simulated spread timeline, if implemented.

Keep historical observations and future forecasts visually distinct.

## 5. Weather and ignition-risk simulator

Create a dedicated scenario panel with controls for:
- Temperature
- Relative humidity
- Wind speed
- Wind direction, if supported by the model
- Precipitation
- Soil moisture, if supported by the model

Display the baseline forecast values next to the scenario values.

Include:
- A “Reset to forecast” control.
- A “Run scenario” action.
- Baseline estimated risk.
- Scenario estimated risk.
- Absolute or relative change, clearly labelled.
- A map highlighting patches whose model outputs changed.
- A concise explanation of which supported model inputs changed.

The frontend must send overrides to the backend and display the returned model result. It must not invent a risk score using frontend-only formulas.

If the model does not support an input variable, disable that control or clearly explain the limitation.

Label all outputs as estimated risk, not a guarantee that a fire will or will not ignite.

## 6. Fire monitoring

Display active-fire detections and historical fire perimeters as separate layers.

For detections, show available source, observation time and source-provided confidence or quality fields.

For historical perimeters, show the event name, dates and other available metadata.

If simulated spread is available, use a separate style and an explicit “Simulation” label. Never draw a hypothetical perimeter in the same style as an observed fire perimeter.

## 7. API integration

Use the following backend endpoints as the planned contract:

- GET /api/v1/study-area
- GET /api/v1/health
- GET /api/v1/layers/forest-health
- GET /api/v1/layers/vegetation
- GET /api/v1/layers/ignition-risk
- GET /api/v1/weather/forecast
- POST /api/v1/simulations/weather
- GET /api/v1/fires/active
- GET /api/v1/fires/perimeters
- POST /api/v1/simulations/fire-spread

These are planned endpoint names; coordinate exact request parameters and response schemas with the backend team.

All map-layer endpoints should return valid GeoJSON FeatureCollections where appropriate. The frontend must read actual property names from the agreed schema rather than assume every layer has the same properties.

Implement loading indicators, timeouts or error messages, empty states and a retry action.

## 8. Data provenance and confidence

For each layer, provide an information panel with:
- Data source.
- Observation or forecast time.
- Model name and version.
- Prediction target.
- Test metric or evaluation summary when available.
- Known limitations.

Distinguish:
- Directly observed data.
- Model-inferred predictions.
- User-defined scenarios.
- Simulated fire spread.

Do not present a model's uncalibrated score as a probability or imply that a prediction has been independently verified.

## 9. Responsive design

Prioritise desktop and laptop layouts for the demonstration. On smaller screens, collapse sidebars into drawers and preserve map usability.

## 10. Acceptance criteria

The frontend is ready for the MVP when:
1. All available layers can be toggled independently.
2. Clicking a patch displays the correct properties for that patch.
3. Weather forecast data shows units and valid timestamps.
4. Scenario controls call the backend and display returned results.
5. Active-fire observations and simulated spread are visually distinguishable.
6. Loading, empty and error states work.
7. No mock prediction is displayed as a real prediction.
8. The interface clearly explains data sources and limitations.
9. The application remains usable when one layer or API fails.
10. The UI can be deployed independently from the FastAPI backend.