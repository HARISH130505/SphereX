"""Bilinear stencil propagation of independent variances and detector masks."""
import numpy as np
from astropy.wcs.utils import pixel_to_pixel


INTEGER_SNAP_TOLERANCE_PIXEL = 1e-7

def native_valid_mask(model):
    image = np.asarray(model["image"])
    variance = np.asarray(model["variance"])
    if variance.shape != image.shape:
        return np.zeros(image.shape, dtype=bool)
    valid = np.isfinite(image) & np.isfinite(variance) & (variance > 0)
    if model.get("valid_mask") is not None:
        valid &= np.asarray(model["valid_mask"], dtype=bool)
    return valid


def propagate_bilinear(model, reference_wcs, output_shape):
    """No renormalization around invalid pixels; any contributing bad pixel vetoes.

    Coordinates within 1e-7 pixel of an integer are snapped to suppress numerical
    WCS round-trip noise. Variance is sum(weight**2 * variance); flags are bitwise
    OR and each named boolean state is OR across nonzero-weight contributors.
    Adjacent output covariance is not captured by the returned diagonal variance.
    """
    yy, xx = np.indices(output_shape, dtype=float)
    sx, sy = pixel_to_pixel(reference_wcs.celestial, model["wcs"].celestial, xx, yy)
    finite = np.isfinite(sx) & np.isfinite(sy)
    sx, sy = np.where(finite, sx, -100), np.where(finite, sy, -100)
    sx = np.where(np.abs(sx-np.rint(sx)) < INTEGER_SNAP_TOLERANCE_PIXEL, np.rint(sx), sx)
    sy = np.where(np.abs(sy-np.rint(sy)) < INTEGER_SNAP_TOLERANCE_PIXEL, np.rint(sy), sy)
    x0, y0 = np.floor(sx).astype(int), np.floor(sy).astype(int)
    fx, fy = sx-x0, sy-y0
    variance = np.asarray(model["variance"], dtype=float)
    native_valid = native_valid_mask(model)
    masks = {name: np.asarray(mask, dtype=bool) for name, mask in model.get("quality_masks", {}).items()}
    masks["invalid_variance"] = ~np.isfinite(variance) | (variance <= 0)
    flags = np.asarray(model.get("flags_uint64", np.zeros(variance.shape, np.uint64)), dtype=np.uint64)
    output_masks = {name: np.zeros(output_shape, bool) for name in masks}
    output_flags = np.zeros(output_shape, np.uint64)
    output_variance = np.zeros(output_shape, float)
    valid, geometry = finite.copy(), finite.copy()
    h, w = variance.shape
    for dx, dy, weight in ((0,0,(1-fx)*(1-fy)), (1,0,fx*(1-fy)), (0,1,(1-fx)*fy), (1,1,fx*fy)):
        x, y = x0+dx, y0+dy
        active = finite & (weight > 0)
        inside = (x >= 0) & (x < w) & (y >= 0) & (y < h)
        geometry &= ~active | inside
        ix, iy = np.clip(x, 0, w-1), np.clip(y, 0, h-1)
        valid &= ~active | (inside & native_valid[iy, ix])
        take = active & inside
        safe_variance = np.where(np.isfinite(variance[iy, ix]) & (variance[iy, ix] > 0), variance[iy, ix], 0)
        output_variance += np.where(take, weight**2 * safe_variance, 0)
        output_flags |= np.where(take, flags[iy, ix], np.uint64(0))
        for name, mask in masks.items():
            output_masks[name] |= take & mask[iy, ix]
    valid &= geometry & np.isfinite(output_variance) & (output_variance > 0)
    return {"variance": np.where(valid, output_variance, np.nan), "valid_mask": valid,
            "geometric_mask": geometry, "flags": output_flags, "masks": output_masks}
