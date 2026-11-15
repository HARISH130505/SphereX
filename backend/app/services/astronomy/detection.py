"""
Astronomical Candidate Detection, Source Extraction, and Motion Assessment.
Maintains strict scientific separation between:
1. Detector quality screening (SUR errors, bitmasks, well depth saturation).
2. Astronomical source detection (localized residual flux peaks).
3. Cross-epoch positional matching (celestial angular separation).
4. Photometric variability analysis (flux ratios and confidence intervals).
5. Moving-object candidate assessment (proper motion and reflex parallax).
"""
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u


DEFAULT_RESIDUAL_THRESHOLD_SIGMA = 5.0
DEFAULT_RESIDUAL_MIN_PIXELS = 2

def compute_reflex_parallax(distance_au: float, baseline_au: float = 2.0) -> float:
    """
    Calculates apparent reflex parallax displacement for outer solar system objects
    observed over a 6-month SPHEREx survey sweep (baseline ~2 AU) in arcseconds.

    Formula:
        theta_reflex (arcsec) = (baseline_au / distance_au) * (180 * 3600 / pi)
                              ~ (baseline_au * 206,264.8) / distance_au
    """
    if distance_au <= 0:
        return 0.0
    return float((baseline_au * 206264.806) / distance_au)


def estimate_apparent_distance_from_motion(delta_arcsec: float, dt_days: float) -> Optional[float]:
    """
    Estimate hypothetical outer solar system heliocentric distance (AU)
    assuming observed angular displacement is primarily Earth reflex parallax.
    Valid for observation intervals near 180 days (6 months).
    """
    if delta_arcsec <= 0.01 or dt_days <= 1.0:
        return None
    # Fraction of 6-month Earth baseline spanned
    effective_baseline_au = min(2.0, 2.0 * (dt_days / 182.625))
    return float((effective_baseline_au * 206264.806) / delta_arcsec)


def detect_residual_sources(
    significance_map: np.ndarray,
    wcs: Optional[WCS] = None,
    diff_map: Optional[np.ndarray] = None,
    total_var: Optional[np.ndarray] = None,
    img1: Optional[np.ndarray] = None,
    img2: Optional[np.ndarray] = None,
    ref_target_coord: Optional[Tuple[float, float]] = None,
    is_saturated: bool = False,
    threshold_sigma: float = DEFAULT_RESIDUAL_THRESHOLD_SIGMA,
    min_pixels: int = DEFAULT_RESIDUAL_MIN_PIXELS,
    pixel_scale_arcsec: float = 6.2,
) -> List[Dict[str, Any]]:
    """
    Identifies localized, statistically significant astronomical flux concentrations
    in a difference significance map (|S| >= threshold_sigma).
    Performs centroiding, celestial projection, aperture photometry, astrometric
    uncertainty estimation, and five-category scientific candidate classification.
    """
    valid = np.isfinite(significance_map)
    if not np.any(valid):
        return []

    sig = np.where(valid, significance_map, 0.0)
    high_sig_mask = np.abs(sig) >= threshold_sigma

    if not np.any(high_sig_mask):
        return []

    from scipy.ndimage import label

    labeled_array, num_features = label(high_sig_mask)
    sources: List[Dict[str, Any]] = []
    h, w = significance_map.shape

    for feat_id in range(1, num_features + 1):
        feat_mask = labeled_array == feat_id
        pixel_count = int(np.sum(feat_mask))
        if pixel_count < min_pixels:
            continue

        # Centroid weighted by absolute significance
        weights = np.abs(sig[feat_mask])
        y_indices, x_indices = np.where(feat_mask)
        cy = float(np.sum(y_indices * weights) / np.sum(weights))
        cx = float(np.sum(x_indices * weights) / np.sum(weights))

        peak_val = float(np.max(sig[feat_mask]))
        min_val = float(np.min(sig[feat_mask]))
        peak_sig = peak_val if abs(peak_val) >= abs(min_val) else min_val

        # Astrometric centroid uncertainty: sigma_ast ~ FWHM / (2 * SNR)
        snr = max(abs(peak_sig), 1.0)
        ast_unc_arcsec = round(max(0.05, min(3.1, pixel_scale_arcsec / (2.0 * snr))), 3)

        # Photometry extraction
        flux_val = 0.0
        flux_err = 0.0
        if diff_map is not None:
            finite_diff = diff_map[feat_mask & np.isfinite(diff_map)]
            if len(finite_diff) > 0:
                flux_val = float(np.sum(finite_diff))
        if total_var is not None:
            finite_var = total_var[feat_mask & np.isfinite(total_var) & (total_var > 0)]
            if len(finite_var) > 0:
                flux_err = float(np.sqrt(np.sum(finite_var)))

        # Epoch sampling
        iy, ix = int(round(cy)), int(round(cx))
        f1_val = float(img1[iy, ix]) if img1 is not None and 0 <= iy < h and 0 <= ix < w and np.isfinite(img1[iy, ix]) else None
        f2_val = float(img2[iy, ix]) if img2 is not None and 0 <= iy < h and 0 <= ix < w and np.isfinite(img2[iy, ix]) else None

        source_info: Dict[str, Any] = {
            "source_id": feat_id,
            "centroid_xy": [round(cx, 2), round(cy, 2)],
            "pixel_count": pixel_count,
            "peak_significance": round(peak_sig, 2),
            "flux": round(flux_val, 4),
            "flux_err": round(flux_err, 4),
            "epoch_1_flux": round(f1_val, 4) if f1_val is not None else None,
            "epoch_2_flux": round(f2_val, 4) if f2_val is not None else None,
            "astrometric_uncertainty_arcsec": ast_unc_arcsec,
            "nature": "positive_excess" if peak_sig > 0 else "negative_deficit",
        }

        # Project centroid to celestial coordinates
        ra_deg, dec_deg = None, None
        if wcs is not None and wcs.has_celestial:
            try:
                ra_dec = wcs.all_pix2world([[cx, cy]], 0)[0]
                ra_deg = float(ra_dec[0])
                dec_deg = float(ra_dec[1])
                source_info["ra_deg"] = round(ra_deg, 6)
                source_info["dec_deg"] = round(dec_deg, 6)
            except Exception:
                pass

        # Angular separation from target catalog coordinates
        ang_sep_arcsec = None
        if ra_deg is not None and dec_deg is not None and ref_target_coord is not None:
            try:
                c_src = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg)
                c_tgt = SkyCoord(ra=ref_target_coord[0] * u.deg, dec=ref_target_coord[1] * u.deg)
                ang_sep_arcsec = float(c_src.separation(c_tgt).arcsec)
                source_info["angular_separation_from_target_arcsec"] = round(ang_sep_arcsec, 3)
            except Exception:
                pass

        # Edge proximity check
        is_edge = (cx < 1.5 or cy < 1.5 or cx >= w - 1.5 or cy >= h - 1.5)

        # Scientific classification into 5 distinct categories
        if is_saturated:
            classification = "DETECTOR_ARTIFACT"
            rationale = "Target exhibits central detector saturation (SUR ramp fit overflow). Difference peak reflects masked saturation boundary."
        elif is_edge:
            classification = "INSUFFICIENT_EVIDENCE"
            rationale = "Candidate is located on the boundary edge of the detector cutout or reprojection footprint."
        else:
            classification = "INSUFFICIENT_EVIDENCE"
            rationale = "A residual or target-center offset alone cannot establish source motion or variability. Consult independent-epoch source associations."

        source_info["classification"] = classification
        source_info["classification_rationale"] = rationale

        sources.append(source_info)

    return sources


def cross_epoch_positional_match(
    coord1: Tuple[float, float],
    coord2: Tuple[float, float],
    match_radius_arcsec: float = 3.1,
) -> Dict[str, Any]:
    """
    Cross-matches celestial coordinates between two epochs.
    match_radius_arcsec defaults to 3.1" (half SPHEREx FWHM of 6.2").
    """
    ra1, dec1 = coord1
    ra2, dec2 = coord2
    c1 = SkyCoord(ra=ra1 * u.deg, dec=dec1 * u.deg)
    c2 = SkyCoord(ra=ra2 * u.deg, dec=dec2 * u.deg)
    sep_arcsec = float(c1.separation(c2).arcsec)

    is_matched = sep_arcsec <= match_radius_arcsec
    return {
        "angular_separation_arcsec": round(sep_arcsec, 3),
        "is_spatially_coincident": is_matched,
        "classification": "stationary_source" if is_matched else "spatially_displaced",
    }


def evaluate_variability(
    flux1: float, flux2: float, var1: float, var2: float,
    *, variance_provenance=None,
) -> Dict[str, Any]:
    """Legacy scalar helper: unknown/invalid variance cannot establish variability."""
    values = np.asarray([flux1, flux2, var1, var2], dtype=float)
    verified = (variance_provenance is not None and len(variance_provenance) == 2 and
                all(value == "MEASURED" for value in variance_provenance))
    finite_flux = bool(np.all(np.isfinite(values[:2])))
    delta = float(values[1]-values[0]) if finite_flux else None
    ratio = float(values[1]/values[0]) if finite_flux and values[0] != 0 else None
    result = {"flux_ratio": ratio, "delta_flux": delta,
              "variability_significance_sigma": None, "is_statistically_variable": False,
              "status": "INSUFFICIENT_EVIDENCE"}
    if not verified or not np.all(np.isfinite(values)) or np.any(values[2:] <= 0):
        return result
    combined = float(values[2]+values[3])
    if not np.isfinite(combined) or combined <= 0:
        return result
    significance = delta / np.sqrt(combined)
    if not np.isfinite(significance):
        return result
    result.update(variability_significance_sigma=round(float(significance), 2),
                  is_statistically_variable=bool(abs(significance) >= 3),
                  status="MEASURED_VARIANCE_COMPARISON")
    return result


def assess_candidate(
    peak_sig: float,
    dt_days: float,
    is_saturated: bool = False,
    angular_displacement_arcsec: Optional[float] = None,
    *,
    motion_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Summarize measured source associations, never pointing/target separation.

    The legacy angular_displacement_arcsec argument is intentionally ignored:
    an unassociated scalar is not evidence. confidence_score remains zero for
    API compatibility and is explicitly uncalibrated, not a probability.
    """
    result = {"category": "INSUFFICIENT_EVIDENCE", "detected": False,
              "confidence_score": 0.0, "confidence_score_calibrated": False,
              "peak_sig": peak_sig, "proper_motion_arcsec_per_yr": None,
              "scientific_assessment": "Independent epoch measurements and reliable celestial registration are required; a scalar separation is insufficient."}
    if is_saturated:
        result.update(category="DETECTOR_ARTIFACT", scientific_assessment=(
            "Known detector saturation prevents reliable source astrometry. These residuals cannot be interpreted as an astronomical transient or moving object."))
        return result
    if (not motion_analysis or motion_analysis.get("status") != "VALID_FOR_SOURCE_ASSOCIATION" or
            not np.isfinite(dt_days) or dt_days <= 0):
        if motion_analysis:
            result["scientific_assessment"] = "; ".join(motion_analysis.get("failure_reasons", [])) or "Insufficient source association evidence."
        return result
    associations = motion_analysis.get("associations", [])
    for category in ["POSSIBLE_MOVING_OBJECT_CANDIDATE", "VARIABLE_SOURCE", "STATIONARY_ASTRONOMICAL_SOURCE"]:
        selected = [a for a in associations if a["classification"] == category]
        if selected:
            result.update(category=category, detected=category != "STATIONARY_ASTRONOMICAL_SOURCE",
                          association_count=len(selected), scientific_assessment=(
                              f"{len(selected)} source association(s): {category}. " + selected[0]["rationale"]))
            if category == "POSSIBLE_MOVING_OBJECT_CANDIDATE" and len(selected) == 1:
                result["proper_motion_arcsec_per_yr"] = selected[0]["proper_motion_arcsec_per_yr"]
            break
    return result


def evaluate_transient_candidate(peak_sig: float, dt_days: float) -> dict:
    """
    Backward-compatible adapter for existing epoch comparison endpoints.
    """
    res = assess_candidate(peak_sig, dt_days, is_saturated=False)
    return {
        "detected": res["detected"],
        "score": res["confidence_score"],
        "peak_sig": peak_sig,
        "category": res["category"],
        "assessment": res["scientific_assessment"],
    }
