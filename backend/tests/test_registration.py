"""
Unit and scientific validation tests for astronomical image registration.
Tests WCS celestial reprojection, valid footprint overlap, and fallback handling.
"""
import numpy as np
import pytest
from app.services.storage.repository import repository
from app.services.astronomy.fits_io import load_fits_image
from app.services.astronomy.registration import register_arrays, register_observation_pair


def test_register_arrays_legacy():
    """Verify legacy dimension-matching function preserves array shapes."""
    a = np.zeros((59, 58))
    b = np.ones((60, 58))
    reg_a, reg_b = register_arrays(a, b)
    assert reg_a.shape == (59, 58)
    assert reg_b.shape == (59, 58)


def test_wcs_reprojection_registration_real_data():
    """Verify genuine WCS reprojection on two independent M101 survey epochs."""
    obs1 = repository.get_by_id("TAP_M101_002")
    obs2 = repository.get_by_id("TAP_M101_221")
    assert obs1 is not None and obs2 is not None

    m1 = load_fits_image(obs1)
    m2 = load_fits_image(obs2)
    assert m1.get("wcs") is not None and m2.get("wcs") is not None

    reg = register_observation_pair(m1, m2, reference="epoch_1")

    # Assert shape alignment
    assert reg["registered_img1"].shape == m1["image"].shape
    assert reg["registered_img2"].shape == m1["image"].shape
    assert reg["registered_var2"].shape == m1["variance"].shape

    # Assert genuine WCS reprojection metrics
    diag = reg["diagnostics"]
    assert diag["wcs_aligned"] is True
    assert diag["method"] == "wcs_reprojection_bilinear"
    assert diag["overlap_pixel_count"] > 2500
    assert diag["overlap_fraction"] > 0.70
    assert "angular_separation_arcsec" in diag
    assert "subpixel_offset_xy" in diag

    # Assert valid footprint mask
    footprint = reg["valid_footprint"]
    assert footprint.dtype == bool
    assert np.sum(footprint) == diag["overlap_pixel_count"]


def test_registration_fallback_without_wcs():
    """Verify safe fallback and diagnostic warning when WCS is absent."""
    m1 = {
        "image": np.ones((30, 25), dtype=np.float32),
        "variance": np.full((30, 25), 0.01, dtype=np.float32),
        "wcs": None,
        "wcs_info": {},
    }
    m2 = {
        "image": np.ones((35, 20), dtype=np.float32),
        "variance": np.full((35, 20), 0.02, dtype=np.float32),
        "wcs": None,
        "wcs_info": {},
    }

    reg = register_observation_pair(m1, m2)
    assert reg["registered_img1"].shape == (30, 20)
    assert reg["registered_img2"].shape == (30, 20)
    assert reg["diagnostics"]["wcs_aligned"] is False
    assert "warning" in reg["diagnostics"]
