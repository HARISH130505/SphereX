"""
Comprehensive unit tests for genuine SPHEREx FITS retrieval, parsing,
variable dimensions, WCS extraction, NaN preservation, and error handling.
"""
import pytest
import numpy as np
from app.services.storage.repository import repository
from app.services.astronomy.fits_io import load_fits_image, render_png_base64


def test_render_png_base64_valid():
    """Verify PNG rasterization with contrast stretches."""
    data = np.ones((59, 58), dtype=np.float32) * 5.0
    for stretch in ["asinh", "log", "sqrt", "linear"]:
        png = render_png_base64(data, stretch=stretch, colormap="plasma")
        assert png.startswith("data:image/png;base64,")


def test_render_nan_fallback():
    """Verify all-NaN array renders safely with warning watermark."""
    data = np.full((59, 58), np.nan, dtype=np.float32)
    png = render_png_base64(data, stretch="asinh")
    assert png.startswith("data:image/png;base64,")


def test_genuine_fits_loading_m101():
    """Verify genuine FITS loading for clean target M101."""
    obs = repository.get_by_id("TAP_M101_136")
    assert obs is not None

    model = load_fits_image(obs)
    assert model["shape"] == [59, 58]
    assert model["nan_count"] == 0
    assert model["valid_pct"] == 100.0
    assert model["min_val"] < 0  # True background noise has slight negative values
    assert model["max_val"] > 10.0  # Galaxy core flux
    assert "source_file" in model and "TAP_M101_136" in model["source_file"]
    assert "wcs_info" in model
    assert "ra_center" in model["wcs_info"]


def test_genuine_fits_loading_mira_variable_dimension():
    """Verify genuine FITS loading for Mira red giant: shape (44, 58) and true NaNs."""
    obs = repository.get_by_id("2026W32_2A_0147_1::SPHEREx-D1")
    assert obs is not None

    model = load_fits_image(obs)
    # Crucial test: Mira D1 is 44 x 58, NOT 59 x 58
    assert model["shape"] == [44, 58]
    # Saturated core has genuine detector NaNs from SUR overflow
    assert model["nan_count"] == 12
    assert model["valid_pct"] > 99.0
    # Halo flux reaches thousands of MJy/sr
    assert model["max_val"] > 3000.0


def test_genuine_fits_loading_delta_cephei():
    """Verify genuine FITS loading for Delta Cephei Cepheid variable."""
    obs = repository.get_by_id("2026W32_1A_0147_1::SPHEREx-D1")
    assert obs is not None

    model = load_fits_image(obs)
    assert model["shape"] == [59, 58]
    assert model["nan_count"] == 30
    assert model["max_val"] > 4000.0


def test_genuine_fits_loading_algol():
    """Verify genuine FITS loading for Algol eclipsing binary."""
    obs = repository.get_by_id("2026W33_1A_0574_2::SPHEREx-D1")
    assert obs is not None

    model = load_fits_image(obs)
    assert model["shape"] == [59, 58]
    assert model["nan_count"] == 47
    assert model["max_val"] > 5000.0


def test_historical_failed_download_can_recover_only_from_genuine_fits():
    """A stale failure label cannot permanently block a now-available archive product."""
    obs = repository.get_by_id("TAP_M101_057")
    assert obs is not None
    assert obs.screening_status == "FAILED_DOWNLOAD"

    model = load_fits_image(obs)
    assert model["fits_provenance"]["status"] == "AVAILABLE"
    assert model["fits_provenance"]["byte_count"] > 1000
    assert model["source_file"].endswith(".fits")
