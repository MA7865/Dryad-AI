import { useState } from "react";
import ErrorBox from "../data/ErrorBox";
import type { ApiError } from "../data/dryadApi";
import type { Frame, PatchDetail, PatchSeries } from "../data/types";
import { BAND_COLORS } from "../layers/layerRegistry";

interface Props {
  patchId: string;
  detail: PatchDetail | null;
  error: ApiError | null;
  onRetry: () => void;
  series?: PatchSeries;
  frames: Frame[];
  frameIndex: number;
  cutoffs?: { elevated: number; high: number };
  onClose: () => void;
}

const SERIES = [
  { key: "health_index", label: "Condition index", digits: 0 },
  { key: "ndvi", label: "NDVI", digits: 2 },
  { key: "ndmi", label: "NDMI", digits: 2 },
  { key: "mortality_likelihood", label: "Mortality likelihood", digits: 3 },
] as const;

const ARROWS: Record<string, string> = {
  "Improving vs peers": "↑",
  "Stable vs peers": "→",
  "Declining vs peers": "↓",
  Recovering: "↗",
  "Not enough data": "–",
};
const MORT_COLORS: Record<string, string> = { Lower: "#3B9E5A", Elevated: "#E0A526", High: "#C8452F" };

const NA = "Data unavailable";
const fmt = (v: number | null | undefined, d: number) => (v == null ? NA : v.toFixed(d));

function mortBand(v: number | null | undefined, cut?: { elevated: number; high: number }) {
  if (v == null || !cut) return null;
  return v >= cut.high ? "High" : v >= cut.elevated ? "Elevated" : "Lower";
}

function Pill({ text, color }: { text: string; color: string }) {
  return <span className="pill" style={{ background: color }}>{text}</span>;
}

function LineChart({ frames, values, current, digits }: { frames: Frame[]; values: (number | null)[]; current: number; digits: number }) {
  const W = 350, H = 140, L = 38, R = 8, T = 10, B = 24;
  const nums = values.filter((v): v is number => v != null);
  if (nums.length === 0) return <p className="muted">No values for this series.</p>;
  let lo = Math.min(...nums), hi = Math.max(...nums);
  if (hi - lo < 1e-9) { lo -= 1; hi += 1; }
  const pad = (hi - lo) * 0.12;
  lo -= pad; hi += pad;
  const n = Math.max(1, frames.length - 1);
  const x = (i: number) => L + (i * (W - L - R)) / n;
  const y = (v: number) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const paths: string[] = [];
  let cur = "";
  values.forEach((v, i) => {
    if (v == null) { if (cur) paths.push(cur); cur = ""; }
    else cur += `${cur ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
  });
  if (cur) paths.push(cur);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Series over time">
      <line x1={L} x2={W - R} y1={H - B} y2={H - B} stroke="#cfd8d2" />
      <text x={4} y={T + 8} fontSize="10" fill="#66726c">{hi.toFixed(digits)}</text>
      <text x={4} y={H - B} fontSize="10" fill="#66726c">{lo.toFixed(digits)}</text>
      <text x={L} y={H - 6} fontSize="10" fill="#66726c">{frames[0]?.year}</text>
      <text x={W - R} y={H - 6} fontSize="10" fill="#66726c" textAnchor="end">{frames[frames.length - 1]?.year}</text>
      <line x1={x(current)} x2={x(current)} y1={T} y2={H - B} stroke="#14231b" strokeDasharray="3 3" />
      {paths.map((d, k) => <path key={k} d={d} fill="none" stroke="#3B9E5A" strokeWidth="1.5" />)}
      {values.map((v, i) =>
        v == null ? null : (
          <circle key={i} cx={x(i)} cy={y(v)} r={i === current ? 4.5 : 2.5}
            fill={frames[i].season === "summer" ? "#14231b" : "#ffffff"} stroke="#14231b" strokeWidth="1" />
        ),
      )}
    </svg>
  );
}

function Sparkline({ values }: { values: (number | null)[] }) {
  const nums = values.filter((v): v is number => v != null);
  if (nums.length < 2) return null;
  const lo = Math.min(...nums), span = Math.max(...nums) - lo || 1;
  const pts = values
    .map((v, i) => (v == null ? null : `${4 + (i * 120) / (values.length - 1)},${24 - ((v - lo) / span) * 20}`))
    .filter(Boolean)
    .join(" ");
  return (
    <svg width="128" height="28" viewBox="0 0 128 28" aria-label="Condition index by summer">
      <polyline points={pts} fill="none" stroke="#66726c" strokeWidth="1.5" />
    </svg>
  );
}

export default function PatchDetails(p: Props) {
  const [which, setWhich] = useState<(typeof SERIES)[number]["key"]>("health_index");
  const d = p.detail && p.detail.patch_id === p.patchId ? p.detail : null;
  const frame = p.frames[p.frameIndex];
  const s = p.series;
  const lk = s?.mortality_likelihood[p.frameIndex] ?? null;
  const pc = s?.mortality_percentile[p.frameIndex] ?? null;
  const band = mortBand(lk, p.cutoffs);
  const idxNow = s?.health_index[p.frameIndex] ?? null;
  const bandNow = s?.health_band[p.frameIndex] ?? null;
  const chosen = SERIES.find((x) => x.key === which) ?? SERIES[0];
  const live = d?.live ?? null;

  return (
    <div>
      <div className="panel-head">
        <h3>Patch {p.patchId}</h3>
        <button onClick={p.onClose}>Close</button>
      </div>
      {p.error && <ErrorBox title="Could not load this patch" error={p.error} onRetry={p.onRetry} />}
      {!d && !p.error && <p className="muted">Loading patch details...</p>}

      {d && (
        <>
          <p className="muted">
            Burn status: {d.burn_status} | Data quality: {d.data_quality}
            {frame && <> | Showing: {frame.label}</>}
          </p>

          <div className="kv">
            <span>Mortality likelihood (model)</span>
            <span className="val">
              {frame?.season !== "summer" ? <span className="muted">Summer frames only</span>
                : lk == null ? <span className="muted">Not scored (burned or too little forest)</span>
                : <><b>{lk.toFixed(3)}</b>{band && <Pill text={band} color={MORT_COLORS[band]} />}</>}
            </span>
          </div>
          <div className="kv">
            <span>Rank among Shaver Lake patches</span>
            <span className="val">{pc == null ? "–" : `${pc.toFixed(0)}th percentile (higher = more likely)`}</span>
          </div>
          <div className="kv">
            <span>Condition index</span>
            <span className="val">
              {idxNow == null ? NA : <><b>{idxNow.toFixed(0)} / 100</b>{bandNow && <Pill text={bandNow} color={BAND_COLORS[bandNow] ?? "#BDBDBD"} />}</>}
            </span>
          </div>
          <div className="kv">
            <span>NDVI / NDMI</span>
            <span className="val">{fmt(s?.ndvi[p.frameIndex], 2)} / {fmt(s?.ndmi[p.frameIndex], 2)}</span>
          </div>
          <div className="kv">
            <span>5-summer trend</span>
            <span className="val">
              <Sparkline values={d.history.map((h) => h.health_index)} />
              <div><b>{ARROWS[d.trend_label] ?? "–"} {d.trend_label}</b></div>
              <div className="muted">{d.trend_slope == null ? NA : `${d.trend_slope} points per year`} | context only</div>
            </span>
          </div>

          <h2>Over time</h2>
          <div className="seg" style={{ flexWrap: "wrap", marginBottom: 6 }}>
            {SERIES.map((x) => (
              <button key={x.key} className={which === x.key ? "on" : ""} onClick={() => setWhich(x.key)}>{x.label}</button>
            ))}
          </div>
          {s ? <LineChart frames={p.frames} values={s[chosen.key]} current={p.frameIndex} digits={chosen.digits} />
             : <p className="muted">{NA}</p>}
          <p className="muted">Filled dots are summers, hollow dots experimental seasonal frames. Mortality exists for summers only.</p>

          <h2>Live window</h2>
          {live ? (
            <>
              <div className="kv"><span>Window</span><span className="val">{live.window_start} to {live.window_end}</span></div>
              <div className="kv"><span>Condition index</span><span className="val">{live.health_index == null ? NA : `${live.health_index} / 100`} {live.health_band}</span></div>
              <div className="kv"><span>NDVI / NDMI</span><span className="val">{fmt(live.ndvi, 2)} / {fmt(live.ndmi, 2)}</span></div>
              <div className="kv"><span>Clear observations / quality</span><span className="val">{live.obs_count ?? NA} / {live.data_quality}</span></div>
              <div className="kv"><span>Mortality (latest completed summer)</span>
                <span className="val">{live.mortality_likelihood == null ? (live.model_status ?? NA) : `${live.mortality_likelihood.toFixed(3)} (${live.mortality_band})`}</span></div>
              <p className="muted">{live.note}</p>
              {live.model_note && <p className="muted">{live.model_note}</p>}
            </>
          ) : <p className="muted">Live values unavailable.</p>}

          <h2>About this patch</h2>
          <p style={{ fontSize: 13 }}>{d.explanation}</p>
          <p className="muted">
            Source: {d.source}. Condition model {d.model_version}.
            {live?.mortality_model_version && <> Mortality model {live.mortality_model_version}, climate year {live.mortality_climate_year ?? NA} (latest available).</>}
          </p>
          <p className="muted">Condition and trend are context, not diagnoses or damage warnings. Mortality likelihood is relative to surveyed forest, not a real-world probability.</p>
        </>
      )}
    </div>
  );
}