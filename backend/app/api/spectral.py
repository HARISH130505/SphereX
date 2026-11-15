"""
Spectral Explorer API endpoints: Full Spectral Energy Distribution (SED)
across all 6 SPHEREx detector channels (0.74 - 5.0 μm) from table_photometry-this.tbl.
"""
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException

from app.models import SpectralSummary, SpectrumDataPoint
from app.services.data_service import data_service

router = APIRouter(prefix="/spectral", tags=["Spectral Explorer"])

@router.get("/m101", response_model=SpectralSummary)
def get_m101_spectral_summary():
    """Returns the full 371-channel SPHEREx calibrated spectrum of M101."""
    return data_service.get_m101_spectral_summary()

@router.get("/points", response_model=List[SpectrumDataPoint])
def get_spectral_points(
    band: Optional[str] = Query(None, description="Filter by band name (e.g. SPHEREx-D1)"),
    min_wavelength: Optional[float] = Query(None, description="Minimum wavelength in microns"),
    max_wavelength: Optional[float] = Query(None, description="Maximum wavelength in microns"),
    min_snr: Optional[float] = Query(None, description="Minimum SNR"),
):
    """Filter individual spectral data points across wavelengths and bands."""
    summary = data_service.get_m101_spectral_summary()
    pts = summary.points
    if band:
        pts = [p for p in pts if p.band_name.lower() == band.lower()]
    if min_wavelength is not None:
        pts = [p for p in pts if p.wavelength_um >= min_wavelength]
    if max_wavelength is not None:
        pts = [p for p in pts if p.wavelength_um <= max_wavelength]
    if min_snr is not None:
        pts = [p for p in pts if p.snr >= min_snr]
    return pts
