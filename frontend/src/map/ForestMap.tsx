import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { PatchCollection } from "../data/types";

const BOUNDS: [[number, number], [number, number]] = [[-119.53, 36.98], [-119.22, 37.22]];

interface Props {
  geometry: PatchCollection;
  colorOf: (id: string) => string;
  viewKey: string;
  opacity: number;
  basemap: "streets" | "satellite";
  showBurned: boolean;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

export default function ForestMap(p: Props) {
  const box = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const active = useRef<"a" | "b">("a");
  const ids = useRef<string[]>(p.geometry.features.map((f) => f.properties.patch_id));
  const onSelectRef = useRef(p.onSelect);
  onSelectRef.current = p.onSelect;
  const [ready, setReady] = useState(false);

  // Create the map once.
  useEffect(() => {
    if (!box.current) return;
    const map = new maplibregl.Map({
      container: box.current,
      style: {
        version: 8,
        transition: { duration: 700, delay: 0 },
        sources: {
          streets: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            maxzoom: 19,
            attribution: "&copy; OpenStreetMap contributors",
          },
          satellite: {
            type: "raster",
            tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
            tileSize: 256,
            maxzoom: 19,
            attribution: "Imagery &copy; Esri, Maxar, Earthstar Geographics",
          },
        },
        layers: [
          { id: "streets", type: "raster", source: "streets", layout: { visibility: "none" } },
          { id: "satellite", type: "raster", source: "satellite" },
        ],
      } as maplibregl.StyleSpecification,
      bounds: BOUNDS,
      fitBoundsOptions: { padding: 20 },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.FullscreenControl(), "top-right");

    map.on("load", () => {
      map.addSource("patches", { type: "geojson", data: p.geometry as any, promoteId: "patch_id" });
      // Two fill layers take turns: colours are written to the hidden one, then the layers cross-fade.
      for (const k of ["a", "b"] as const) {
        map.addLayer({
          id: `fill-${k}`,
          type: "fill",
          source: "patches",
          paint: {
            "fill-color": ["coalesce", ["feature-state", k], "#BDBDBD"],
            "fill-opacity": 0,
          },
        });
      }
      map.addLayer({
        id: "lines", type: "line", source: "patches",
        paint: { "line-color": "#ffffff", "line-opacity": 0.25, "line-width": 0.4 },
      });
      map.addLayer({
        id: "burned", type: "line", source: "patches",
        filter: ["==", ["get", "burn_status"], "mostly_burned"],
        layout: { visibility: "none" },
        paint: { "line-color": "#35566F", "line-width": 1.2, "line-opacity": 0.9 },
      });
      map.addLayer({
        id: "selected", type: "line", source: "patches",
        filter: ["==", ["get", "patch_id"], ""],
        paint: { "line-color": "#111111", "line-width": 3 },
      });
      setReady(true);
    });

    map.on("click", (e) => {
      const f = map.queryRenderedFeatures(e.point, { layers: ["fill-a", "fill-b"] })[0];
      onSelectRef.current(f ? String(f.properties?.patch_id ?? f.id) : null);
    });
    map.on("mousemove", (e) => {
      const hit = map.queryRenderedFeatures(e.point, { layers: ["fill-a", "fill-b"] }).length > 0;
      map.getCanvas().style.cursor = hit ? "pointer" : "";
    });

    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      setReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // New colours: write them to the hidden layer, then cross-fade.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const next = active.current === "a" ? "b" : "a";
    for (const id of ids.current) {
      map.setFeatureState({ source: "patches", id }, { [next]: p.colorOf(id) });
    }
    map.setPaintProperty(`fill-${next}`, "fill-opacity", p.opacity);
    map.setPaintProperty(`fill-${active.current}`, "fill-opacity", 0);
    active.current = next;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.viewKey, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setPaintProperty(`fill-${active.current}`, "fill-opacity", p.opacity);
  }, [p.opacity, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setLayoutProperty("streets", "visibility", p.basemap === "streets" ? "visible" : "none");
    map.setLayoutProperty("satellite", "visibility", p.basemap === "satellite" ? "visible" : "none");
  }, [p.basemap, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setLayoutProperty("burned", "visibility", p.showBurned ? "visible" : "none");
  }, [p.showBurned, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setFilter("selected", ["==", ["get", "patch_id"], p.selectedId ?? ""]);
  }, [p.selectedId, ready]);

  return <div ref={box} className="map" />;
}