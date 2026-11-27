import type { ReactNode } from "react";
import { PLACEHOLDERS } from "./layerRegistry";
import type { LayerDef, LegendItem } from "./layerRegistry";

interface Props {
  layers: LayerDef[];
  layerId: string;
  onLayer: (id: string) => void;
  mode: "history" | "live";
  onMode: (m: "history" | "live") => void;
  opacity: number;
  onOpacity: (v: number) => void;
  basemap: "streets" | "satellite";
  onBasemap: (b: "streets" | "satellite") => void;
  dimLow: boolean;
  onDimLow: (v: boolean) => void;
  showBurned: boolean;
  onShowBurned: (v: boolean) => void;
  legend: LegendItem[];
  legendNote: string;
  liveNote: ReactNode;
  compareOn: boolean;
}

export default function LayerControls(p: Props) {
  return (
    <div>
      <h2>View</h2>
      <div className="seg">
        <button className={p.mode === "history" ? "on" : ""} onClick={() => p.onMode("history")}>History</button>
        <button className={p.mode === "live" ? "on" : ""} onClick={() => p.onMode("live")}>Latest 30 days (live)</button>
      </div>
      {p.liveNote}

      <h2>M1 Forest health</h2>
      {p.layers.map((l) => (
        <label key={l.id} className={`option ${p.layerId === l.id && !p.compareOn ? "on" : ""}`}>
          <input type="radio" name="layer" checked={p.layerId === l.id} onChange={() => p.onLayer(l.id)} style={{ display: "none" }} />
          <b>{l.label}</b>
          <small>{l.blurb}</small>
        </label>
      ))}

      <h2>Other modules</h2>
      {PLACEHOLDERS.map((l) => (
        <div key={l.module} className="option off">
          <b>{l.module} {l.label}</b>
          <small>Not connected yet</small>
        </div>
      ))}

      <h2>Legend</h2>
      <div className="legend">
        {p.legend.map((i) => (
          <div key={i.label}><span className="swatch" style={{ background: i.color }} />{i.label}</div>
        ))}
      </div>
      <p className="muted">{p.compareOn ? "Difference in condition index between the two chosen frames." : p.legendNote}</p>

      <h2>Display</h2>
      <label className="check">
        Opacity
        <input type="range" min={0.2} max={1} step={0.05} value={p.opacity} onChange={(e) => p.onOpacity(Number(e.target.value))} />
      </label>
      <div className="seg">
        <button className={p.basemap === "satellite" ? "on" : ""} onClick={() => p.onBasemap("satellite")}>Satellite</button>
        <button className={p.basemap === "streets" ? "on" : ""} onClick={() => p.onBasemap("streets")}>Streets</button>
      </div>
      <label className="check"><input type="checkbox" checked={p.showBurned} onChange={(e) => p.onShowBurned(e.target.checked)} />Outline mostly burned patches</label>
      <label className="check"><input type="checkbox" checked={p.dimLow} onChange={(e) => p.onDimLow(e.target.checked)} />Dim limited-quality patches (mostly under 50% tree cover)</label>
    </div>
  );
}