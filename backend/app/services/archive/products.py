"""
Product URL resolution for Level 2 FITS cutouts and spectrophotometry tables.
"""
from urllib.parse import urlencode

def construct_cutout_url(base_fits_url: str, ra: float, dec: float, size_deg: float = 0.1) -> str:
    clean_base = base_fits_url.split("?")[0]
    params = {"center": f"{ra},{dec}", "size": str(size_deg)}
    return f"{clean_base}?{urlencode(params)}"
