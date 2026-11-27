import type { LayerProps, PatchSeries } from "../data/types";

export const GREY = "#BDBDBD";

export const BAND_COLORS: Record<string, string> = {
  Healthy: "#3B9E5A",
  "Moderate stress": "#E0A526",
  "High stress": "#C8452F",
  "Post-fire recovery": "#6B8CA6",
  "Not scored": GREY,
};
export const TREND_COLORS: Record<string, string> = {
  "Improving vs peers": "#2E7D32",
  "Stable vs peers": "#7A7A7A",
  "Declining vs peers": "#E0A526",
  Recovering: "#4A7FB5",
  "Not enough data": GREY,
};
export const RAMP = ["#FAEEDA", "#FAC775", "#EF9F27", "#BA7517", "#854F0B"];

function rgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function mix(a: string, b: string, t: number): string {
  const [r1, g1, b1] = rgb(a);
  const [r2, g2, b2] = rgb(b);
  const m = (x: number, y: number) => Math.round(x + (y - x) * t).toString(16).padStart(2, "0");
  return `#${m(r1, r2)}${m(g1, g2)}${m(b1, b2)}`;
}

export function rampColor(p: number | null | undefined): string {
  if (p == null) return GREY;
  return RAMP[Math.min(4, Math.max(0, Math.ceil(p / 20) - 1))];
}

export function diffColor(delta: number | null): string {
  if (delta == null) return GREY;
  const t = Math.max(-1, Math.min(1, delta / 40));
  return t < 0 ? mix("#E6E6E6", "#C8452F", -t) : mix("#E6E6E6", "#3B9E5A", t);
}

export interface ColorCtx {
  frameIndex: number;
  series?: PatchSeries;
  liveProps?: LayerProps;
  staticProps?: LayerProps;
  live: boolean;
}
type Key = "health_band" | "health_index" | "mortality_percentile" | "mortality_likelihood" | "data_quality";

export function valueAt(c: ColorCtx, key: Key): string | number | null {
  const v = c.live
    ? (c.liveProps as unknown as Record<string, string | number | null | undefined> | undefined)?.[key]
    : (c.series?.[key] as (string | number | null)[] | undefined)?.[c.frameIndex];
  return v ?? null;
}

export interface LegendItem {
  color: string;
  label: string;
}
export interface LayerDef {
  id: string;
  module: "M1" | "M2" | "M3" | "M4";
  label: string;
  blurb: string;
  legend: LegendItem[];
  legendNote: string;
  color: (c: ColorCtx) => string;
}

export const M1_LAYERS: LayerDef[] = [
  {
    id: "condition",
    module: "M1",
    label: "Condition index (relative)",
    blurb: "Greenness and moisture compared with unburned forest in the area (0-100). Not a damage warning.",
    legend: Object.entries(BAND_COLORS).map(([label, color]) => ({ label, color })),
    legendNote: "Summer frames share one fixed scale. Autumn, winter and spring frames are relative to the same season.",
    color: (c) => BAND_COLORS[String(valueAt(c, "health_band") ?? "Not scored")] ?? GREY,
  },
  {
    id: "mortality",
    module: "M1",
    label: "Mortality likelihood (model)",
    blurb: "Relative likelihood that USFS aerial surveys would map tree mortality here. Summer frames only.",
    legend: [
      ...RAMP.map((color, i) => ({
        color,
        label: ["Lowest fifth", "Second fifth", "Middle fifth", "Fourth fifth", "Highest fifth"][i],
      })),
      { color: GREY, label: "Burned or not scored" },
    ],
    legendNote: "Colour is the rank within Shaver Lake, not absolute risk. The darkest fifth is still below the Sierra-wide Elevated cutoff.",
    color: (c) => rampColor(valueAt(c, "mortality_percentile") as number | null),
  },
  {
    id: "trend",
    module: "M1",
    label: "5-summer trend",
    blurb: "Greenness trend 2022-2026 relative to similar patches. Context only.",
    legend: Object.entries(TREND_COLORS).map(([label, color]) => ({ label, color })),
    legendNote: "Not a damage warning. Refreshed once a year.",
    color: (c) => TREND_COLORS[String(c.series?.trend_label ?? c.staticProps?.trend_label ?? "Not enough data")] ?? GREY,
  },
];

export const PLACEHOLDERS = [
  { module: "M2", label: "Vegetation and observed damage" },
  { module: "M3", label: "Ignition risk and weather" },
  { module: "M4", label: "Active fire and perimeters" },
];