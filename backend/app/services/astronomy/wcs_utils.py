"""
WCS coordinate transformations and pixel scale utilities.
"""
def arcsec_to_pixels(arcsec: float, plate_scale_arcsec_per_px: float = 6.2) -> float:
    return arcsec / plate_scale_arcsec_per_px

def pixels_to_arcsec(pixels: float, plate_scale_arcsec_per_px: float = 6.2) -> float:
    return pixels * plate_scale_arcsec_per_px
