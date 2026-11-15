"""
Candidate Investigator API endpoints: Screening results, detector flag bitmask
diagnostics, and aperture quality threshold simulator.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, HTTPException, Body
from pydantic import BaseModel

from app.models import ObservationRecord
from app.services.data_service import data_service
from app.services.screening_service import (
    get_flag_dictionary,
    evaluate_aperture_quality,
    decode_spherex_flags,
)

router = APIRouter(prefix="/candidates", tags=["Candidate Investigator"])

class ThresholdEvaluationRequest(BaseModel):
    center_finite: bool = True
    center_flags_raw: Optional[int] = 2097152
    aperture_finite_pixels: int = 29
    aperture_fatal_count: int = 0
    aperture_total_pixels: int = 29
    bg_usable_pixels: int = 128
    variance_available: bool = True
    target_inside: bool = True

@router.get("/screening-results", response_model=List[ObservationRecord])
def get_screening_results(
    status: Optional[str] = Query(None, description="Filter: PASSED_CLEAN, FEASIBLE_WITH_CAVEATS, REJECTED_SATURATED, FAILED_DOWNLOAD"),
    target: Optional[str] = Query(None, description="Filter by target name"),
):
    """Retrieve full screening pipeline records across all vetted targets."""
    return data_service.get_observations(target=target, status=status)

@router.get("/flags")
def get_flags():
    """Retrieve complete SPHEREx detector flag bitmask specification."""
    return get_flag_dictionary()

@router.post("/evaluate")
def evaluate_custom_thresholds(req: ThresholdEvaluationRequest):
    """Interactive re-screening tool testing custom criteria against candidate apertures."""
    res = evaluate_aperture_quality(
        center_finite=req.center_finite,
        center_flags_raw=req.center_flags_raw,
        aperture_finite_pixels=req.aperture_finite_pixels,
        aperture_fatal_count=req.aperture_fatal_count,
        aperture_total_pixels=req.aperture_total_pixels,
        bg_usable_pixels=req.bg_usable_pixels,
        variance_available=req.variance_available,
        target_inside=req.target_inside,
    )
    flags = decode_spherex_flags(req.center_flags_raw)
    res["decoded_flags"] = flags
    return res
