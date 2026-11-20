"""ee_check.py -- checks that Python can talk to Earth Engine and shows the latest imagery date."""
import ee

PROJECT = "gen-lang-client-0751448138"      # the project in your grid asset path
ee.Initialize(project=PROJECT)

aoi = ee.Geometry.Rectangle([-119.50, 37.00, -119.25, 37.20])
s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
      .filterBounds(aoi)
      .filterDate("2026-10-01", "2026-12-01"))

print("Scenes since 1 Oct 2026:", s2.size().getInfo())
latest = s2.sort("system:time_start", False).first()
print("Latest scene date:", ee.Date(latest.get("system:time_start")).format("YYYY-MM-dd").getInfo())