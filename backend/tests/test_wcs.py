"""
Unit tests for WCS pixel conversions.
"""
from app.services.astronomy.wcs_utils import arcsec_to_pixels, pixels_to_arcsec

def test_wcs_scaling():
    # SPHEREx plate scale: 6.2 arcsec/pixel
    px = arcsec_to_pixels(12.4, 6.2)
    assert px == 2.0
    arcsec = pixels_to_arcsec(3.0, 6.2)
    assert round(arcsec, 1) == 18.6
