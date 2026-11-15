"""
SPHEREx Screening Service: Flag decoding, photometric quality evaluation,
and aperture artifact diagnostics ported directly from spherex_screening_pipeline.py.
"""
from typing import List, Dict, Any, Optional

# Compatibility entry point; product ingestion resolves MP_* headers independently.
from app.services.astronomy.quality import SPHEREX_FLAGS, FATAL_BITS, FATAL_MASK, decode_flags


def decode_spherex_flags(flag_val: Optional[int]) -> List[str]:
    return decode_flags(flag_val)


def get_flag_dictionary() -> List[Dict[str, Any]]:
    """Return all known SPHEREx flag bits with metadata for the UI documentation & badges."""
    return [
        {
            "bit": bit,
            "name": info["name"],
            "desc": info["desc"],
            "fatal": info["fatal"],
            "category": info["category"],
        }
        for bit, info in sorted(SPHEREX_FLAGS.items())
    ]

def evaluate_aperture_quality(
    center_finite: bool,
    center_flags_raw: Optional[int],
    aperture_finite_pixels: int,
    aperture_fatal_count: int,
    aperture_total_pixels: int,
    bg_usable_pixels: int,
    variance_available: bool,
    target_inside: bool,
) -> Dict[str, Any]:
    """
    Evaluates science quality using rigorous multi-stage threshold logic.
    """
    if not target_inside:
        return {
            "status": "REJECTED_GEOMETRY",
            "reason": "Target falls outside image cutout bounds.",
            "usable": False,
        }

    if not center_finite:
        center_flags = decode_spherex_flags(center_flags_raw)
        flag_str = "|".join(center_flags) if center_flags else "NO_FLAGS"
        return {
            "status": "REJECTED_INVALID_PIXEL",
            "reason": f"Central pixel is nonfinite; active flags: {flag_str}. Nonfinite data alone does not identify saturation.",
            "usable": False,
        }

    if not variance_available:
        return {
            "status": "REJECTED_NO_VARIANCE",
            "reason": "VARIANCE plane missing or entirely non-finite.",
            "usable": False,
        }

    if bg_usable_pixels < 10:
        return {
            "status": "REJECTED_NO_BACKGROUND",
            "reason": f"Only {bg_usable_pixels} clean pixels in background annulus (minimum 10 required).",
            "usable": False,
        }

    if aperture_total_pixels > 0 and (aperture_fatal_count / aperture_total_pixels) > 0.5:
        return {
            "status": "REJECTED_APERTURE_CORRUPT",
            "reason": f">{50:.0f}% of aperture pixels carry fatal detector corruption flags.",
            "usable": False,
        }

    if aperture_fatal_count > 0:
        return {
            "status": "FEASIBLE_WITH_CAVEATS",
            "reason": f"Central pixel valid; {aperture_fatal_count} non-central aperture pixel(s) carry flags. Usable with PSF fitting or masked aperture.",
            "usable": True,
        }

    return {
        "status": "PASSED_CLEAN",
        "reason": "Observation meets all geometry, validity, flag, and background criteria.",
        "usable": True,
    }
