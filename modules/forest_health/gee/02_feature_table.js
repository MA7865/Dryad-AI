var GRID_ASSET = 'projects/gen-lang-client-0751448138/assets/dryad_grid';

var grid = ee.FeatureCollection(GRID_ASSET);
var aoi = grid.geometry().bounds();
print('Grid cells (expect 2061):', grid.size());

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

function summerCollection(year) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(aoi)
    .filterDate(year + '-06-01', year + '-10-01')
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60));
}

function summer(year) {
  return summerCollection(year).map(maskClouds).map(addIndices)
    .select(['NDVI', 'NDMI', 'NBR']).median();
}

var forest = ee.ImageCollection('ESA/WorldCover/v200').first()
  .select('Map').eq(10);

// Any burn since 2015 (MODIS, 500 m, coarse)
var burned = ee.ImageCollection('MODIS/061/MCD64A1')
  .filterDate('2015-01-01', '2026-12-01')
  .select('BurnDate').max().unmask(0).gt(0);

var years = [2022, 2023, 2024, 2025, 2026];

years.forEach(function(y) {
  print('Scenes ' + y, summerCollection(y).size());
});

function featuresFor(y) {
  var img = summer(y);
  var stack = img
    .updateMask(forest)
    .addBands(img.select('NDMI').mask().rename('valid'))
    .addBands(forest.rename('forest_frac'))
    .addBands(burned.rename('burn_frac'));

  return stack.reduceRegions({
    collection: grid,
    reducer: ee.Reducer.mean(),
    scale: 20,
    tileScale: 4
  }).map(function(f) { return f.set('year', y); });
}

var all = ee.FeatureCollection([]);
years.forEach(function(y) {
  all = all.merge(featuresFor(y));
});

print('Rows (expect 2061 x 5 = 10305):', all.size());

Export.table.toDrive({
  collection: all,
  description: 'm1_features_2022_2026',
  folder: 'forest_sentinel',
  fileFormat: 'CSV',
  selectors: ['patch_id', 'row', 'col', 'year', 'NDVI', 'NDMI', 'NBR',
              'valid', 'forest_frac', 'burn_frac']
});