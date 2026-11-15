"""
Background estimation using circular annulus around astronomical sources.
"""
import numpy as np

def estimate_annulus_background(image: np.ndarray, center_xy: tuple, r_in: float = 6.0, r_out: float = 10.0) -> dict:
    tx, ty = center_xy
    y, x = np.indices(image.shape)
    dist_sq = (x - tx)**2 + (y - ty)**2
    mask = (dist_sq >= r_in**2) & (dist_sq <= r_out**2)
    pix = image[mask]
    finite_pix = pix[np.isfinite(pix)]
    median_val = float(np.median(finite_pix)) if len(finite_pix) > 0 else 0.0
    return {"median": median_val, "usable_pixels": int(len(finite_pix))}
