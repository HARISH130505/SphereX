"""
Schemas for epoch comparisons, difference imaging, and transient metrics.
Includes astronomical registration diagnostics and candidate vetting metrics.
"""
from typing import Dict, Optional, List, Any
from pydantic import BaseModel, Field, AliasChoices, model_validator
from app.schemas.observation import ObservationSchema

class EpochComparisonRequest(BaseModel):
    epoch_1_product_id: str = Field(min_length=1, validation_alias=AliasChoices("epoch_1_product_id", "epoch_1_obs_id"))
    epoch_2_product_id: str = Field(min_length=1, validation_alias=AliasChoices("epoch_2_product_id", "epoch_2_obs_id"))

    @model_validator(mode="before")
    @classmethod
    def reject_conflicting_identifiers(cls, values):
        if isinstance(values, dict):
            for epoch in (1, 2):
                new, old = f"epoch_{epoch}_product_id", f"epoch_{epoch}_obs_id"
                if new in values and old in values and values[new] != values[old]:
                    raise ValueError(f"Conflicting {new} and {old}")
        return values

    stretch: str = "asinh"
    colormap: str = "coolwarm"

class ComparisonFailure(BaseModel):
    code: str
    message: str

class ComparisonValidity(BaseModel):
    status: str
    scientific_analysis_allowed: bool
    failure_reasons: List[ComparisonFailure]
    min_overlap_fraction: float
    overlap_fraction: Optional[float] = None
    overlap_definition: str

class EpochComparisonResponse(BaseModel):
    comparison_validity: ComparisonValidity
    data_quality: Dict[str, Any] = Field(default_factory=dict)
    epoch_1_meta: ObservationSchema
    epoch_2_meta: ObservationSchema
    time_delta_days: float
    epoch_1_image_base64: str
    epoch_2_image_base64: str
    difference_image_base64: Optional[str] = None
    significance_image_base64: Optional[str] = None
    flux_ratio: Optional[float] = None
    transient_score: Optional[float] = None
    motion_detected: bool
    motion_vector_arcsec: Optional[Dict[str, float]] = None
    scientific_summary: str
    registration_diagnostics: Optional[Dict[str, Any]] = None
    difference_statistics: Optional[Dict[str, Any]] = None
    candidate_assessment: Optional[Dict[str, Any]] = None
    motion_analysis: Optional[Dict[str, Any]] = None
    epoch_1_original_image_base64: Optional[str] = None
    epoch_2_original_image_base64: Optional[str] = None
    overlap_mask_image_base64: Optional[str] = None
    detected_sources: List[Dict[str, Any]] = []
    evidence_dossier: Optional[Dict[str, Any]] = None
    evidence_report_markdown: Optional[str] = None
