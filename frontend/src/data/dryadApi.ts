import { useCallback, useEffect, useState } from "react";
import type { ModelCard, PatchCollection, PatchDetail, StatusInfo, Timeline } from "./types";

const BASE = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  endpoint: string;
  status: number;
  detail: string;
  constructor(endpoint: string, status: number, detail: string) {
    super(`${status} ${endpoint}: ${detail}`);
    this.endpoint = endpoint;
    this.status = status;
    this.detail = detail;
  }
}

async function getJson<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, { headers: { Accept: "application/json" } });
  } catch {
    throw new ApiError(path, 0, "Cannot reach the API. Is the backend running (uvicorn backend.app.main:app --reload)?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* keep the status text */
    }
    throw new ApiError(path, res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  layerSummer: () => getJson<PatchCollection>("/api/v1/layers/forest-health"),
  layerLive: () => getJson<PatchCollection>("/api/v1/layers/forest-health?period=live"),
  timeline: () => getJson<Timeline>("/api/v1/layers/forest-health/timeline"),
  status: () => getJson<StatusInfo>("/api/v1/layers/forest-health/status"),
  modelCard: () => getJson<ModelCard>("/api/v1/layers/forest-health/model-card"),
  patch: (id: string) => getJson<PatchDetail>(`/api/v1/patches/${encodeURIComponent(id)}/forest-health`),
};

export interface AsyncState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[], enabled = true): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    setError(null);
    fn()
      .then((d) => {
        if (alive) {
          setData(d);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (alive) {
          setError(e instanceof ApiError ? e : new ApiError("unknown", 0, String(e)));
          setLoading(false);
        }
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}