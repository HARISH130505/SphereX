from types import SimpleNamespace

import numpy as np
from astropy.wcs import WCS

from app.services.astronomy.fits_io import classify_observation_quality, fetch_or_load_fits_file
from app.services.archive.coverage import coverage_report, position_inside_model, sedna_ephemerides
from app.services.astronomy import fits_io


def _quality(image, valid, saturated=None):
    masks = {"saturated": np.zeros(image.shape, bool) if saturated is None else saturated}
    return classify_observation_quality(image, valid, masks, True, True, "MEASURED", WCS(naxis=2), (2, 2))


def test_partially_saturated_core_preserves_surrounding_capabilities():
    image = np.ones((5, 5))
    saturated = np.zeros((5, 5), bool)
    saturated[2, 2] = True
    valid = ~saturated
    result = _quality(image, valid, saturated)
    assert result["observation_status"] == "PARTIALLY_SATURATED"
    assert result["valid_pixel_count"] == 24
    assert result["valid_pixel_fraction"] == 24 / 25
    assert result["capabilities"]["visualization"]
    assert result["capabilities"]["background_analysis"]
    assert result["capabilities"]["astrometry"]
    assert result["capabilities"]["difference_imaging"]
    assert not result["capabilities"]["aperture_photometry"]
    assert not result["core_values_recovered_or_fabricated"]


def test_fully_invalid_image_is_entirely_unusable():
    image = np.full((5, 5), np.nan)
    result = _quality(image, np.zeros((5, 5), bool))
    assert result["observation_status"] == "ENTIRELY_UNUSABLE"
    assert not any(result["capabilities"].values())


def test_nonfinite_core_is_not_inferred_to_be_saturated():
    image = np.ones((5, 5))
    image[2, 2] = np.nan
    valid = np.isfinite(image)
    result = _quality(image, valid)
    assert result["observation_status"] == "PARTIALLY_INVALID_CORE"
    assert not result["center_pixel"]["saturated"]
    assert result["valid_pixel_count"] == 24


def test_archive_422_logs_diagnostics_without_synthetic_fallback(monkeypatch, tmp_path, caplog):
    response = SimpleNamespace(status_code=422, text="Arrays do not overlap.", content=b"")
    monkeypatch.setattr(fits_io, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(fits_io.requests, "get", lambda *args, **kwargs: response)
    obs = SimpleNamespace(obs_id="A", band="SPHEREx-D1", product_id="A::SPHEREx-D1",
        cutout_url="https://archive.test/file.fits?center=1%2C2&size=0.1")
    try:
        fetch_or_load_fits_file(obs)
        assert False, "422 must not return a fabricated product"
    except FileNotFoundError as caught:
        assert "HTTP 422" in str(caught) and "Arrays do not overlap" in str(caught)


def test_horizons_parser_and_moving_position_footprint():
    result = "header\n$$SOE\n 2026-Aug-07, , , 62.330233704, 8.996637062,\n$$EOE\n"
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"result": result})
    rows = sedna_ephemerides([61259.1], request_get=lambda *args, **kwargs: response)
    assert rows[0]["ra_deg"] == 62.330233704
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [5, 5]; wcs.wcs.crval = [62.330233704, 8.996637062]
    wcs.wcs.cdelt = [-0.01, 0.01]; wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    assert position_inside_model({"wcs": wcs, "image": np.ones((10, 10))}, rows[0]["ra_deg"], rows[0]["dec_deg"])
    assert not position_inside_model({"wcs": wcs, "image": np.ones((10, 10))}, 10, 10)


def test_no_match_and_failed_query_are_distinct(monkeypatch):
    unavailable = coverage_report("Sedna", live_search=False)
    assert unavailable["status"] == "SEARCH_INCOMPLETE_OR_UNAVAILABLE"
    no_epochs = coverage_report("Sedna", live_search=True, epochs=[])
    assert no_epochs["status"] == "NO_MATCHING_RECORDS_IN_SEARCHED_CATALOG"
    field = coverage_report("Planet 9 Candidate Field")
    assert field["status"] == "HYPOTHETICAL_SEARCH_REGION"
