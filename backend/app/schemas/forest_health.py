from pydantic import BaseModel


class HistoryPoint(BaseModel):
    year: int
    health_index: int | None
    health_band: str
    ndvi: float | None
    ndmi: float | None

class LiveObservation(BaseModel):
    window_start: str
    window_end: str
    observed_at: str
    health_index: int | None
    health_band: str
    ndvi: float | None
    ndmi: float | None
    obs_count: float | None
    data_quality: str
    note: str
    mortality_likelihood: float | None = None
    mortality_band: str | None = None
    model_status: str | None = None
    mortality_model_version: str | None = None
    mortality_model_window: str | None = None
    model_note: str | None = None
    mortality_climate_year: int | None = None
    
class ForestHealthPatch(BaseModel):
    patch_id: str
    year: int
    period: str
    health_index: int | None
    health_band: str
    ndvi: float | None
    ndmi: float | None
    trend_label: str
    trend_slope: float | None
    burn_status: str
    data_quality: str
    explanation: str
    model_version: str
    source: str
    data_kind: str
    history: list[HistoryPoint]
    live: LiveObservation | None = None