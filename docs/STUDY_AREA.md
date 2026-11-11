# Study Area: Shaver Lake, California

## Bounding box

Order is **west, south, east, north** (longitude/latitude, degrees):

```
west, south, east, north
-119.50, 37.00, -119.25, 37.20
```

Size is about 22 km x 22 km (roughly 490 km2).

## Coordinate systems

- **All GeoJSON output and API responses:** WGS84 lon/lat, `EPSG:4326`.
- **Grid construction and distance/area calculations:** UTM zone 11N, `EPSG:32611` (units are metres).
- **Timestamps:** UTC, ISO 8601 (e.g. `2026-08-15T12:00:00Z`).

## Shared grid

- Cell size: **500 m x 500 m** (0.25 km2).
- Cells: **2,061** (46 rows x 46 columns). Cells along the edge that only partly overlap the box are kept, so the grid can extend up to ~0.5 km beyond it.
- Row 0 is the southern edge, column 0 is the western edge.
- The grid is anchored to round UTM coordinates, so re-running the script gives identical cells.

## patch_id

Format: `P_r{row:03d}_c{col:03d}`, for example `P_r012_c034` (row 12, column 34).

IDs are permanent. Never renumber them.

## The grid file

- File: `data/grid.geojson`
- Built by: `scripts/make_grid.py` (run from the repo root: `python scripts/make_grid.py`)
- Properties: `patch_id`, `row`, `col`, `center_lon`, `center_lat`

**Rule: everyone loads this file. Nobody builds their own grid.** If the grid ever needs to change, update the script and the file together and tell the whole team.

## Assigning observations to patches (proposed, to be confirmed by the team)

- **Point** (e.g. a fire detection): belongs to the cell that contains it.
- **Polygon** (e.g. a fire perimeter): belongs to every cell it intersects; store the fraction of each cell covered where useful.
- **Coarse data** (e.g. ~10 km weather): every cell inside the source pixel gets that pixel's value. Keep the source resolution noted in the layer's metadata.