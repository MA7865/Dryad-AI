from pydantic import BaseModel, Field


class ScenarioInput(BaseModel):
    valid_at: str | None = None
    delta_temp_c: float = Field(...)
    delta_wind_pct: float = Field(...)
    delta_precip_pct: float = Field(...)
    patch_ids: list[str] | None = None


class RiskProperties(BaseModel):
    feature_id: str
    patch_id: str
    row: int
    col: int
    center_lon: float
    center_lat: float
    layer_type: str
    valid_at: str
    window_hours: int
    observed_at: str | None
    generated_at: str
    risk_score: float | None
    risk_percentile: float | None
    risk_band: str
    top_drivers: list[str] | None
    model_status: str
    model_note: str
    model_version: str
    source: str
    data_kind: str
    data_quality: str
