"""
Schemas for FITS image tiles, cutouts, and contrast parameters.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class CutoutRenderRequest(BaseModel):
    obs_id: str
    stretch: str = "asinh"
    colormap: str = "plasma"
    overlays: bool = True

class CutoutRenderResponse(BaseModel):
    product_id: str
    archive_product_id: Optional[str] = None
    obs_id: str
    target: str
    band: str
    screening_status: str
    image_shape: List[int]
    target_xy: List[float]
    png_base64: str
    center_val: Optional[float] = None
    bg_median: Optional[float] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    median_val: Optional[float] = None
    nan_count: Optional[int] = None
    valid_pct: Optional[float] = None
    wcs_info: Optional[Dict[str, Any]] = None
    source_file: Optional[str] = None
    quality_summary: Optional[Dict[str, Any]] = None
    variance_summary: Optional[Dict[str, Any]] = None
    science_valid_pixel_count: Optional[int] = None
    observation_quality: Optional[Dict[str, Any]] = None
    fits_valid: bool = True
