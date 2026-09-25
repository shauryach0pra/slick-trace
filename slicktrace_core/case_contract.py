"""
Canonical Case contract: one object per incident, assembled from the artifacts
the pipeline already wrote.

Rules this module keeps
  * Field names are the artifact keys, verbatim. Nothing is renamed, so a
    reader can trace every field to the file and key it came from.
  * Assembled, never computed. Every value is copied from an artifact; the only
    logic here is joining the manifest's tracks to the historical mapping's
    assessments on vessel_key, and checking that the pieces agree.
  * The truth sidecar is never opened. The contract cannot carry the answer.
  * Unknown fields are rejected (extra="forbid"), so an artifact that grows or
    renames a key fails validation instead of drifting past the interface.
    The one exception is `slick`, a deliberate projection of the detection
    result.

What is deliberately absent
  * No forecast envelope polygon: forecast_result.json stores horizon areas
    and centroids only. Persisting contours is separate work.
  * No vessel type: no source or generated track carries one.
  * No not-testable fragility or not-applicable next-observation variant: both
    branches return without writing a file, so no artifact ever has that shape.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

SCHEMA_VERSION = "1"

# Must equal the families in synth_generator.CASE_PLAN; a test holds them together.
Family = Literal["decoy", "moving_discharge", "absent_source", "crowded", "along_track_ribbon"]
VesselStatus = Literal["candidate", "excluded", "unassessed"]
HourState = Literal["inside", "outside", "no_data"]
CaseState = Literal["no_slick", "potential_slick", "needs_review"]


def _iso_with_offset(s: str) -> str:
    """Timestamps stay as the artifact wrote them, but must parse and carry an
    explicit UTC offset. Re-serialising through datetime would change the text."""
    if datetime.fromisoformat(s).tzinfo is None:
        raise ValueError(f"timestamp without a UTC offset: {s!r}")
    return s


IsoUtc = Annotated[str, AfterValidator(_iso_with_offset)]
LonLat = tuple[float, float]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------- meta --

class BBox(_Strict):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


class Provenance(_Strict):
    status: Literal["observed", "modelled", "synthetic"]
    source: str
    license: Optional[str] = None


class Generator(_Strict):
    family: Family
    seed: int
    version: str


class Meta(_Strict):
    incident_id: str
    scene_id: str
    acquired_utc: IsoUtc
    case_state: CaseState
    sensor: str
    crs: str
    metric_crs: str
    bbox: BBox
    img_size_px: int
    pixel_spacing_m: float
    label_source: str
    data_licence: str
    ais_source: str
    ais_window_start_utc: IsoUtc
    ais_window_end_utc: IsoUtc
    forcing_product: str
    forcing_valid_from_utc: IsoUtc
    forcing_valid_to_utc: IsoUtc
    provenance: Provenance
    generator: Generator


META_FIELDS = tuple(Meta.model_fields)


class SensitiveArea(_Strict):
    name: str
    kind: str
    polygon: list[LonLat]


class Geography(_Strict):
    coastline: list[LonLat]
    sensitive_areas: list[SensitiveArea]


# ------------------------------------------------------------------ slick --

class SlickGeometry(_Strict):
    area_km2: float
    perimeter_km: float
    interior_holes_filled_px: int
    major_axis_km: float
    minor_axis_km: float
    elongation: float
    orientation_deg_from_north: float
    centroid: LonLat


DOWNSTREAM_NOTE = ("Detector output, shown as the observed slick. The hindcast, forward "
                   "replay, fragility sweep and forecast are seeded from the generator's "
                   "mask, not from this polygon.")


class Slick(_Strict):
    detector: str
    detected: bool
    polygon: list[LonLat]
    geometry: SlickGeometry
    n_regions: int
    total_area_km2: float
    measurement_note: str
    truth_agreement_iou: Optional[float] = None   # synthetic cases only
    downstream_note: str = DOWNSTREAM_NOTE


# ---------------------------------------------------------------- vessels --

class Fix(_Strict):
    t_utc: IsoUtc
    lon: float
    lat: float
    sog_knots: Optional[float] = None
    cog_deg: Optional[float] = None
    interpolated: bool


class TrackProvenance(_Strict):
    status: Literal["observed", "modelled", "synthetic"]
    source: str


class Vessel(_Strict):
    # from manifest.tracks[]
    vessel_key: str
    mmsi: Optional[str] = None
    imo: Optional[str] = None
    name: Optional[str] = None
    identity_valid_from: Optional[IsoUtc] = None
    identity_valid_to: Optional[IsoUtc] = None
    fixes: list[Fix]
    missing_intervals: list[tuple[IsoUtc, IsoUtc]]
    provenance: TrackProvenance
    # from historical_mapping.assessments[]
    status: VesselStatus
    reason: str
    first_entry_hours_before: Optional[float] = None
    inside_at: list[float]
    hourly_state: list[HourState]
    hours_with_data: int
    data_intervals_hours_before: list[tuple[float, float]]


class Historical(_Strict):
    hours_back: int
    hours_queried: list[float]
    inclusion_radius_deg: float
    state_rule: str


# --------------------------------------------------------------- baseline --

class ProximityRow(_Strict):
    vessel_key: str
    distance_deg: float


class Baseline(_Strict):
    incident_id: str
    method: str
    ranking: list[ProximityRow]
    top_candidate_id: Optional[str] = None


# ------------------------------------------------------------ attribution --

class RankedCandidate(_Strict):
    candidate_id: str
    vessel_key: str
    release_start: IsoUtc
    duration_hours: float
    is_continuous: bool
    mean_iou: float
    mean_loss: float
    ensemble_win_count: int
    n_ensemble: int


class Discrimination(_Strict):
    discriminated: Optional[bool] = None
    loss_gap: Optional[float] = None
    iou_gap: Optional[float] = None
    tolerance: float
    note: str


class NamedFactor(_Strict):
    vessel_key: str
    proximity_deg_at_acquisition: Optional[float] = None
    trajectory_envelope_dwell: Optional[int] = None
    physical_fit_mean_iou: float
    physical_fit_mean_loss: float


class NamedFactors(_Strict):
    factors: list[NamedFactor]
    ranked_on: str
    note: str
    behavioural_anomalies: str


class ReleaseAge(_Strict):
    estimable: bool
    hours: Optional[float] = None
    hours_low: Optional[float] = None
    hours_high: Optional[float] = None
    confidence: str
    method: Optional[str] = None
    caveat: Optional[str] = None


class LossWeights(_Strict):
    a_iou: float
    b_boundary: float
    c_area: float
    d_complexity: float


class Attribution(_Strict):
    incident_id: str
    candidates_considered: list[str]
    ranking: list[RankedCandidate]
    top_candidate_id: Optional[str] = None
    unknown_source: bool
    abstention_iou_gate: float
    discrimination: Discrimination
    named_factors: NamedFactors
    release_age: ReleaseAge
    loss_weights: LossWeights
    n_ensemble_variants: int


# -------------------------------------------------------------- fragility --

class FragilityParams(_Strict):
    current_u_bias: float
    current_v_bias: float
    diffusivity_scale: float
    mask_threshold: float
    duration_shift_h: float


class GridPoint(_Strict):
    point_id: str
    params: FragilityParams
    changed_axes: dict[str, float]
    magnitude: float
    top_candidate: str
    top_iou: float
    baseline_candidate_iou: float
    loss_margin: Optional[float] = None
    flipped: bool
    source: Literal["computed"]


class FragilityAxis(_Strict):
    tested_values: list[float]
    normalising_scale: float
    label: str


class Fragility(_Strict):
    incident_id: str
    testable: Literal[True]
    baseline_top: str
    baseline_unknown_source: bool
    n_points_tested: int
    n_points_flipped: int
    flip_found: bool
    smallest_flip: Optional[GridPoint] = None
    lead_retained_fraction: Optional[float] = None
    grid: list[GridPoint]
    axes: dict[str, FragilityAxis]
    coverage_note: str
    interpretation_note: str
    loss_weights: LossWeights
    nominal_mean_losses: dict[str, float]


# --------------------------------------------------------------- coverage --

class OperatingPoint(_Strict):
    gate_radius_deg: float
    contact_position_noise_deg: float
    detector_miss_rate: float
    false_detection_rate: float
    hide_fraction_selective: float
    coverage_failure_radius_deg: float


class CoverageCondition(_Strict):
    n_runs: int
    # null means the denominator was zero: no rate was measured, not a rate of 0
    hidden_ais_recovery_rate: Optional[float] = None
    hidden_ais_recovery_n: str
    false_unmatched_alert_rate: Optional[float] = None
    false_unmatched_alert_n: str
    mistaken_promotion_rate: Optional[float] = None
    mistaken_promotion_n: str


class CoverageConditions(_Strict):
    selective: CoverageCondition
    coverage_failure: CoverageCondition


class Coverage(_Strict):
    incident_id: str
    operating_point: OperatingPoint
    conditions: CoverageConditions
    limits: list[str]


# --------------------------------------------------------------- forecast --

class Exposure(_Strict):
    name: str
    kind: str
    modelled_particle_fraction: float
    any_contact: bool


class ForecastHorizon(_Strict):
    horizon_hours: int
    valid_utc: IsoUtc
    envelope_area_km2: float
    centroid: LonLat
    modelled_shoreline_fraction: Optional[float] = None
    sensitive_area_exposure: list[Exposure]
    particles: int


class Forecast(_Strict):
    incident_id: str
    issued_from_utc: IsoUtc
    forcing_mode: str
    n_ensemble_variants: int
    horizons: list[ForecastHorizon]
    first_modelled_shoreline_contact_h: Optional[int] = None
    first_modelled_sensitive_contact_h: dict[str, Optional[int]]
    interpretation_note: str


# ------------------------------------------------------- next observation --

class Hypothesis(_Strict):
    vessel_key: str
    candidate_id: str


class Ambiguity(_Strict):
    mean_iou_gap: float
    mean_loss_gap: float


class ObservationWindow(_Strict):
    horizon_hours: int
    valid_utc: IsoUtc
    disagreement_score: float
    predicted_overlap_iou: float
    disagreement_bbox: Optional[BBox] = None
    schedule_status: str


class NextObservation(_Strict):
    incident_id: str
    applicable: Literal[True]
    hypothesis_a: Hypothesis
    hypothesis_b: Hypothesis
    current_ambiguity: Ambiguity
    windows: list[ObservationWindow]
    recommended_window: ObservationWindow
    method_note: str
    scope_note: str


# ------------------------------------------------------------------- case --

class Case(_Strict):
    schema_version: Literal["1"] = SCHEMA_VERSION
    meta: Meta
    geography: Geography
    slick: Optional[Slick] = None
    historical: Historical
    vessels: list[Vessel]
    baseline: Optional[Baseline] = None
    attribution: Optional[Attribution] = None
    fragility: Optional[Fragility] = None
    coverage: Optional[Coverage] = None
    forecast: Optional[Forecast] = None
    next_observation: Optional[NextObservation] = None

    @model_validator(mode="after")
    def _pieces_agree(self) -> "Case":
        iid = self.meta.incident_id
        for name in ("baseline", "attribution", "fragility", "coverage", "forecast",
                     "next_observation"):
            section = getattr(self, name)
            if section is not None and section.incident_id != iid:
                raise ValueError(f"{name} belongs to {section.incident_id}, not {iid}")

        keys = [v.vessel_key for v in self.vessels]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate vessel_key")
        n_hours = len(self.historical.hours_queried)
        for v in self.vessels:
            if len(v.hourly_state) != n_hours:
                raise ValueError(f"{v.vessel_key}: {len(v.hourly_state)} hourly states "
                                 f"for {n_hours} queried times")

        if self.baseline is not None:
            if {r.vessel_key for r in self.baseline.ranking} != set(keys):
                raise ValueError("proximity baseline does not rank exactly the case's vessels")

        if self.attribution is not None:
            candidates = [v.vessel_key for v in self.vessels if v.status == "candidate"]
            if self.attribution.candidates_considered != candidates:
                raise ValueError("forward replay considered vessels other than the "
                                 "historical-mapping candidates")
            if not {r.vessel_key for r in self.attribution.ranking} <= set(candidates):
                raise ValueError("ranking contains a vessel that is not a candidate")
        return self


# ---------------------------------------------------------------- builder --

def _load(case_dir: str, name: str, required: bool = False) -> Optional[dict]:
    path = os.path.join(case_dir, name)
    if not os.path.exists(path):
        if required:
            raise FileNotFoundError(f"{path} has not been computed")
        return None
    with open(path) as f:
        return json.load(f)


def build_case(case_dir: str) -> Case:
    """Assemble and validate one incident. Missing optional artifacts become
    None, so a caller can show "not computed" rather than a guess."""
    manifest = _load(case_dir, "manifest.json", required=True)
    hm = _load(case_dir, "historical_mapping.json", required=True)
    detection = _load(case_dir, "detection_result.json")

    by_key = {a["vessel_key"]: a for a in hm["assessments"]}
    track_keys = [t["vessel_key"] for t in manifest["tracks"]]
    if set(by_key) != set(track_keys):
        raise ValueError("historical mapping and manifest disagree on the vessel list")

    vessels = []
    for track in manifest["tracks"]:
        assessment = {k: v for k, v in by_key[track["vessel_key"]].items() if k != "vessel_key"}
        clash = set(track) & set(assessment)
        if clash:
            raise ValueError(f"track and assessment both define {sorted(clash)}")
        vessels.append({**track, **assessment})

    slick = None
    if detection is not None:
        slick = {k: detection[k] for k in ("detector", "detected", "polygon", "geometry",
                                            "n_regions", "total_area_km2", "measurement_note")}
        agreement = detection.get("agreement_with_truth_mask")
        slick["truth_agreement_iou"] = agreement.get("iou") if agreement else None

    return Case.model_validate({
        "meta": {k: manifest[k] for k in META_FIELDS},
        "geography": {"coastline": manifest["coastline"],
                      "sensitive_areas": manifest["sensitive_areas"]},
        "slick": slick,
        "historical": {k: hm[k] for k in ("hours_back", "hours_queried",
                                          "inclusion_radius_deg", "state_rule")},
        "vessels": vessels,
        "baseline": _load(case_dir, "naive_baseline_result.json"),
        "attribution": _load(case_dir, "attribution_result.json"),
        "fragility": _load(case_dir, "fragility_result.json"),
        "coverage": _load(case_dir, "coverage_result.json"),
        "forecast": _load(case_dir, "forecast_result.json"),
        "next_observation": _load(case_dir, "next_observation_result.json"),
    })
