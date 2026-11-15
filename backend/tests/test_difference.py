"""
Unit and scientific validation tests for differential imaging and variance propagation.
Verifies:
    D = I2 - I1
    Var(D) = Var(I1) + Var(I2)
    S = D / sqrt(Var(D))
"""
import numpy as np
import pytest
from app.services.astronomy.difference import compute_difference_map


def test_variance_propagation_independent_exposures():
    """Verify exact variance propagation: Var(D) = Var(I1) + Var(I2)."""
    img1 = np.full((10, 10), 12.0, dtype=np.float32)
    img2 = np.full((10, 10), 18.0, dtype=np.float32)
    var1 = np.full((10, 10), 2.0, dtype=np.float32)
    var2 = np.full((10, 10), 3.0, dtype=np.float32)

    res = compute_difference_map(img1, img2, var1, var2, variance_provenance=("MEASURED", "MEASURED"))

    # D = 18 - 12 = 6.0
    assert np.allclose(res["diff"], 6.0)

    # Var(D) = 2.0 + 3.0 = 5.0
    assert np.allclose(res["total_variance"], 5.0)

    # S = 6.0 / sqrt(5.0) ~ 2.68328
    expected_sig = 6.0 / np.sqrt(5.0)
    assert np.allclose(res["significance"], expected_sig, atol=1e-4)
    assert abs(res["peak_sig"] - expected_sig) < 1e-3
    assert res["variance_propagation_verified"] is True


def test_difference_masking_nans_and_saturation():
    """Verify that NaNs, infs, and saturated pixels (>3000 MJy/sr) are excluded from S/N."""
    img1 = np.full((20, 20), 5.0, dtype=np.float32)
    img2 = np.full((20, 20), 8.0, dtype=np.float32)
    var1 = np.full((20, 20), 0.5, dtype=np.float32)
    var2 = np.full((20, 20), 0.5, dtype=np.float32)

    # Inject NaN in center
    img1[10, 10] = np.nan
    # Inject saturation overflow in corner
    img2[0, 0] = 5500.0

    res = compute_difference_map(img1, img2, var1, var2, saturation_threshold_mjy_sr=3000.0, variance_provenance=("MEASURED", "MEASURED"))

    # NaN pixel must be masked
    assert np.isnan(res["diff"][10, 10])
    assert np.isnan(res["significance"][10, 10])

    # Saturated pixel must be masked
    assert np.isnan(res["diff"][0, 0])
    assert np.isnan(res["significance"][0, 0])

    # Nonfinite and brightness-screened pixels are not physical saturation flags.
    assert res["saturated_pixel_count"] == 0
    assert res["brightness_threshold_pixel_count"] == 1
    assert res["nonfinite_image_pixel_count"] == 1
    # Clean pixels evaluate to D = 3.0, S = 3.0 / sqrt(1.0) = 3.0
    assert res["peak_sig"] == 3.0


def test_difference_footprint_masking():
    """Verify that pixels outside valid footprint are masked."""
    img1 = np.ones((15, 15), dtype=np.float32)
    img2 = np.ones((15, 15), dtype=np.float32) * 4.0
    var1 = np.ones((15, 15), dtype=np.float32)
    var2 = np.ones((15, 15), dtype=np.float32)

    # Footprint valid only in inner 5x5
    footprint = np.zeros((15, 15), dtype=bool)
    footprint[5:10, 5:10] = True

    res = compute_difference_map(img1, img2, var1, var2, valid_mask=footprint, variance_provenance=("MEASURED", "MEASURED"))
    assert res["valid_pixel_count"] == 25
    assert np.isnan(res["diff"][0, 0])
    assert np.allclose(res["diff"][5:10, 5:10], 3.0)
