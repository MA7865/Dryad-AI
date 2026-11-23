from typing import Optional

from pydantic import BaseModel, Field


class FireSpreadRequest(BaseModel):
    """Input for POST /api/v1/simulations/fire-spread."""
    ignition_lon: float = Field(..., ge=-119.50, le=-119.25, description="Ignition longitude (inside the study area)")
    ignition_lat: float = Field(..., ge=37.00, le=37.20, description="Ignition latitude (inside the study area)")
    target_area_km2: float = Field(..., gt=0, le=50, description="Final burned area the simulated fire is grown to")
    wind_dir_deg: Optional[float] = Field(None, ge=0, le=360,
                                          description="Direction the wind blows FROM (0 = north, 90 = east). Omit for no wind.")
    wind_k: float = Field(0.0, ge=0, le=6, description="Wind strength (0 = none; 2 worked best on Goose)")
    seed: int = Field(0, description="Random seed; the same inputs and seed give the same fire")
