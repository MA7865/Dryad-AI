import type { Frame } from "../data/types";

export interface CompareState {
  on: boolean;
  a: number;
  b: number;
}

interface Props {
  frames: Frame[];
  index: number;
  onIndex: (i: number) => void;
  playing: boolean;
  onPlaying: (v: boolean) => void;
  speedMs: number;
  onSpeed: (ms: number) => void;
  compare: CompareState;
  onCompare: (c: CompareState) => void;
  notes: string[];
  windowText: string;
  live: boolean;
}

export default function TimelineControls(p: Props) {
  const n = p.frames.length;
  const f = p.frames[p.index];
  const step = (d: number) => p.onIndex((p.index + d + n) % n);

  if (p.live) {
    return (
      <div className="tl-row">
        <span className="tl-label">Latest 30 days (live)</span>
        <span className="muted">{p.windowText}</span>
      </div>
    );
  }

  return (
    <div>
      <div className="tl-row">
        <button onClick={() => step(-1)} disabled={p.compare.on}>Prev</button>
        <button className="primary" onClick={() => p.onPlaying(!p.playing)} disabled={p.compare.on}>
          {p.playing ? "Pause" : "Play"}
        </button>
        <button onClick={() => step(1)} disabled={p.compare.on}>Next</button>
        <span className="tl-label">{p.compare.on ? "Compare two frames" : f?.label}</span>
        {!p.compare.on && f && f.season !== "summer" && (
          <span className="badge exp">experimental, relative to the same season</span>
        )}
        <span className="muted">{p.windowText}</span>
        <span style={{ flex: 1 }} />
        <select value={p.speedMs} onChange={(e) => p.onSpeed(Number(e.target.value))} aria-label="Playback speed">
          <option value={2000}>Slow</option>
          <option value={1200}>Normal</option>
          <option value={600}>Fast</option>
        </select>
        <label className="check">
          <input type="checkbox" checked={p.compare.on} onChange={(e) => p.onCompare({ ...p.compare, on: e.target.checked })} />
          Compare
        </label>
      </div>

      {p.compare.on ? (
        <div className="tl-row" style={{ marginTop: 8 }}>
          <label>From{" "}
            <select value={p.compare.a} onChange={(e) => p.onCompare({ ...p.compare, a: Number(e.target.value) })}>
              {p.frames.map((fr, i) => <option key={fr.id} value={i}>{fr.label}</option>)}
            </select>
          </label>
          <label>to{" "}
            <select value={p.compare.b} onChange={(e) => p.onCompare({ ...p.compare, b: Number(e.target.value) })}>
              {p.frames.map((fr, i) => <option key={fr.id} value={i}>{fr.label}</option>)}
            </select>
          </label>
        </div>
      ) : (
        <>
          <div className="ticks">
            {p.frames.map((fr, i) => (
              <span
                key={fr.id}
                title={fr.label}
                className={`tick ${fr.season === "summer" ? "summer" : ""} ${i === p.index ? "on" : ""}`}
                onClick={() => p.onIndex(i)}
              />
            ))}
          </div>
          <input type="range" min={0} max={Math.max(0, n - 1)} value={p.index} onChange={(e) => p.onIndex(Number(e.target.value))} />
        </>
      )}

      <details className="notes">
        <summary>About these frames</summary>
        {p.notes.map((t, i) => <p key={i}>{t}</p>)}
        <p>Darker green ticks are summers (the mortality model applies to these). Light ticks are experimental seasonal frames.</p>
      </details>
    </div>
  );
}