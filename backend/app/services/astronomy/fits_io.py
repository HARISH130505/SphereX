"""
Genuine SPHEREx FITS array extraction, WCS processing, contrast stretching, and PNG rasterization.
Replaces synthetic Gaussian modeling with real multi-extension FITS file processing.
"""
import io
import hashlib
import base64
import json
import threading
from urllib.parse import urlsplit, parse_qs
import requests
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import numpy as np
import matplotlib
from PIL import Image, ImageDraw
import astropy.io.fits as fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
import astropy.units as u
from app.services.astronomy.quality import read_quality_planes

from app.config import CACHE_DIR
from app.utils.logging_utils import get_logger

logger = get_logger("astronomy.fits_io")
_download_locks = [threading.Lock() for _ in range(32)]

def get_fits_cache_path(obs_id: str, band: str) -> Path:
    """Return local cache path for an observation FITS product."""
    safe_name = f"{obs_id}_{band}.fits".replace("/", "_").replace(":", "_")
    return CACHE_DIR / safe_name


def fetch_or_load_fits_file(obs) -> Path:
    with _download_locks[hash((obs.obs_id, obs.band)) % len(_download_locks)]:
        return _fetch_or_load_fits_file(obs)


def _fetch_or_load_fits_file(obs) -> Path:
    """
    Ensure the real FITS file is available in local cache.
    Downloads from obs.cutout_url if not cached and URL is valid.
    Raises FileNotFoundError if archive download failed or file is unavailable.
    """
    # 1. Check local cache
    local_path = get_fits_cache_path(obs.obs_id, obs.band)
    if local_path.exists() and local_path.stat().st_size > 1000:
        return local_path

    # Never fall back to a bandless cache file: its product identity is unverified.

    # Retry authoritative URLs even when a historical catalog row records a failure.
    url = getattr(obs, "cutout_url", None)
    if not url or not url.startswith("http"):
        raise FileNotFoundError(
            f"No valid archive cutout URL for observation {obs.obs_id} ({obs.band})."
        )

    try:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        diagnostic = {"product_id": getattr(obs, "product_id", f"{obs.obs_id}::{obs.band}"),
            "center": query.get("center", [None])[0], "size": query.get("size", [None])[0],
            "archive_endpoint": f"{parsed.scheme}://{parsed.netloc}{parsed.path}"}
        logger.info("archive_cutout_request %s", json.dumps(diagnostic, sort_keys=True))
        # requests uses its maintained CA bundle with certificate and hostname verification.
        response = requests.get(url, timeout=25,
            headers={"User-Agent": "SPHEREx-Explorer/2.1 (Astrophysics Data Retrieval)"})
        if (response.status_code == 422 and 'arrays do not overlap' in response.text.lower()
                and getattr(obs, 'access_url', None)):
            logger.warning('Cutout footprint mismatch product=%s; trying bounded complete product', obs.product_id)
            # Complete product fallback is bounded; never substitute another observation.
            with requests.get(obs.access_url, timeout=(5, 30), stream=True) as full:
                full.raise_for_status()
                limit = 128 * 1024 * 1024
                if int(full.headers.get('Content-Length', 0)) > limit:
                    raise FileNotFoundError('Complete product exceeds the 128 MiB demo download limit; choose another product.')
                chunks, size = [], 0
                for chunk in full.iter_content(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        raise FileNotFoundError('Complete product exceeds the 128 MiB demo download limit; choose another product.')
                    chunks.append(chunk)
                content = b''.join(chunks)
            with fits.open(io.BytesIO(content)) as check:
                check.verify('exception')
            temporary = local_path.with_suffix('.download')
            temporary.write_bytes(content)
            temporary.replace(local_path)
            return local_path
        if response.status_code >= 400:
            detail = response.text[:300].replace("\n", " ").strip()
            logger.warning("archive_cutout_failure %s", json.dumps({**diagnostic,
                "http_status": response.status_code, "error_detail": detail}, sort_keys=True))
            raise FileNotFoundError(
                f"Archive cutout failed for {diagnostic['product_id']}: HTTP {response.status_code}; {detail or 'no response detail'}")
        content = response.content
        if len(content) < 1000:
            raise ValueError("Archive returned empty or truncated file.")
        with fits.open(io.BytesIO(content)) as check:
            check.verify('exception')
        temporary = local_path.with_suffix('.download')
        temporary.write_bytes(content)
        temporary.replace(local_path)
        return local_path
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.warning("archive_cutout_failure %s", json.dumps({**locals().get("diagnostic", {}),
            "http_status": None, "error_type": type(e).__name__, "error_detail": str(e)[:300]}, sort_keys=True))
        raise FileNotFoundError(
            f"Failed to retrieve FITS cutout from archive ({url}): {e}"
        )


def load_fits_image(obs) -> Dict[str, Any]:
    """
    Load and process a genuine SPHEREx FITS product for an observation.
    Extracts the IMAGE HDU, VARIANCE HDU, calculates real array statistics,
    and resolves celestial WCS coordinates.
    """
    fits_path = fetch_or_load_fits_file(obs)

    # Hash the exact immutable byte snapshot parsed below, not a later cache reread.
    fits_bytes = fits_path.read_bytes()
    fits_provenance = {"sha256": hashlib.sha256(fits_bytes).hexdigest(),
                       "byte_count": len(fits_bytes), "status": "AVAILABLE",
                       "scope": "complete_fits_file_bytes"}
    with fits.open(io.BytesIO(fits_bytes), memmap=False) as hdul:
        # Locate IMAGE HDU
        img_hdu = None
        if "IMAGE" in hdul:
            img_hdu = hdul["IMAGE"]
        elif hdul[0].data is not None and getattr(hdul[0].data, "ndim", 0) == 2:
            # Support primary-HDU science images, never mistake FLAGS/VARIANCE for IMAGE.
            img_hdu = hdul[0]

        if img_hdu is None or img_hdu.data is None:
            raise ValueError(f"No 2D image data found in FITS product {fits_path.name}")

        image_arr = np.array(img_hdu.data, dtype=np.float64)
        if image_arr.ndim != 2:
            raise ValueError("IMAGE must be two-dimensional")

        # Preserve measured variance, including invalid entries; no fabricated estimate.
        var_raw = None
        var_bunit = None
        variance_issues = []
        if "VARIANCE" in hdul and hdul["VARIANCE"].data is not None:
            var_raw = np.array(hdul["VARIANCE"].data, copy=True)
            var_bunit = hdul["VARIANCE"].header.get("BUNIT")
        variance_provenance = "MEASURED" if var_raw is not None else "UNAVAILABLE"
        var_arr = np.full(image_arr.shape, np.nan, dtype=np.float64)
        if var_raw is not None and var_raw.shape == image_arr.shape:
            var_arr = np.array(var_raw, dtype=np.float64)
        elif var_raw is not None:
            variance_issues.append("VARIANCE dimensions do not match IMAGE")
        else:
            variance_issues.append("VARIANCE plane is missing; no estimate was substituted")
        bunit = img_hdu.header.get("BUNIT")
        try:
            image_units_verified = bunit is not None and u.Unit(bunit) == u.MJy/u.sr
            variance_units_verified = var_bunit is not None and u.Unit(var_bunit) == (u.MJy/u.sr)**2
        except (ValueError, TypeError):
            image_units_verified = variance_units_verified = False
        if not image_units_verified:
            variance_issues.append("IMAGE units are missing or not MJy/sr")
        if not variance_units_verified:
            variance_issues.append("VARIANCE units are missing or not (MJy/sr)^2")
        variance_valid = np.isfinite(var_arr) & (var_arr > 0)
        science_units_verified = bool(image_units_verified and variance_units_verified)
        quality = read_quality_planes(hdul, image_arr, obs.cutout_url)
        valid_mask = quality["quality_valid_mask"] & variance_valid
        if not science_units_verified:
            valid_mask[:] = False
        variance_summary = {"provenance": variance_provenance, "unit": var_bunit,
            "image_unit": bunit, "units_verified": science_units_verified,
            "valid_pixel_count": int(variance_valid.sum()),
            "invalid_pixel_count": int((~variance_valid).sum()), "issues": variance_issues,
            "estimation_method": None}
        # Parse native WCS without substituting an assumed celestial transform.
        wcs_info = {}
        wcs = None
        try:
            wcs = WCS(img_hdu.header)
            if wcs.has_celestial:
                wcs_info = {
                    "ra_center": float(wcs.wcs.crval[0]),
                    "dec_center": float(wcs.wcs.crval[1]),
                    "ctype": [str(c) for c in wcs.wcs.ctype],
                    "pixel_scale_arcsec": 6.2,
                }
                if hasattr(wcs, "pixel_scale_matrix"):
                    try:
                        ps = np.sqrt(np.prod(np.abs(proj_plane_pixel_scales(wcs.celestial)))) * 3600.0
                        wcs_info["pixel_scale_arcsec"] = round(float(ps), 3)
                    except Exception:
                        pass
        except Exception:
            pass

    # Dynamic image dimensions
    h, w = image_arr.shape
    shape = [int(h), int(w)]

    # Compute array statistics preserving NaNs and saturation values
    finite_mask = np.isfinite(image_arr)
    nan_count = int(np.isnan(image_arr).sum())
    total_pixels = int(image_arr.size)
    valid_pct = round((float(finite_mask.sum()) / float(total_pixels)) * 100.0, 2)

    if finite_mask.any():
        min_val = round(float(np.min(image_arr[finite_mask])), 4)
        max_val = round(float(np.max(image_arr[finite_mask])), 4)
        median_val = round(float(np.median(image_arr[finite_mask])), 4)
    else:
        min_val = max_val = median_val = None

    # Determine target center in pixel coordinates
    tx = getattr(obs, "target_x", None)
    ty = getattr(obs, "target_y", None)
    if tx is None or ty is None or tx < 0 or ty < 0 or tx >= w or ty >= h:
        # Fallback to geometric center of cutout
        tx = float(w) / 2.0
        ty = float(h) / 2.0
    else:
        tx = float(tx)
        ty = float(ty)

    # Determine central pixel value
    iy, ix = int(round(ty)), int(round(tx))
    if 0 <= iy < h and 0 <= ix < w:
        center_pixel_val = float(image_arr[iy, ix])
        if not np.isfinite(center_pixel_val):
            center_val = None
        else:
            center_val = round(center_pixel_val, 4)
    else:
        center_val = getattr(obs, "center_image_val", None)

    return {
        "image": image_arr,
        "variance": var_arr,
        "variance_provenance": variance_provenance,
        "variance_raw": var_raw,
        "variance_summary": variance_summary,
        "science_units_verified": science_units_verified,
        "valid_mask": valid_mask,
        **quality,
        "shape": shape,
        "target_xy": [round(tx, 2), round(ty, 2)],
        "min_val": min_val,
        "max_val": max_val,
        "median_val": median_val,
        "nan_count": nan_count,
        "valid_pct": valid_pct,
        "wcs": wcs,
        "wcs_info": wcs_info,
        "bunit": bunit,
        "var_bunit": var_bunit,
        "source_file": fits_path.name,
        "fits_provenance": fits_provenance,
        "center_val": center_val,
        "observation_quality": classify_observation_quality(
            image_arr, valid_mask, quality["quality_masks"], quality["quality_verified"],
            science_units_verified, variance_provenance, wcs, (iy, ix)),
    }


def classify_observation_quality(image, valid_mask, masks, quality_verified,
                                 units_verified, variance_provenance, wcs, center_yx):
    """Separate pixel states from observation capabilities without restoring bad pixels."""
    total = int(image.size)
    finite = np.isfinite(image)
    saturated = masks.get("saturated", np.zeros(image.shape, bool))
    cy, cx = center_yx
    center_inside = 0 <= cy < image.shape[0] and 0 <= cx < image.shape[1]
    center_saturated = bool(center_inside and saturated[cy, cx])
    center_nonfinite = bool(not center_inside or not finite[cy, cx])
    valid_count = int(valid_mask.sum())
    finite_count = int(finite.sum())
    if valid_count == 0:
        status = "ENTIRELY_UNUSABLE"
    elif center_saturated:
        status = "PARTIALLY_SATURATED"
    elif center_nonfinite:
        status = "PARTIALLY_INVALID_CORE"
    else:
        status = "USABLE_UNSATURATED_CORE"
    verified_science = bool(quality_verified and units_verified and variance_provenance == "MEASURED")
    capabilities = {
        "visualization": finite_count > 0,
        "background_analysis": valid_count >= 10,
        "astrometry": bool(wcs is not None and valid_count > 0),
        "aperture_photometry": bool(verified_science and valid_count > 0 and not center_saturated and not center_nonfinite),
        "difference_imaging": bool(verified_science and valid_count > 0 and wcs is not None),
    }
    return {"observation_status": status, "total_pixel_count": total,
        "finite_pixel_count": finite_count, "valid_pixel_count": valid_count,
        "finite_pixel_fraction": finite_count / total if total else 0.0,
        "valid_pixel_fraction": valid_count / total if total else 0.0,
        "saturated_pixel_count": int(saturated.sum()),
        "nonfinite_pixel_count": int((~finite).sum()),
        "center_pixel": {"inside": center_inside, "saturated": center_saturated,
                         "nonfinite": center_nonfinite, "valid": bool(center_inside and valid_mask[cy, cx])},
        "capabilities": capabilities,
        "core_values_recovered_or_fabricated": False}


def render_png_base64(
    data_arr: np.ndarray,
    stretch: str = "asinh",
    colormap: str = "plasma",
    aperture_center: Optional[Tuple[float, float]] = None,
    draw_overlays: bool = True,
    scale_factor: int = 6,
) -> str:
    """
    Renders 2D numpy array to base64 PNG with contrast stretching,
    colormap application, and photometric aperture overlays.
    """
    data = data_arr.copy()
    valid = np.isfinite(data)

    if not np.any(valid):
        blank = Image.new("RGBA", (data.shape[1] * scale_factor, data.shape[0] * scale_factor), (25, 25, 35, 255))
        draw = ImageDraw.Draw(blank)
        draw.text((10, 10), "No valid pixels", fill=(255, 100, 100, 255))
        buf = io.BytesIO()
        blank.save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"

    # Robust percentile clipping
    v_min = float(np.nanpercentile(data, 1.0))
    v_max = float(np.nanpercentile(data, 99.5))
    if v_max <= v_min:
        v_max = v_min + 1.0

    # Apply astronomical contrast stretching
    if stretch == "asinh":
        beta = (v_max - v_min) * 0.1 or 1.0
        stretched = np.arcsinh((data - v_min) / beta)
        norm_data = np.clip((stretched - np.arcsinh(0.0)) / (np.arcsinh((v_max - v_min) / beta) + 1e-6), 0.0, 1.0)
    elif stretch == "log":
        shifted = np.maximum(data - v_min + 1.0, 1e-4)
        norm_data = np.clip(np.log10(shifted) / (np.log10(v_max - v_min + 1.0) + 1e-6), 0.0, 1.0)
    elif stretch == "sqrt":
        shifted = np.maximum(data - v_min, 0.0)
        norm_data = np.clip(np.sqrt(shifted) / (np.sqrt(v_max - v_min) + 1e-6), 0.0, 1.0)
    else:  # linear
        norm_data = np.clip((data - v_min) / (v_max - v_min + 1e-6), 0.0, 1.0)

    try:
        cmap = matplotlib.colormaps.get_cmap(colormap)
    except Exception:
        cmap = matplotlib.colormaps.get_cmap("plasma")

    rgba = (cmap(norm_data) * 255).astype(np.uint8)
    # Distinct deep-slate tone for uncalibrated / saturated NaNs
    rgba[~valid] = [18, 16, 24, 255]

    img = Image.fromarray(rgba, mode="RGBA")
    h, w = data.shape
    img = img.resize((w * scale_factor, h * scale_factor), resample=Image.Resampling.NEAREST)

    if draw_overlays and aperture_center:
        tx, ty = aperture_center
        cx = tx * scale_factor
        cy = ty * scale_factor
        draw = ImageDraw.Draw(img)

        # Target aperture radius ~3 pixels
        r_ap = 3.0 * scale_factor
        draw.ellipse([cx - r_ap, cy - r_ap, cx + r_ap, cy + r_ap], outline=(56, 189, 248, 220), width=2)

        # Background annulus inner and outer radii
        r_in = 6.0 * scale_factor
        r_out = 10.0 * scale_factor
        draw.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], outline=(234, 179, 8, 150), width=1)
        draw.ellipse([cx - r_out, cy - r_out, cx + r_out, cy + r_out], outline=(234, 179, 8, 150), width=1)

        # Precision target reticle crosshairs
        ch = 4.0 * scale_factor
        draw.line([cx - ch, cy, cx + ch, cy], fill=(56, 189, 248, 255), width=1)
        draw.line([cx, cy - ch, cx, cy + ch], fill=(56, 189, 248, 255), width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"


def render_overlap_mask_base64(
    valid_footprint: np.ndarray,
    sat_mask: Optional[np.ndarray] = None,
    scale_factor: int = 6,
) -> str:
    """
    Renders the spatial overlap and valid pixel footprint mask as a color-coded PNG.
    - Green/Cyan: Valid multi-epoch registered overlap
    - Crimson Red: Excluded detector saturation / non-linear regime
    - Dark Slate: Non-overlapping / out-of-footprint boundaries
    """
    h, w = valid_footprint.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)

    # Dark background for out-of-footprint
    rgba[:] = [15, 23, 42, 255]

    # Valid overlap
    rgba[valid_footprint] = [16, 185, 129, 220]

    # Saturated mask overlay (if supplied)
    if sat_mask is not None and sat_mask.shape == (h, w):
        rgba[sat_mask] = [239, 68, 68, 240]

    img = Image.fromarray(rgba, mode="RGBA")
    img = img.resize((w * scale_factor, h * scale_factor), resample=Image.Resampling.NEAREST)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"


def generate_cutout_model(obs) -> dict:
    """
    Deprecated synthetic generator kept solely for backward compatibility.
    Production routes use load_fits_image(obs) to read genuine FITS products.
    """
    return load_fits_image(obs)
