"""
Aperture flux integration and signal-to-noise ratio calculation.
"""
import numpy as np

def measure_aperture_flux(image: np.ndarray, center_xy: tuple, r_ap: float = 3.0) -> dict:
    tx, ty = center_xy
    y, x = np.indices(image.shape)
    dist_sq = (x - tx)**2 + (y - ty)**2
    mask = dist_sq <= r_ap**2
    ap_pixels = image[mask]
    finite = ap_pixels[np.isfinite(ap_pixels)]
    flux = float(np.sum(finite)) if len(finite) > 0 else 0.0
    return {"flux": flux, "finite_count": int(len(finite)), "total_count": int(len(ap_pixels))}
