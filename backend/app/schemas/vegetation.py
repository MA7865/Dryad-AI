
"""
Pydantic response schemas for the M2 vegetation API.

Models the actual fields produced by
scripts/m2_build_vegetation_layer.py.

Null means unavailable or not evaluated.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class VegetationProperties(BaseModel):
    """Properties of a vegetation grid patch."""

    # Shared grid identifiers
    patch_id: str
    feature_id: str

    # LANDFIRE vegetation reference
    vegetation_class: str | None
    vegetation_code: int | None
    class_shares: dict[str, Any]
    coverage_fraction: float
    valid_pixel_count: int

    # M2 Sentinel-2 measurements
    NDVI: float
    NDMI: float
    obs_count: float
    window_start: str
    window_end: str
    year: int

    # Historical vegetation-index anomalies
    ndvi_anomaly: float | None
    ndmi_anomaly: float | None
    anomaly_status: str
    anomaly_eligible: bool

    # Burn and forest context
    burn_frac: float
    forest_frac: float
    burned_flag: bool
    burn_status: str

    # Statistical detection results
    ndvi_flag: bool | None
    ndmi_flag: bool | None
    ndvi_threshold: float | None
    ndmi_threshold: float | None
    anomaly_detected: bool | None
    detection_status: Literal[
        "negative_change_flagged",
        "not_flagged",
        "not_evaluated",
    ]
    anomaly_method: str

    # Separate source-specific quality
    vegetation_data_quality: str
    satellite_data_quality: str
    anomaly_data_quality: str

    # Backward-compatible combined quality
    data_quality: str

    # Provenance
    vegetation_source: str
    satellite_source: str
    anomaly_source: str
    source: str
    generated_at: str
    layer_type: str
    processing_version: str
    prediction_kind: str

    # No damage-prediction model exists yet
    damage_class: str | None
    model_version: str | None


class VegetationGeometry(BaseModel):
    """GeoJSON Polygon geometry in WGS84."""

    type: Literal["Polygon"]
    coordinates: list[list[list[float]]]


class VegetationFeature(BaseModel):
    """One vegetation GeoJSON feature."""

    type: Literal["Feature"]
    geometry: VegetationGeometry
    properties: VegetationProperties


class VegetationFeatureCollection(BaseModel):
    """The complete vegetation GeoJSON response."""

    type: Literal["FeatureCollection"]
    features: list[VegetationFeature] = Field(
        default_factory=list
    )
