"""
Validation of archive responses and FITS file integrity.
"""
def validate_fits_header(header: dict) -> bool:
    required_keys = ["NAXIS", "BITPIX"]
    return all(k in header for k in required_keys)
