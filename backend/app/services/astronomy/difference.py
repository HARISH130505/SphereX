"""
Differential image calculation and variance-propagated significance mapping.
Propagates diagonal variances under independent input-exposure assumptions:
    D = I2 - I1
    Var(D) = Var(I1) + Var(I2)
    S = D / sqrt(Var(D))
Accounts for NaN/inf pixels, saturated detector cores, missing variance,
and common valid survey footprints.
"""
from typing import Dict, Any, Optional, Tuple
import numpy as np
from app.services.astronomy.quality import BRIGHTNESS_THRESHOLD_MJY_SR


def compute_difference_map(
    img1: np.ndarray,
    img2: np.ndarray,
    var1: np.ndarray,
    var2: np.ndarray,
    valid_mask: Optional[np.ndarray] = None,
    saturation_threshold_mjy_sr: float = BRIGHTNESS_THRESHOLD_MJY_SR,
    variance_provenance: Optional[Tuple[str, str]] = None,
    quality_masks: Optional[Dict[str, np.ndarray]] = None,
) -> Dict[str, Any]:
    """
    Computes masked differences and diagonal-noise significance from measured variance.

    Parameters:
    - img1: Reference epoch calibrated flux array (MJy/sr)
    - img2: Target epoch calibrated flux array (MJy/sr), registered on img1 grid
    - var1: Reference epoch variance array (MJy^2/sr^2)
    - var2: Target epoch variance array (MJy^2/sr^2), registered on img1 grid
    - valid_mask: Boolean mask indicating valid celestial footprint overlap
    - saturation_threshold_mjy_sr: Flux ceiling above which pixels are treated as saturated/non-linear

    Returns:
    - diff: Differential flux array (I2 - I1) with invalid/saturated pixels set to NaN
    - significance: Unitless S/N significance map S = D / sqrt(Var(D))
    - total_variance: Combined variance map Var(D) = Var(I1) + Var(I2)
    - peak_sig: Peak absolute significance |S| evaluated strictly over valid pixels
    - mean_diff: Mean residual flux over valid uncorrupted pixels
    - median_diff: Median residual flux over valid uncorrupted pixels
    - rms_diff: Root-mean-square residual flux over valid uncorrupted pixels
    - valid_pixel_count: Number of uncorrupted astronomical pixels evaluated
    - saturated_pixel_count: Number of detector-saturated pixels masked
    """
    # Shared dimensions are necessary but do not establish celestial registration.
    if img1.shape != img2.shape or var1.shape != img1.shape or var2.shape != img1.shape:
        raise ValueError("Difference imaging requires matching registered science and variance grids")
    if valid_mask is not None and valid_mask.shape != img1.shape:
        raise ValueError("Validity mask must match the registered reference grid")

    # Raw difference: D = I2 - I1
    raw_diff = np.asarray(img2, dtype=float) - np.asarray(img1, dtype=float)

    # Missing, zero, negative or nonfinite variance remains invalid; never substitute.
    verified = variance_provenance is not None and len(variance_provenance) == 2 and all(item == "MEASURED" for item in variance_provenance)
    variance_valid = np.isfinite(var1) & (var1 > 0) & np.isfinite(var2) & (var2 > 0)
    total = np.asarray(var1, float) + np.asarray(var2, float)
    variance_valid &= np.isfinite(total) & (total > 0)
    tot_var = np.where(variance_valid, total, np.nan)
    # The brightness cutoff is an explicit engineering screen, not a physical flag.
    brightness_mask = (np.isfinite(img1) & (img1 >= saturation_threshold_mjy_sr)) | (np.isfinite(img2) & (img2 >= saturation_threshold_mjy_sr))
    masks = dict(quality_masks or {})
    for name, mask in masks.items():
        if np.asarray(mask).shape != img1.shape:
            raise ValueError(f"Quality mask {name} must match the reference grid")
    excluded = np.zeros(img1.shape, bool)
    for name in ("quality_excluded", "invalid_variance", "unknown_bits"):
        if name in masks:
            excluded |= masks[name]
    saturation = masks.get("saturated", np.zeros(img1.shape, bool))
    finite_mask = np.isfinite(raw_diff) & variance_valid & ~brightness_mask & ~excluded & ~saturation
    if not verified:
        finite_mask[:] = False
    raw_sig = np.full(img1.shape, np.nan, float)
    np.divide(raw_diff, np.sqrt(tot_var), out=raw_sig, where=finite_mask)

    finite_mask &= np.isfinite(raw_sig)
    if valid_mask is not None:
        strict_valid = finite_mask & valid_mask
    else:
        strict_valid = finite_mask

    # Mask difference and significance maps
    diff_out = np.where(strict_valid, raw_diff, np.nan)
    sig_out = np.where(strict_valid, raw_sig, np.nan)

    valid_vals = diff_out[strict_valid]
    valid_sigs = sig_out[strict_valid]

    if len(valid_sigs) > 0:
        peak_sig = float(np.max(np.abs(valid_sigs)))
        mean_diff = float(np.mean(valid_vals))
        median_diff = float(np.median(valid_vals))
        rms_diff = float(np.sqrt(np.mean(valid_vals ** 2)))
    else:
        peak_sig = mean_diff = median_diff = rms_diff = None

    return {
        "diff": diff_out,
        "significance": sig_out,
        "total_variance": np.where(strict_valid, tot_var, np.nan),
        "peak_sig": round(peak_sig, 3) if peak_sig is not None else None,
        "mean_diff": round(mean_diff, 4) if mean_diff is not None else None,
        "median_diff": round(median_diff, 4) if median_diff is not None else None,
        "rms_diff": round(rms_diff, 4) if rms_diff is not None else None,
        "valid_pixel_count": int(np.sum(strict_valid)),
        "saturated_pixel_count": int(np.sum(saturation)),
        "nonfinite_image_pixel_count": int((~np.isfinite(img1) | ~np.isfinite(img2)).sum()),
        "brightness_threshold_pixel_count": int(brightness_mask.sum()),
        "invalid_variance_pixel_count": int((~variance_valid).sum()),
        "quality_mask_counts": {name: int(np.count_nonzero(mask)) for name, mask in masks.items()},
        "variance_provenance": list(variance_provenance) if variance_provenance else ["UNVERIFIED", "UNVERIFIED"],
        "variance_propagation_verified": verified,
        "sat_mask": saturation, "brightness_mask": brightness_mask,
    }
