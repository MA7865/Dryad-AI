var aoi = ee.Geometry.Rectangle([-119.50, 37.00, -119.25, 37.20]);
Map.centerObject(aoi, 10);

function maskClouds(img) {
  var scl = img.select('SCL');
  var m = scl.neq(3).and(scl.neq(8)).and(scl.neq(9))
             .and(scl.neq(10)).and(scl.neq(11));
  return img.updateMask(m);
}

function addIndices(img) {
  return img.addBands([
    img.normalizedDifference(['B8', 'B4']).rename('NDVI'),
    img.normalizedDifference(['B8', 'B11']).rename('NDMI'),
    img.normalizedDifference(['B8', 'B12']).rename('NBR')
  ]);
}

function rawSummer(year) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(aoi)
    .filterDate(year + '-06-01', year + '-10-01')
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60));
}

function summer(year) {
  return rawSummer(year).map(maskClouds).map(addIndices)
    .select(['NDVI', 'NDMI', 'NBR']).median().clip(aoi);
}

// Forest mask: ESA WorldCover class 10 = tree cover
var forest = ee.ImageCollection('ESA/WorldCover/v200').first()
  .select('Map').eq(10).clip(aoi);

// Burned areas 2015-2024 (MODIS, 500 m, coarse)
var burned = ee.ImageCollection('MODIS/061/MCD64A1')
  .filterDate('2015-01-01', '2025-01-01')
  .select('BurnDate').max().unmask(0).gt(0).clip(aoi);
print('Share of box burned 2015-2024 (MODIS):',
  burned.reduceRegion({
    reducer: ee.Reducer.mean(), geometry: aoi,
    scale: 500, maxPixels: 1e9
  }));

print('Share of box that is tree cover:',
  forest.reduceRegion({
    reducer: ee.Reducer.mean(), geometry: aoi,
    scale: 100, maxPixels: 1e9
  }));

var years = [2021, 2022, 2023, 2024];

years.forEach(function(y) {
  var raw = rawSummer(y);
  var comp = summer(y);

  print('Scenes ' + y, raw.size());

  // Share of FOREST pixels that have cloud-free data in the composite
  var validForest = comp.select('NDMI').mask().rename('valid_forest')
    .updateMask(forest);
  print('Valid share of forest ' + y,
    validForest.reduceRegion({
      reducer: ee.Reducer.mean(), geometry: aoi,
      scale: 100, maxPixels: 1e9, tileScale: 4
    }));

  print('Forest-mean indices ' + y,
    comp.updateMask(forest).reduceRegion({
      reducer: ee.Reducer.mean(), geometry: aoi,
      scale: 100, maxPixels: 1e9, tileScale: 4
    }));
});

Map.addLayer(forest.selfMask(), {palette: ['darkgreen']}, 'Forest mask (WorldCover)', false);
Map.addLayer(burned.selfMask(), {palette: ['red']}, 'Burned 2015-2024 (MODIS)');
Map.addLayer(summer(2024).updateMask(forest).select('NDMI'),
  {min: 0, max: 0.6, palette: ['brown', 'yellow', 'green']}, 'NDMI 2024 (forest only)');
Map.addLayer(aoi, {color: 'yellow'}, 'AOI', true);