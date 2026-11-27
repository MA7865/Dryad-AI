export interface Frame {
  id: string;
  season: string;
  year: number;
  label: string;
  window: [string, string];
}

export interface PatchSeries {
  health_index: (number | null)[];
  health_band: (string | null)[];
  ndvi: (number | null)[];
  ndmi: (number | null)[];
  data_quality: (string | null)[];
  mortality_likelihood: (number | null)[];
  mortality_percentile: (number | null)[];
  burn_status?: string | null;
  trend_label?: string | null;
}

export interface Timeline {
  frames: Frame[];
  patches: Record<string, PatchSeries>;
  notes: string[];
}

export interface LayerProps {
  patch_id: string;
  health_index: number | null;
  health_band: string | null;
  ndvi: number | null;
  ndmi: number | null;
  trend_label?: string | null;
  trend_slope?: number | null;
  burn_status?: string | null;
  data_quality?: string | null;
  mortality_likelihood?: number | null;
  mortality_percentile?: number | null;
  mortality_band?: string | null;
  model_status?: string | null;
  window_start?: string;
  window_end?: string;
  observed_at?: string;
  mortality_climate_year?: number | null;
}

export interface PatchFeature {
  type: "Feature";
  geometry: any;
  properties: LayerProps;
}
export interface PatchCollection {
  type: "FeatureCollection";
  features: PatchFeature[];
}

export interface HistoryPoint {
  year: number;
  health_index: number | null;
  health_band: string;
  ndvi: number | null;
  ndmi: number | null;
}

export interface LiveBlock {
  window_start: string;
  window_end: string;
  observed_at: string;
  health_index: number | null;
  health_band: string;
  ndvi: number | null;
  ndmi: number | null;
  obs_count: number | null;
  data_quality: string;
  note: string;
  mortality_likelihood?: number | null;
  mortality_percentile?: number | null;
  mortality_band?: string | null;
  model_status?: string | null;
  mortality_model_version?: string | null;
  mortality_model_window?: string | null;
  mortality_climate_year?: number | null;
  model_note?: string | null;
}

export interface PatchDetail {
  patch_id: string;
  year: number;
  period: string;
  health_index: number | null;
  health_band: string;
  ndvi: number | null;
  ndmi: number | null;
  trend_label: string;
  trend_slope: number | null;
  burn_status: string;
  data_quality: string;
  explanation: string;
  model_version: string;
  source: string;
  data_kind: string;
  history: HistoryPoint[];
  live: LiveBlock | null;
}

export interface StatusInfo {
  summer: { year: number; period: string; generated_at: string; model_version: string } | null;
  live: { newest_scene: string; window_start: string; window_end: string; generated_at: string } | null;
  live_status: { enabled: boolean; refreshing: boolean; error: string | null; age_minutes: number | null };
}

export type ModelCard = any;