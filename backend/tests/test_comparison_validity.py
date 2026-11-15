"""Comparison guard tests: real FITS for HTTP integration; synthetic WCS for boundaries."""
from copy import deepcopy
import numpy as np
import pytest
from astropy.wcs import WCS
from fastapi.testclient import TestClient
from app.main import app
from app.services.storage.repository import repository
from app.services.astronomy.fits_io import load_fits_image
from app.services.astronomy import registration
from app.services.astronomy.comparison_validity import evaluate_comparison_validity
from app.services.astronomy.difference import compute_difference_map
from app.api.routes import comparisons


def real_pair():
    observations = [repository.get_by_id(key) for key in ("TAP_M101_002", "TAP_M101_221")]
    return observations, [load_fits_image(obs) for obs in observations]


def block_science(monkeypatch):
    for name in ("compute_difference_map", "detect_residual_sources", "investigate_epoch_motion", "assess_candidate"):
        monkeypatch.setattr(comparisons, name, lambda *a, **k: pytest.fail("Invalid comparison invoked scientific analysis"))


def post_pair(client, pair):
    return client.post("/api/epoch/compare", json={
        "epoch_1_product_id": pair[0].product_id, "epoch_2_product_id": pair[1].product_id})


@pytest.mark.parametrize("failure,code", [("target", "TARGET_MISMATCH"), ("same", "SAME_PRODUCT"),
    ("band", "INCOMPATIBLE_BANDS"), ("epoch", "INVALID_EPOCH_BASELINE")])
def test_invalid_metadata_rejected_before_fits_access(monkeypatch, failure, code):
    first = repository.get_by_id("TAP_M101_002")
    second = repository.get_by_id("TAP_M101_221").model_copy()
    if failure == "target": second.target = "Mira"
    if failure == "same": second = first
    if failure == "band": second.band = "SPHEREx-D4"
    if failure == "epoch": second.obs_time_mjd = first.obs_time_mjd
    pair = [first, second]
    monkeypatch.setattr(comparisons.repository, "get_by_id", lambda key: first if key == first.product_id else second)
    monkeypatch.setattr(comparisons, "load_fits_image", lambda *a: pytest.fail("Invalid metadata reached FITS loading"))
    block_science(monkeypatch)
    with TestClient(app) as client:
        response = post_pair(client, pair)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "INVALID_COMPARISON"
    assert not detail["scientific_analysis_allowed"]
    assert code in {reason["code"] for reason in detail["failure_reasons"]}


@pytest.mark.parametrize("failure", ["missing_wcs", "noncelestial_wcs", "singular_wcs", "failed_reprojection", "missing_dependency", "no_overlap", "low_overlap"])
def test_invalid_registration_is_visual_only_and_never_runs_science(monkeypatch, failure):
    pair, models = real_pair()
    models = deepcopy(models)
    if failure == "missing_wcs": models[1]["wcs"] = None
    if failure == "noncelestial_wcs": models[1]["wcs"] = WCS(naxis=2)
    if failure == "singular_wcs": models[1]["wcs"].wcs.cdelt[0] = 0
    if failure == "failed_reprojection":
        def broken(*args, **kwargs): raise RuntimeError("injected reprojection failure")
        monkeypatch.setattr(registration, "reproject_interp", broken)
    if failure == "missing_dependency": monkeypatch.setattr(registration, "HAS_REPROJECT", False)
    if failure == "no_overlap": models[1]["wcs"].wcs.crval[0] += 10
    if failure == "low_overlap": models[1]["image"][:, :40] = np.nan
    monkeypatch.setattr(comparisons, "load_fits_image", lambda obs: models[0] if obs.product_id == pair[0].product_id else models[1])
    block_science(monkeypatch)
    with TestClient(app) as client:
        response = post_pair(client, pair)
    assert response.status_code == 200, response.text[:300]
    data = response.json()
    validity = data["comparison_validity"]
    assert validity["status"] == "NON_SCIENTIFIC_VISUAL_COMPARISON"
    assert not validity["scientific_analysis_allowed"] and validity["failure_reasons"]
    assert data["difference_image_base64"] is None
    assert data["significance_image_base64"] is None
    assert data["flux_ratio"] is None and data["transient_score"] is None
    assert data["difference_statistics"] is None
    assert data["candidate_assessment"]["peak_sig"] is None
    assert data["candidate_assessment"]["category"] == "INSUFFICIENT_EVIDENCE"
    assert data["motion_vector_arcsec"] is None and not data["motion_detected"]
    assert data["detected_sources"] == []
    assert data["motion_analysis"]["associations"] == []
    assert data["evidence_dossier"]["comparison_validity"] == validity
    assert validity["status"] in data["evidence_report_markdown"]
    assert data["epoch_1_original_image_base64"] == data["epoch_1_image_base64"]
    if failure not in {"no_overlap", "low_overlap"}:
        assert data["registration_diagnostics"]["overlap_fraction"] == 0
        assert not data["registration_diagnostics"]["wcs_aligned"]


def test_real_registered_comparison_has_explicit_validity():
    pair, _ = real_pair()
    with TestClient(app) as client:
        response = post_pair(client, pair)
    assert response.status_code == 200
    data = response.json()
    validity = data["comparison_validity"]
    assert validity["scientific_analysis_allowed"]
    assert validity["status"] == "VALID_FOR_REGISTERED_COMPARISON"
    assert validity["overlap_fraction"] >= validity["min_overlap_fraction"]
    assert data["difference_image_base64"] and data["significance_image_base64"]
    assert data["evidence_dossier"]["comparison_validity"] == validity
    assert validity["status"] in data["evidence_report_markdown"]


def test_overlap_threshold_boundary_is_unrounded_and_configurable():
    """SIMULATION of valid pixel coverage, not real survey overlap calibration."""
    pair, models = real_pair()
    reg = registration.register_observation_pair(*models)
    reg["diagnostics"]["overlap_fraction"] = 0.49999
    assert not evaluate_comparison_validity(*pair, *models, reg, 0.5)["scientific_analysis_allowed"]
    assert evaluate_comparison_validity(*pair, *models, reg, 0.49)["scientific_analysis_allowed"]
    reg["diagnostics"]["overlap_fraction"] = 0.5
    assert evaluate_comparison_validity(*pair, *models, reg, 0.5)["scientific_analysis_allowed"]
    reg["diagnostics"]["overlap_fraction"] = np.nan
    assert not evaluate_comparison_validity(*pair, *models, reg, 0.5)["scientific_analysis_allowed"]


def test_cropping_does_not_create_celestial_overlap():
    a = {"image": np.ones((30, 25)), "variance": np.ones((30, 25)), "wcs": None}
    b = {"image": np.ones((35, 20)), "variance": np.ones((35, 20)), "wcs": None}
    result = registration.register_observation_pair(a, b)
    assert result["registered_img1"].shape == (30, 20)
    assert not result["valid_footprint"].any()
    assert result["diagnostics"]["overlap_pixel_count"] == 0
    assert result["diagnostics"]["registration_status"] == "NON_SCIENTIFIC_VISUAL_COMPARISON"


def test_difference_grid_mismatch_cannot_silently_crop():
    with pytest.raises(ValueError, match="matching registered"):
        compute_difference_map(np.ones((3, 3)), np.ones((4, 3)), np.ones((3, 3)), np.ones((4, 3)))


def test_invalid_variance_is_excluded_from_registration_overlap():
    _, models = real_pair()
    models[1]["variance"][:] = -1
    result = registration.register_observation_pair(*models)
    assert result["diagnostics"]["wcs_aligned"]
    assert not result["valid_footprint"].any()
    assert result["diagnostics"]["overlap_fraction"] == 0
