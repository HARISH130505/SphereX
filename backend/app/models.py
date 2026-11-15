"""
Pydantic data models for SPHEREx Explorer API.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TargetInfo(BaseModel):
    id: str
    name: str
    ra: float
    dec: float
    description: str
    category: str  # galaxy, variable_star, asteroid, planet_x_candidate
    saturation_risk: str  # NONE, LOW, MEDIUM, CRITICAL_SATURATED
    recommended_band: Optional[str] = None
    observation_count: int = 0
    clean_count: int = 0

class ObservationRecord(BaseModel):
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
    aperture_total_pixels: int = 0
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

class EpochGroup(BaseModel):
    epoch_id: int
    name: str
    mjd_min: float
    mjd_max: float
    date_label: str
    observation_count: int
    bands: List[str]
    observations: List[ObservationRecord]

class SpectrumDataPoint(BaseModel):
    mjd: float
    det_id: int
    band_name: str
    wavelength_um: float
    wavelength_width_um: float
    flux_ujy: float
    flux_err_ujy: float
    flux_err_tractor_ujy: Optional[float] = None
    flux_bkg_mjy_sr: Optional[float] = None
    snr: float
    flags_raw: int
    flags_decoded: List[str]
    fit_ql: float
    ra: float
    dec: float
    obs_publisher_did: str

class SpectralSummary(BaseModel):
    target: str
    ra: float
    dec: float
    total_points: int
    wavelength_range_um: List[float]
    bands: List[str]
    points: List[SpectrumDataPoint]
    median_snr: float
    highest_flux_point: Optional[SpectrumDataPoint] = None

class EpochComparisonRequest(BaseModel):
    epoch_1_obs_id: str
    epoch_2_obs_id: str
    stretch: str = "asinh"  # asinh, linear, log, sqrt
    colormap: str = "plasma"  # plasma, viridis, inferno, coolwarm, bone
    subtraction_method: str = "direct"  # direct, normalized, significance

class EpochComparisonResponse(BaseModel):
    epoch_1_meta: ObservationRecord
    epoch_2_meta: ObservationRecord
    time_delta_days: float
    epoch_1_image_base64: str
    epoch_2_image_base64: str
    difference_image_base64: str
    significance_image_base64: str
    flux_ratio: float
    transient_score: float  # 0 to 1
    motion_detected: bool
    motion_vector_arcsec: Optional[Dict[str, float]] = None
    scientific_summary: str

class ResearchQuestionRequest(BaseModel):
    question: str
    context_target: Optional[str] = "M101"
