from typing import Literal

from pydantic import BaseModel, Field


class ScenarioInput(BaseModel):
    valid_at: str | None = None
    delta_temp_c: float = Field(
        ...,
        description="Temperature change in degrees Celsius; allowed range -10 to 10",
    )
    delta_wind_pct: float = Field(
        ...,
        description="Wind change in percent; allowed range -50 to 100",
    )
    delta_precip_pct: float = Field(
        ...,
        description="Precipitation change in percent; allowed range -100 to 100",
    )
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


class RiskScenario(BaseModel):
    delta_temp_c: float
    delta_wind_pct: float
    delta_precip_pct: float


class RiskFeatureProperties(RiskProperties):
    baseline_risk_score: float | None = None
    risk_change: float | None = None
    scenario: RiskScenario | None = None


class GeoJsonGeometry(BaseModel):
    type: Literal["Polygon"]
    coordinates: list


class RiskFeature(BaseModel):
    type: Literal["Feature"]
    geometry: GeoJsonGeometry
    properties: RiskFeatureProperties


class RiskFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"]
    features: list[RiskFeature]


class RiskStatus(BaseModel):
    valid_at: str
    weather_used_at: str | None
    generated_at: str
    model_version: str
    model_status: str
    error: str | None


class ScenarioEcho(BaseModel):
    delta_temp_c: float
    delta_wind_pct: float
    delta_precip_pct: float
