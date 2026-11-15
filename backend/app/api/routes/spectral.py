"""
Spectral Explorer API routes for calibrated spectrophotometric SEDs.
"""
from fastapi import APIRouter
from app.services.storage.repository import repository

router = APIRouter(prefix="/spectral", tags=["Spectral Explorer"])

@router.get("/m101")
def get_m101_spectral():
    points = repository.get_m101_photometry()
    snrs = [p["snr"] for p in points if p.get("snr") is not None]
    median_snr = sorted(snrs)[len(snrs) // 2] if snrs else 0.0
    highest_flux_point = max(points, key=lambda p: p["flux_ujy"]) if points else None
    return {
        "target": "M101",
        "ra": 210.80227,
        "dec": 54.34895,
        "total_points": len(points),
        "wavelength_range_um": [0.737, 5.0],
        "bands": ["SPHEREx-D1", "SPHEREx-D2", "SPHEREx-D3", "SPHEREx-D4", "SPHEREx-D5", "SPHEREx-D6"],
        "points": points,
        "median_snr": round(median_snr, 1),
        "highest_flux_point": highest_flux_point,
    }
