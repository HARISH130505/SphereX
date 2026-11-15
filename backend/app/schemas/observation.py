"""
Schemas for SPHEREx astronomical observations and targets.
"""
from typing import List, Optional
from pydantic import BaseModel, computed_field
from app.services.product_identity import product_id, archive_product_id

class TargetSchema(BaseModel):
    id: str
    name: str
    ra: float
    dec: float
    description: str
    category: str
    saturation_risk: str
    recommended_band: Optional[str] = None
    observation_count: int = 0
    clean_count: int = 0
    exploration_status: str = 'LIMITED SCIENTIFIC USABILITY'

class ObservationSchema(BaseModel):
    collection: Optional[str] = None
    access_url: Optional[str] = None
    archive_obs_id: Optional[str] = None
    footprint: Optional[str] = None
    obs_publisher_did: Optional[str] = None

    @computed_field
    @property
    def product_id(self) -> str:
        return product_id(self.obs_id, self.band)

    @computed_field
    @property
    def archive_product_id(self) -> Optional[str]:
        return archive_product_id(self.cutout_url, self.obs_publisher_did)

    obs_id: str
    target: str
    band: str
    obs_time_mjd: float
    obs_time_iso: Optional[str] = None
    ra: float
    dec: float
    cutout_url: str
    download_status: str
    fits_valid: bool
    extensions_found: str
    image_shape: str
    target_x: Optional[float] = None
    target_y: Optional[float] = None
    target_inside_cutout: bool
    center_pixel_finite: bool
    center_image_val: Optional[float] = None
    center_var_val: Optional[float] = None
    center_flags_raw: Optional[float] = None
    center_flags_decoded: Optional[str] = None
    aperture_total_pixels: int = 29
    aperture_finite_pixels: int = 0
    aperture_overflow_count: int = 0
    aperture_sur_error_count: int = 0
    aperture_bloom_count: int = 0
    aperture_source_count: int = 0
    aperture_fatal_count: int = 0
    bg_usable_pixels: int = 0
    bg_median_mjy_sr: Optional[float] = None
    zodi_median_mjy_sr: Optional[float] = None
    variance_available: bool = True
    screening_status: str
    rejection_reason: str

class TimelineItemSchema(BaseModel):
    product_id: str
    archive_product_id: Optional[str] = None
    obs_id: str
    band: str
    obs_time_mjd: float
    obs_time_iso: Optional[str] = None
    product_identifier: str
    image_shape: str
    screening_status: str
    rejection_reason: str
    data_quality: str
    provenance: str
    comparison_eligible: bool
    eligibility_reason: str

class TargetTimelineResponse(BaseModel):
    target: str
    category: str
    ra: float
    dec: float
    coverage_status: str
    observation_count: int
    eligible_count: int
    timeline: List[TimelineItemSchema]

