"""
Astronomical Image Registration on a Common Celestial Reference Grid.
Performs WCS-based reprojection, sub-pixel interpolation, valid footprint
masking, and registration quality diagnostics.
"""
from typing import Dict, Any, Tuple, Optional
import numpy as np
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
from app.services.astronomy.resampling import native_valid_mask, propagate_bilinear
from astropy.coordinates import SkyCoord
import astropy.units as u

try:
    from reproject import reproject_interp
    HAS_REPROJECT = True
except ImportError:
    HAS_REPROJECT = False


WCS_ROUNDTRIP_TOLERANCE_PIXEL = 1e-3

def register_arrays(arr1: np.ndarray, arr2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Legacy array dimension adjustment (truncation fallback).
    NOTE: Slicing arrays to min dimensions is NOT astronomical image registration!
    Use register_observation_pair for genuine WCS celestial reprojection.
    """
    h = min(arr1.shape[0], arr2.shape[0])
    w = min(arr1.shape[1], arr2.shape[1])
    return arr1[:h, :w], arr2[:h, :w]


def celestial_wcs_error(model):
    """Numerical WCS sanity check on center/corners; does not calibrate astrometry."""
    image, wcs = np.asarray(model["image"]), model.get("wcs")
    if image.ndim != 2 or min(image.shape) < 2:
        return "Science image must be a nonempty two-dimensional grid."
    try:
        if not isinstance(wcs, WCS) or not wcs.has_celestial:
            return "Missing celestial WCS."
        celestial = wcs.celestial
        scales = proj_plane_pixel_scales(celestial)
        determinant = np.linalg.det(celestial.pixel_scale_matrix)
        if not np.all(np.isfinite(scales)) or np.any(scales <= 0) or not np.isfinite(determinant) or determinant == 0:
            return "Nonfinite or singular celestial pixel transform."
        h, w = image.shape
        x = np.array([0, w-1, 0, w-1, (w-1)/2])
        y = np.array([0, 0, h-1, h-1, (h-1)/2])
        sky = celestial.pixel_to_world(x, y)
        bx, by = celestial.world_to_pixel(sky)
        if (not np.all(np.isfinite(sky.ra.deg)) or not np.all(np.isfinite(sky.dec.deg)) or
                not np.all(np.isfinite(bx)) or not np.all(np.isfinite(by)) or
                np.max(np.hypot(bx-x, by-y)) > WCS_ROUNDTRIP_TOLERANCE_PIXEL):
            return "Celestial WCS fails finite center/corner round-trip check (0.001 pixel)."
    except Exception as exc:
        return f"Invalid celestial WCS: {exc}"
    return None


def register_observation_pair(m1: Dict[str, Any], m2: Dict[str, Any],
                              reference: str = "epoch_1") -> Dict[str, Any]:
    """Reproject onto epoch 1; fallback arrays carry ZERO celestial overlap.

    overlap_fraction is unrounded usable pixel count / full reference grid size.
    Cropping is retained only for legacy visual consumers and never establishes
    scientific registration. The API shows original frames for visual fallbacks.
    """
    if reference != "epoch_1":
        raise ValueError("Only epoch_1 is supported as a reference grid")
    img1, img2 = np.asarray(m1["image"]), np.asarray(m2["image"])
    var1, var2 = np.asarray(m1["variance"]), np.asarray(m2["variance"])
    wcs1, wcs2 = m1.get("wcs"), m2.get("wcs")
    diagnostics = {"reference_grid": reference, "reference_shape": list(img1.shape),
                   "source_shape": list(img2.shape), "wcs_aligned": False,
                   "method": "dimension_slice_fallback", "overlap_pixel_count": 0,
                   "overlap_fraction": 0.0, "geometric_overlap_fraction": None,
                   "registration_status": "NON_SCIENTIFIC_VISUAL_COMPARISON",
                   "failure_reasons": [], "angular_separation_arcsec": None,
                   "subpixel_offset_xy": None}
    info1, info2 = m1.get("wcs_info", {}), m2.get("wcs_info", {})
    try:
        c1 = SkyCoord(info1["ra_center"] * u.deg, info1["dec_center"] * u.deg)
        c2 = SkyCoord(info2["ra_center"] * u.deg, info2["dec_center"] * u.deg)
        sep = float(c1.separation(c2).arcsec)
        if np.isfinite(sep):
            diagnostics["angular_separation_arcsec"] = sep
    except (KeyError, ValueError, TypeError):
        pass
    errors = [f"Epoch {i}: {error}" for i, model in enumerate((m1, m2), 1)
              if (error := celestial_wcs_error(model))]
    if not HAS_REPROJECT:
        errors.append("The reproject dependency is unavailable.")
    if var1.shape != img1.shape or var2.shape != img2.shape:
        errors.append("Variance grids must match their science image grids.")
    if not errors:
        try:
            reproj_img2, footprint = reproject_interp((img2, wcs2.celestial), wcs1.celestial,
                shape_out=img1.shape, order="bilinear")
            propagation = propagate_bilinear(m2, wcs1, img1.shape)
            reproj_var2 = propagation["variance"]
            if reproj_img2.shape != img1.shape or reproj_var2.shape != img1.shape:
                raise ValueError("Reprojection returned an unexpected output shape")
            geometry = propagation["geometric_mask"]
            valid = (geometry & np.isfinite(footprint) & (footprint > 0.5) &
                     native_valid_mask(m1) & propagation["valid_mask"] & np.isfinite(reproj_img2))
            reproj_img2 = np.where(propagation["valid_mask"], reproj_img2, np.nan)
            # Preserve this pointing diagnostic for display only; no source measurement uses it.
            try:
                target = m1.get("target_xy", [(img1.shape[1]-1)/2, (img1.shape[0]-1)/2])
                px, py = wcs1.celestial.all_world2pix(info2["ra_center"], info2["dec_center"], 0)
                offset = [float(px-target[0]), float(py-target[1])]
                if np.all(np.isfinite(offset)):
                    diagnostics["subpixel_offset_xy"] = offset
            except (KeyError, ValueError, TypeError):
                pass
            diagnostics.update(wcs_aligned=True, method="wcs_reprojection_bilinear",
                registration_status="WCS_REPROJECTED", overlap_pixel_count=int(valid.sum()),
                overlap_fraction=float(valid.sum()/img1.size),
                geometric_overlap_fraction=float(geometry.sum()/img1.size),
                reproject_package="astropy_reproject",
                variance_resampling="bilinear_squared_weights_independent_input_pixels",
                mask_resampling="OR_all_nonzero_bilinear_contributors",
                output_pixel_covariance_modeled=False,
                variance_provenance=[m1.get("variance_provenance", "UNVERIFIED"), m2.get("variance_provenance", "UNVERIFIED")],
                quality_mask_counts={"epoch_1": {name: int(mask.sum()) for name, mask in m1.get("quality_masks", {}).items()},
                                     "epoch_2_on_reference": {name: int(mask.sum()) for name, mask in propagation["masks"].items()}})
            return {"registered_img1": np.where(native_valid_mask(m1), img1, np.nan), "registered_var1": var1.copy(),
                    "registered_img2": reproj_img2,
                    "registered_var2": reproj_var2,
                    "registered_flags1": m1.get("flags_uint64"), "registered_flags2": propagation["flags"],
                    "registered_masks1": m1.get("quality_masks", {}), "registered_masks2": propagation["masks"],
                    "valid_footprint": valid, "diagnostics": diagnostics}
        except Exception as exc:
            errors.append(f"Celestial reprojection failed: {exc}")
            diagnostics["wcs_reprojection_error"] = str(exc)
    diagnostics["failure_reasons"] = errors
    diagnostics["warning"] = "; ".join(errors) + " Visual arrays only; no celestial registration or overlap is established."
    c_img1, c_img2 = register_arrays(img1, img2)
    h, w = c_img1.shape
    # Unavailable variance is represented by NaNs for visual-only compatibility.
    if var1.shape != img1.shape:
        var1 = np.full(img1.shape, np.nan)
    if var2.shape != img2.shape:
        var2 = np.full(img2.shape, np.nan)
    return {"registered_img1": c_img1.copy(), "registered_var1": var1[:h, :w].copy(),
            "registered_img2": c_img2.copy(), "registered_var2": var2[:h, :w].copy(),
            "valid_footprint": np.zeros((h, w), dtype=bool), "diagnostics": diagnostics}
