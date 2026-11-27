import { useEffect, useMemo, useState } from "react";
import { api, useAsync } from "./data/dryadApi";
import type { ApiError } from "./data/dryadApi";
import ErrorBox from "./data/ErrorBox";
import type { LayerProps, StatusInfo } from "./data/types";
import { GREY, M1_LAYERS, diffColor, mix, valueAt } from "./layers/layerRegistry";
import type { LegendItem } from "./layers/layerRegistry";
import LayerControls from "./layers/LayerControls";
import ForestMap from "./map/ForestMap";
import TimelineControls from "./timeline/TimelineControls";
import type { CompareState } from "./timeline/TimelineControls";
import PatchDetails from "./patches/PatchDetails";
import ModelCardPanel from "./model/ModelCardPanel";

const COMPARE_LEGEND: LegendItem[] = [
  { color: diffColor(-40), label: "Condition fell (40+ points)" },
  { color: diffColor(0), label: "No change" },
  { color: diffColor(40), label: "Condition rose (40+ points)" },
  { color: GREY, label: "No data in one of the frames" },
];

function statusChip(s: StatusInfo | null, err: ApiError | null): { text: string; tone: string } {
  if (err) return { text: `API unreachable (${err.status || "no response"})`, tone: "bad" };
  if (!s) return { text: "Connecting...", tone: "warn" };
  const ls = s.live_status;
  if (s.live) {
    return {
      text: `Live: refreshed ${ls.age_minutes ?? "?"} min ago, newest scene ${s.live.newest_scene}`,
      tone: ls.error ? "warn" : "ok",
    };
  }
  if (ls.error) return { text: "Live data unavailable", tone: "warn" };
  if (!ls.enabled) return { text: "Live refresh disabled", tone: "warn" };
  return { text: "Live layer computing", tone: "warn" };
}

export default function App() {
  const geometry = useAsync(() => api.layerSummer(), []);
  const timeline = useAsync(() => api.timeline(), []);
  const status = useAsync(() => api.status(), []);
  const card = useAsync(() => api.modelCard(), []);

  const [mode, setMode] = useState<"history" | "live">("history");
  const live = useAsync(() => api.layerLive(), [], mode === "live");
  const [layerId, setLayerId] = useState("condition");
  const [frameIdx, setFrameIdx] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [speedMs, setSpeedMs] = useState(1200);
  const [compare, setCompare] = useState<CompareState>({ on: false, a: 0, b: 0 });
  const [opacity, setOpacity] = useState(0.75);
  const [basemap, setBasemap] = useState<"streets" | "satellite">("satellite");
  const [dimLow, setDimLow] = useState(false);
  const [showBurned, setShowBurned] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(false);
  const [menu, setMenu] = useState(false);

  const detail = useAsync(() => api.patch(selectedId as string), [selectedId], selectedId !== null);

  const frames = timeline.data?.frames ?? [];
  const firstSummer = Math.max(0, frames.findIndex((f) => f.season === "summer"));
  const lastSummer = useMemo(() => {
    let k = 0;
    (timeline.data?.frames ?? []).forEach((f, i) => { if (f.season === "summer") k = i; });
    return k;
  }, [timeline.data]);
  const idx = frameIdx ?? lastSummer;

  // Refresh the status chip every minute.
  useEffect(() => {
    const t = setInterval(status.reload, 60000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The live layer answers 503 while it is first computed: retry every 20 seconds.
  useEffect(() => {
    if (mode === "live" && live.error?.status === 503) {
      const t = setTimeout(live.reload, 20000);
      return () => clearTimeout(t);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, live.error]);

  // Play: step through the frames and loop.
  useEffect(() => {
    if (!playing || compare.on || mode === "live" || frames.length === 0) return;
    const t = setInterval(() => setFrameIdx((i) => ((i ?? lastSummer) + 1) % frames.length), speedMs);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, speedMs, compare.on, mode, frames.length, lastSummer]);

  const staticById = useMemo(() => {
    const m = new Map<string, LayerProps>();
    geometry.data?.features.forEach((f) => m.set(f.properties.patch_id, f.properties));
    return m;
  }, [geometry.data]);
  const liveById = useMemo(() => {
    const m = new Map<string, LayerProps>();
    live.data?.features.forEach((f) => m.set(f.properties.patch_id, f.properties));
    return m;
  }, [live.data]);

  const layer = M1_LAYERS.find((l) => l.id === layerId) ?? M1_LAYERS[0];
  const liveFirst = live.data?.features[0]?.properties;
  const isLive = mode === "live";

  const colorOf = useMemo(() => {
    const tl = timeline.data;
    if (!tl || !geometry.data) return null;
    return (id: string): string => {
      const series = tl.patches[id];
      const ctx = {
        frameIndex: idx,
        series,
        liveProps: liveById.get(id),
        staticProps: staticById.get(id),
        live: isLive && layer.id !== "trend",
      };
      let color: string;
      if (compare.on && !isLive) {
        const a = series?.health_index[compare.a] ?? null;
        const b = series?.health_index[compare.b] ?? null;
        color = diffColor(a == null || b == null ? null : b - a);
      } else {
        color = layer.color(ctx);
      }
      if (dimLow && valueAt(ctx, "data_quality") === "limited") color = mix(color, "#FFFFFF", 0.55);
      return color;
    };
  }, [timeline.data, geometry.data, idx, layer, compare, isLive, dimLow, liveById, staticById]);

  const viewKey = [mode, layer.id, idx, compare.on ? `${compare.a}-${compare.b}` : "", dimLow, live.data ? "L" : "-"].join("|");

  const windowText = isLive
    ? liveFirst ? `${liveFirst.window_start} to ${liveFirst.window_end}, newest scene ${liveFirst.observed_at?.slice(0, 10)}` : ""
    : compare.on ? `${frames[compare.a]?.label ?? ""} to ${frames[compare.b]?.label ?? ""}`
    : frames[idx] ? `${frames[idx].window[0]} to ${frames[idx].window[1]}` : "";

  const onCompare = (c: CompareState) => {
    if (c.on && !compare.on) setCompare({ on: true, a: firstSummer, b: lastSummer });
    else setCompare(c);
    if (c.on) setPlaying(false);
  };

  const liveNote = isLive ? (
    live.loading && !live.data ? <div className="info">Loading the live layer...</div>
    : live.error ? (
      live.error.status === 503
        ? <div className="info">The live layer is being computed from Earth Engine. Retrying every 20 seconds. <button onClick={live.reload}>Retry now</button></div>
        : <ErrorBox title="Live layer failed" error={live.error} onRetry={live.reload} />
    ) : <div className="info">Live window: {windowText}. The condition index is relative to unburned patches in the same window. The mortality score applies to the latest completed summer.</div>
  ) : null;

  const chip = statusChip(status.data, status.error);
  const cutoffs = card.data?.bands ? { elevated: card.data.bands.elevated, high: card.data.bands.high } : undefined;

  return (
    <div className="app">
      <header className="header">
        <button className="menu-btn" onClick={() => setMenu(!menu)}>Layers</button>
        <h1>AI Forest Sentinel</h1>
        <span className="area">Shaver Lake, California | M1 forest health</span>
        <span className="spacer" />
        <span className={`chip ${chip.tone}`}>{chip.text}</span>
        <button onClick={() => setDrawer(true)}>About this score</button>
      </header>

      <div className="body">
        <aside className={`left ${menu ? "open" : ""}`}>
          <LayerControls
            layers={M1_LAYERS}
            layerId={layerId}
            onLayer={setLayerId}
            mode={mode}
            onMode={(m) => { setMode(m); if (m === "live") setPlaying(false); }}
            opacity={opacity}
            onOpacity={setOpacity}
            basemap={basemap}
            onBasemap={setBasemap}
            dimLow={dimLow}
            onDimLow={setDimLow}
            showBurned={showBurned}
            onShowBurned={setShowBurned}
            legend={compare.on && !isLive ? COMPARE_LEGEND : layer.legend}
            legendNote={layer.legendNote}
            liveNote={liveNote}
            compareOn={compare.on && !isLive}
          />
        </aside>

        <main className="center">
          {geometry.error ? (
            <div style={{ padding: 16 }}>
              <ErrorBox title="Could not load the patch grid" error={geometry.error} onRetry={geometry.reload} />
            </div>
          ) : geometry.data && colorOf ? (
            <ForestMap
              geometry={geometry.data}
              colorOf={colorOf}
              viewKey={viewKey}
              opacity={opacity}
              basemap={basemap}
              showBurned={showBurned}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          ) : (
            <div className="loading">Loading patches...</div>
          )}

          <div className="bottom">
            {timeline.error ? (
              <ErrorBox title="Could not load the timeline" error={timeline.error} onRetry={timeline.reload} />
            ) : timeline.data ? (
              <TimelineControls
                frames={frames}
                index={idx}
                onIndex={setFrameIdx}
                playing={playing}
                onPlaying={setPlaying}
                speedMs={speedMs}
                onSpeed={setSpeedMs}
                compare={compare}
                onCompare={onCompare}
                notes={timeline.data.notes}
                windowText={windowText}
                live={isLive}
              />
            ) : (
              <span className="muted">Loading timeline...</span>
            )}
          </div>
        </main>

        {selectedId && (
          <aside className="right">
            <PatchDetails
              patchId={selectedId}
              detail={detail.data}
              error={detail.error}
              onRetry={detail.reload}
              series={timeline.data?.patches[selectedId]}
              frames={frames}
              frameIndex={idx}
              cutoffs={cutoffs}
              onClose={() => setSelectedId(null)}
            />
          </aside>
        )}
      </div>

      {drawer && (
        <ModelCardPanel card={card.data} error={card.error} loading={card.loading} onRetry={card.reload} onClose={() => setDrawer(false)} />
      )}
    </div>
  );
}