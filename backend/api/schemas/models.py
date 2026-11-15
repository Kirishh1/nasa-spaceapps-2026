from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AnalysisConfig(BaseModel):
    frequency: Literal["A", "B"] = "A"
    polarization: Literal["HH", "HV", "VV", "VH"] = "HH"
    threshold_db: float = Field(3.0, gt=0, le=20, description="|ΔB| threshold for significant change (dB)")
    speckle_filter: Literal["lee", "boxcar", "none"] = "lee"
    filter_size: int = Field(5, ge=1, le=15)
    water_threshold_db: float = Field(-18.0, ge=-40, le=0, description="Later-date backscatter below which a decrease is water-like (dB)")
    min_region_m2: float = Field(20000.0, ge=0)
    min_valid_fraction: float = Field(0.2, ge=0, le=1)
    allow_cross_geometry: bool = False
    include_precipitation: bool = True
    include_reference: bool = True


class AnalysisRequest(BaseModel):
    study_area_id: str
    earlier_id: str
    later_id: str
    sensor: Literal["NISAR", "RCM", "COMPARE"] = "NISAR"
    config: AnalysisConfig = AnalysisConfig()
    geometry: dict | None = Field(None, description="Optional GeoJSON Polygon (lon/lat) drawn by the user; intersected with the study area")
