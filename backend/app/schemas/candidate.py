"""
Schemas for transient candidates, quality vetting, and screening simulation.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class QualityEvaluationRequest(BaseModel):
    center_finite: bool = True
    center_flags_raw: Optional[int] = 2097152
    aperture_finite_pixels: int = 29
    aperture_fatal_count: int = 0
    aperture_total_pixels: int = 29
    bg_usable_pixels: int = 128
    variance_available: bool = True
    target_inside: bool = True
    aperture_fatal_tolerance: Optional[int] = None

class QualityEvaluationResponse(BaseModel):
    status: str
    reason: str
    usable: bool
    decoded_flags: List[str] = []
