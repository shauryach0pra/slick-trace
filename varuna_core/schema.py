"""
Slick Trace / OilTrace — incident manifest schema.

This is the single "join contract" described in the masterplan (p.7): every
stage (detection, AIS/historical mapping, attribution, NLP, export) reads and
writes objects defined here. Real data sources (Zenodo Sentinel-1, DMA/NOAA
AIS, ERA5/Copernicus forcing) must be adapted INTO these shapes; nothing
downstream should need to know whether a field is real, modelled, or
synthetic — that's carried explicitly by `Provenance.status`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DataStatus(str, Enum):
    """Every layer must declare this. Never silently mix statuses."""

    OBSERVED = "observed"      # real sensor / real broadcast data
    MODELLED = "modelled"      # e.g. reanalysis wind/current fields
    SYNTHETIC = "synthetic"    # generated for dev/testing


class Provenance(BaseModel):
    status: DataStatus
    source: str  # e.g. "Zenodo Part I", "DMA historical AIS", "synth_generator v0.1"
    license: Optional[str] = None
    retrieved_at: Optional[datetime] = None


class BBox(BaseModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


class SceneObservation(BaseModel):
    """One SAR/optical acquisition. Detection stage fills `polygon_geojson`."""

    scene_id: str
    acquired_utc: datetime
    sensor: str  # e.g. "Sentinel-1 VV/VH"
    bbox: BBox
    pixel_spacing_m: float
    image_path: str
    mask_path: Optional[str] = None
    polygon_geojson: Optional[dict] = None
    quality_flags: list[str] = Field(default_factory=list)
    model_version: Optional[str] = None
    provenance: Provenance


class VesselFix(BaseModel):
    t_utc: datetime
    lon: float
    lat: float
    sog_knots: Optional[float] = None
    cog_deg: Optional[float] = None
    interpolated: bool = False


class VesselTrack(BaseModel):
    vessel_key: str          # stable internal key
    mmsi: Optional[str] = None
    imo: Optional[str] = None
    name: Optional[str] = None
    identity_valid_from: Optional[datetime] = None
    identity_valid_to: Optional[datetime] = None
    fixes: list[VesselFix] = Field(default_factory=list)
    missing_intervals: list[tuple[datetime, datetime]] = Field(default_factory=list)
    provenance: Provenance


class ForcingField(BaseModel):
    """Wind/current field reference for one simulation timestamp."""

    valid_time_utc: datetime
    kind: str  # "wind" | "current"
    path: str  # e.g. netcdf/zarr path
    provenance: Provenance


class ReleaseHypothesis(BaseModel):
    candidate_id: str
    vessel_key: str
    release_start_utc: datetime
    duration_hours: float
    is_continuous: bool  # pulse vs continuous moving discharge
    windage_pct: Optional[float] = None
    diffusivity_m2_s: Optional[float] = None


class FitResult(BaseModel):
    candidate_id: str
    iou: float
    boundary_distance_m: float
    relative_area_error: float
    complexity_penalty: float
    loss: float  # a(1-IoU) + b(boundary) + c(area) + d(complexity)
    ensemble_variant: str  # which wind/current/threshold variant this run used
    run_id: str
    provenance: Provenance


class CaseState(str, Enum):
    NO_SLICK = "no_slick"
    POTENTIAL_SLICK = "potential_slick"
    NEEDS_REVIEW = "needs_review"


class Incident(BaseModel):
    incident_id: str
    case_state: CaseState
    scene: SceneObservation
    candidate_tracks: list[VesselTrack] = Field(default_factory=list)
    release_hypotheses: list[ReleaseHypothesis] = Field(default_factory=list)
    fit_results: list[FitResult] = Field(default_factory=list)
    unmatched_contacts: list[dict] = Field(default_factory=list)  # SAR contacts w/o AIS match
    top_candidate_id: Optional[str] = None
    unknown_source: bool = False  # explicit abstention state
    created_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: list[str] = Field(default_factory=list)

    def as_manifest_dict(self) -> dict:
        return self.model_dump(mode="json")
