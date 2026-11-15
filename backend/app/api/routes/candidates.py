"""
Candidate screening and aperture quality evaluation routes.
"""
from typing import List, Optional
from fastapi import APIRouter, Query
from app.schemas.observation import ObservationSchema
from app.schemas.candidate import QualityEvaluationRequest, QualityEvaluationResponse
from app.services.storage.repository import repository
from app.services.astronomy.quality import evaluate_quality, decode_flags, SPHEREX_FLAGS

router = APIRouter(prefix="/candidates", tags=["Candidates"])

@router.get("/screening-results", response_model=List[ObservationSchema])
def get_screening_results(
    status: Optional[str] = Query(None),
    target: Optional[str] = Query(None),
):
    return repository.get_all(target=target, status=status)

@router.get("/flags")
def get_flags():
    return [{"bit": b, **info} for b, info in sorted(SPHEREX_FLAGS.items())]

@router.post("/evaluate", response_model=QualityEvaluationResponse)
def evaluate_candidate(req: QualityEvaluationRequest):
    res = evaluate_quality(
        center_finite=req.center_finite,
        center_flags_raw=req.center_flags_raw,
        aperture_fatal_count=req.aperture_fatal_count,
        aperture_total_pixels=req.aperture_total_pixels,
        bg_usable_pixels=req.bg_usable_pixels,
        variance_available=req.variance_available,
        target_inside=req.target_inside,
    )
    if req.aperture_fatal_tolerance is not None and req.aperture_fatal_count > req.aperture_fatal_tolerance:
        res = {"status": "REJECTED_SIMULATED_TOLERANCE",
               "reason": f"{req.aperture_fatal_count} flagged aperture pixels exceed the selected tolerance of {req.aperture_fatal_tolerance}.",
               "usable": False}
    res["decoded_flags"] = decode_flags(req.center_flags_raw)
    return QualityEvaluationResponse(**res)
