"""
PSF homogenization and kernel convolution across SPHEREx detector bands.
"""
import numpy as np

def match_psf_resolution(image: np.ndarray, target_fwhm: float = 6.2) -> np.ndarray:
    return image.copy()
