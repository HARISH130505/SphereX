"""
SPHEREx detector flag bitmasks and quality classification.
"""
from typing import List, Dict, Any, Optional

import numpy as np
from urllib.parse import urlsplit

FLAG_DOCUMENTATION = "https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/sp.html"
BRIGHTNESS_THRESHOLD_MJY_SR = 3000.0
POLICY_VERSION = "conservative_detector_mask_v1"
INFORMATIONAL_FLAGS = {"SOURCE", "FULLSAMPLE"}
# Published image-plane schema, not the separate high-bit spectrophotometry flags.
DOCUMENTED_IMAGE_FLAGS = {
    0: "TRANSIENT", 1: "OVERFLOW", 2: "SUR_ERROR",
    6: "NONFUNC", 7: "DICHROIC", 9: "MISSING_DATA", 10: "HOT", 11: "COLD",
    12: "FULLSAMPLE", 14: "PHANMISS", 15: "NONLINEAR", 17: "PERSIST",
    19: "OUTLIER", 20: "CROSSTALK", 21: "SOURCE", 22: "GHOST", 23: "GHOST_FPA",
    24: "GHOST_EXT", 25: "STREAK", 26: "BLOOM", 27: "SNOWBALL", 28: "HALO", 29: "SATELLITE_HALO",
}
# Simulator/catalog display only. Real FITS decoding uses its resolved definitions.
SPHEREX_FLAGS = {bit: {"name": name, "desc": name.replace("_", " "),
    "fatal": name not in INFORMATIONAL_FLAGS,
    "category": "informational" if name in INFORMATIONAL_FLAGS else "excluded_by_policy"}
    for bit, name in DOCUMENTED_IMAGE_FLAGS.items()}
FATAL_BITS = [bit for bit, info in SPHEREX_FLAGS.items() if info["fatal"]]
FATAL_MASK = sum(1 << bit for bit in FATAL_BITS)


def decode_flags(flag_val: Optional[int], definitions=None) -> List[str]:
    if flag_val is None:
        return []
    try:
        value = int(flag_val)
        definitions = definitions if definitions is not None else DOCUMENTED_IMAGE_FLAGS
        names = [name for bit, name in sorted(definitions.items()) if value & (1 << bit)]
        known = sum(1 << bit for bit in definitions)
        if value & ~known:
            names.append("UNKNOWN_BITS")
        return names
    except (ValueError, TypeError, OverflowError):
        return []


def read_quality_planes(hdul, image, cutout_url):
    """Preserve original FLAGS and resolve its meanings from headers/release metadata.

    Unknown set bits and every noninformational flag are excluded conservatively.
    Missing/invalid planes or definitions are never interpreted as an all-clean mask.
    """
    shape = image.shape
    raw = None
    definitions, descriptions = {}, {}
    issues = []
    source = "UNAVAILABLE"
    if "FLAGS" in hdul and hdul["FLAGS"].data is not None:
        raw = np.array(hdul["FLAGS"].data, copy=True)
        headers = [hdul["FLAGS"].header] + [h.header for h in hdul if h.name != "FLAGS"]
        for header in headers:
            for key, value in header.items():
                if not key.startswith("MP_"):
                    continue
                name = key[3:]
                if not isinstance(value, (int, np.integer)) or not 0 <= value < 64:
                    issues.append(f"Invalid mask definition {key}={value}")
                    continue
                bit = int(value)
                if bit in definitions and definitions[bit] != name:
                    issues.append(f"Conflicting definitions for bit {bit}")
                if name in definitions.values() and definitions.get(bit) != name:
                    issues.append(f"Conflicting bit positions for {name}")
                definitions[bit] = name
                descriptions[bit] = header.comments[key]
        if definitions:
            source = "FITS_MP_HEADERS"
        else:
            parsed = urlsplit(cutout_url)
            path = parsed.path.lower()
            # The archive URL is product provenance; arbitrary local files do not
            # inherit a mission schema merely from a guessed detector name.
            if parsed.hostname == "irsa.ipac.caltech.edu" and any(f"/spherex/{release}/level2/" in path for release in ("qr2", "qr3")):
                definitions = DOCUMENTED_IMAGE_FLAGS.copy()
                source = "DOCUMENTED_RELEASE_SCHEMA"
            else:
                issues.append("No MP_* definitions or recognized release metadata")
    else:
        issues.append("FLAGS plane is missing")
    if raw is not None and (raw.shape != shape or raw.dtype.kind not in "iu" or raw.dtype.itemsize > 8):
        issues.append("FLAGS must be an integer plane matching IMAGE")
    verified = raw is not None and not issues and bool(definitions)
    values = np.zeros(shape, dtype=np.uint64)
    if raw is not None and raw.shape == shape and raw.dtype.kind in "iu" and raw.dtype.itemsize <= 8:
        # Preserve signed FITS storage bit patterns without sign-extending to 64 bits.
        values = raw.astype(np.dtype(f"u{raw.dtype.itemsize}")).astype(np.uint64)
    known = sum(1 << bit for bit in definitions)
    unknown = (values & np.uint64(((1 << 64)-1) ^ known)) != 0
    masks = {}
    excluded = unknown.copy()
    for bit, name in definitions.items():
        mask = (values & np.uint64(1 << bit)) != 0
        masks[name.lower()] = mask
        if name not in INFORMATIONAL_FLAGS:
            excluded |= mask
    masks["unknown_bits"] = unknown
    masks["nonfinite_image"] = ~np.isfinite(image)
    masks["brightness_threshold"] = np.isfinite(image) & (image >= BRIGHTNESS_THRESHOLD_MJY_SR)
    # No physical saturation state is inferred from a NaN or from SUR_ERROR.
    masks["glitch"] = masks.get("transient", np.zeros(shape, bool)) | masks.get("glitch", np.zeros(shape, bool))
    excluded |= masks["nonfinite_image"] | masks["brightness_threshold"]
    if not verified:
        excluded[:] = True
    masks["quality_excluded"] = excluded
    summary = {"status": "VERIFIED" if verified else "UNVERIFIED", "definitions_source": source,
        "documentation": FLAG_DOCUMENTATION if source == "DOCUMENTED_RELEASE_SCHEMA" else None,
        "policy_version": POLICY_VERSION, "informational_flags": sorted(INFORMATIONAL_FLAGS),
        "excluded_flags": sorted(name for name in definitions.values() if name not in INFORMATIONAL_FLAGS),
        "definitions": [{"bit": bit, "name": name, "description": descriptions.get(bit, "Published release flag")}
                        for bit, name in sorted(definitions.items())],
        "issues": issues, "raw_dtype": str(raw.dtype) if raw is not None else None,
        "mask_counts": {name: int(mask.sum()) for name, mask in masks.items()},
        "valid_pixel_count": int((~excluded).sum()), "brightness_threshold_mjy_sr": BRIGHTNESS_THRESHOLD_MJY_SR}
    return {"flags_raw": raw, "flags_uint64": values, "flag_definitions": definitions,
            "quality_verified": verified, "quality_masks": masks,
            "quality_valid_mask": ~excluded, "quality_summary": summary}

def evaluate_quality(
    center_finite: bool,
    center_flags_raw: Optional[int],
    aperture_fatal_count: int,
    aperture_total_pixels: int,
    bg_usable_pixels: int,
    variance_available: bool,
    target_inside: bool,
) -> Dict[str, Any]:
    if not target_inside:
        return {"status": "REJECTED_GEOMETRY", "reason": "Target falls outside image cutout.", "usable": False}
    if not center_finite:
        flags = decode_flags(center_flags_raw)
        return {"status": "REJECTED_INVALID_PIXEL", "reason": f"Central pixel is nonfinite; flags: {'|'.join(flags) or 'unavailable'}. A nonfinite value alone does not identify saturation.", "usable": False}
    if not variance_available:
        return {"status": "REJECTED_NO_VARIANCE", "reason": "Variance array missing or non-finite.", "usable": False}
    if bg_usable_pixels < 10:
        return {"status": "REJECTED_NO_BACKGROUND", "reason": f"Only {bg_usable_pixels} clean background pixels (<10).", "usable": False}
    if aperture_total_pixels > 0 and (aperture_fatal_count / aperture_total_pixels) > 0.5:
        return {"status": "REJECTED_APERTURE_CORRUPT", "reason": ">50% fatal flags in aperture.", "usable": False}
    if aperture_fatal_count > 0:
        return {"status": "FEASIBLE_WITH_CAVEATS", "reason": f"{aperture_fatal_count} non-central aperture pixel(s) carry flags.", "usable": True}
    return {"status": "PASSED_CLEAN", "reason": "Meets all geometric, flag, background, and variance criteria.", "usable": True}
