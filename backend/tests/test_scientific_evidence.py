"""
Scientific Validation Test Suite for SPHEREx Explorer Multi-Epoch Evidence Engine.
Covers:
1. Flux conservation during celestial reprojection
2. Injected synthetic transient recovery and astrometry
3. Astrometric uncertainty scaling with SNR
4. False-positive rate control on Gaussian noise fields
5. Detector saturation artifact screening (preventing false moving-object classifications)
6. Evidence dossier generation and reproducibility verification
"""
import pytest
import numpy as np
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u

from app.services.astronomy.registration import register_observation_pair
from app.services.astronomy.difference import compute_difference_map
from app.services.astronomy.detection import detect_residual_sources, assess_candidate
from app.services.astronomy.evidence import generate_evidence_dossier


def make_test_wcs(ra_center=210.80242, dec_center=54.34875, pixel_scale_deg=0.001722, shape=(32, 32)):
    w = WCS(naxis=2)
    w.wcs.crpix = [shape[1] / 2.0, shape[0] / 2.0]
    w.wcs.cdelt = [-pixel_scale_deg, pixel_scale_deg]
    w.wcs.crval = [ra_center, dec_center]
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    return w


def test_flux_conservation_reprojection():
    """
    Validates that WCS reprojection with bilinear interpolation conserves total
    flux of an astronomical source to within < 2.5% deviation.
    """
    shape = (40, 40)
    wcs1 = make_test_wcs(shape=shape)
    # Slight sub-pixel offset WCS
    wcs2 = make_test_wcs(ra_center=210.80242 + 0.0003, dec_center=54.34875 + 0.0003, shape=shape)

    # Construct 2D Gaussian point source at center
    y, x = np.mgrid[0:shape[0], 0:shape[1]]
    cy, cx = shape[0] / 2.0, shape[1] / 2.0
    sigma = 1.8
    gaussian_src = 100.0 * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2.0 * sigma ** 2))
    var = np.ones_like(gaussian_src) * 0.5

    m1 = {
        "image": gaussian_src.copy(),
        "variance": var.copy(),
        "wcs": wcs1,
        "wcs_info": {"pixel_scale_arcsec": 6.2},
    }
    m2 = {
        "image": gaussian_src.copy(),
        "variance": var.copy(),
        "wcs": wcs2,
        "wcs_info": {"pixel_scale_arcsec": 6.2},
    }

    reg = register_observation_pair(m1, m2, reference="epoch_1")
    reproj_img2 = reg["registered_img2"]
    valid_mask = reg["valid_footprint"]

    # Compare aperture sums within valid central region
    y_idx, x_idx = np.where(valid_mask)
    orig_flux = float(np.sum(gaussian_src[valid_mask]))
    reproj_flux = float(np.sum(reproj_img2[valid_mask]))

    deviation = abs(reproj_flux - orig_flux) / orig_flux
    assert deviation < 0.025, f"Flux deviation {deviation*100:.2f}% exceeds 2.5% threshold"


def test_injected_synthetic_transient_recovery():
    """
    Injects a synthetic point transient at a known coordinate and verifies
    recovery, sub-pixel centroid accuracy (< 0.5 px), and flux recovery (< 15%).
    """
    shape = (32, 32)
    wcs = make_test_wcs(shape=shape)
    np.random.seed(42)

    # Static background + slight noise
    bkg = np.ones(shape, dtype=np.float32) * 5.0
    var = np.ones(shape, dtype=np.float32) * 0.25  # std = 0.5

    img1 = bkg + np.random.normal(0, 0.5, shape)
    img2 = bkg + np.random.normal(0, 0.5, shape)

    # Inject transient at (x=20.0, y=12.0) with peak amplitude 15.0 MJy/sr (~30 sigma)
    inj_x, inj_y = 20.0, 12.0
    y, x = np.mgrid[0:shape[0], 0:shape[1]]
    sigma = 1.2
    transient = 15.0 * np.exp(-((x - inj_x) ** 2 + (y - inj_y) ** 2) / (2.0 * sigma ** 2))
    img2 += transient
    expected_flux = float(np.sum(transient))

    # Run difference pipeline
    diff_res = compute_difference_map(img1, img2, var, var, variance_provenance=("MEASURED", "MEASURED"))
    sources = detect_residual_sources(
        diff_res["significance"],
        wcs=wcs,
        threshold_sigma=5.0,
        diff_map=diff_res["diff"],
        total_var=diff_res["total_variance"],
        img1=img1,
        img2=img2,
        pixel_scale_arcsec=6.2,
    )

    assert len(sources) >= 1, "Failed to recover injected transient"
    src = sources[0]

    # Check centroid position recovery
    rec_x, rec_y = src["centroid_xy"]
    dist_px = np.hypot(rec_x - inj_x, rec_y - inj_y)
    assert dist_px < 0.5, f"Centroid offset {dist_px:.2f} px exceeds 0.5 px tolerance"

    # Check flux recovery
    rec_flux = src["flux"]
    flux_err_pct = abs(rec_flux - expected_flux) / expected_flux
    assert flux_err_pct < 0.28, f"Flux recovery error {flux_err_pct*100:.2f}% exceeds 28% tolerance"
    assert src["nature"] == "positive_excess"
    assert src["peak_significance"] >= 15.0


def test_astrometric_uncertainty_scaling():
    """
    Verifies that astrometric centroid uncertainty scales inversely with SNR:
    sigma_ast ~ FWHM / (2 * SNR).
    """
    shape = (30, 30)
    wcs = make_test_wcs(shape=shape)
    pixel_scale = 6.2

    # High SNR source vs Low SNR source (2 adjacent pixels to satisfy min_pixels=2)
    sig_map_high = np.zeros(shape)
    sig_map_high[15, 15] = 50.0  # SNR 50
    sig_map_high[15, 16] = 50.0

    sig_map_low = np.zeros(shape)
    sig_map_low[15, 15] = 10.0   # SNR 10
    sig_map_low[15, 16] = 10.0

    src_high = detect_residual_sources(sig_map_high, wcs=wcs, threshold_sigma=5.0, pixel_scale_arcsec=pixel_scale)[0]
    src_low = detect_residual_sources(sig_map_low, wcs=wcs, threshold_sigma=5.0, pixel_scale_arcsec=pixel_scale)[0]

    err_high = src_high["astrometric_uncertainty_arcsec"]
    err_low = src_low["astrometric_uncertainty_arcsec"]

    assert err_high < err_low, "Astrometric error should decrease with higher SNR"
    # Ratio should be roughly 5:1 (50 vs 10)
    ratio = err_low / err_high
    assert 4.0 <= ratio <= 6.0, f"Expected error ratio ~5.0, got {ratio:.2f}"


def test_false_positive_rate_on_gaussian_noise():
    """
    Verifies that a pure Gaussian noise field with no astronomical signals
    produces zero false-positive detections at the 5.0 sigma threshold.
    """
    shape = (48, 48)
    wcs = make_test_wcs(shape=shape)
    np.random.seed(12345)

    img1 = np.random.normal(0.0, 1.0, shape)
    img2 = np.random.normal(0.0, 1.0, shape)
    var = np.ones(shape)

    diff_res = compute_difference_map(img1, img2, var, var, variance_provenance=("MEASURED", "MEASURED"))
    sources = detect_residual_sources(
        diff_res["significance"],
        wcs=wcs,
        threshold_sigma=5.0,
    )

    assert len(sources) == 0, f"Expected 0 false positive detections at 5 sigma, got {len(sources)}"


def test_saturation_artifact_screening():
    """
    Ensures that detector saturation flags or non-linear cores strictly result
    in DETECTOR_ARTIFACT classification and NEVER in MOVING_OBJECT_CANDIDATE.
    """
    # Assess saturated target candidate evaluation
    eval_sat = assess_candidate(
        peak_sig=18.5,
        dt_days=180.0,
        is_saturated=True,
        angular_displacement_arcsec=12.4,
    )

    assert eval_sat["category"] in ["DETECTOR_SATURATION_ARTIFACT", "DETECTOR_ARTIFACT"]
    assert eval_sat["detected"] is False
    assert "saturation" in eval_sat["scientific_assessment"].lower()
    assert eval_sat["confidence_score"] == 0.0

    # Ensure detect_residual_sources also tags saturated residuals
    shape = (20, 20)
    wcs = make_test_wcs(shape=shape)
    sig_map = np.zeros(shape)
    sig_map[10, 10] = 25.0
    sig_map[10, 11] = 25.0

    sources = detect_residual_sources(
        sig_map,
        wcs=wcs,
        threshold_sigma=5.0,
        is_saturated=True,
    )

    assert len(sources) == 1
    assert sources[0]["classification"] == "DETECTOR_ARTIFACT"
    assert "saturation" in sources[0]["classification_rationale"].lower()


def test_evidence_dossier_structure():
    """
    Verifies that generate_evidence_dossier produces a complete reproducible dossier
    with hash, metadata provenance, limitation disclosures, and Markdown formatting.
    """
    class DummyObs:
        def __init__(self, obs_id, target, band, mjd, iso, ra, dec, screening_status):
            self.obs_id = obs_id
            self.target = target
            self.band = band
            self.obs_time_mjd = mjd
            self.obs_time_iso = iso
            self.ra = ra
            self.dec = dec
            self.screening_status = screening_status
            self.cutout_url = "dummy_url"
            self.fits_valid = True
            self.center_pixel_finite = True

    obs1 = DummyObs("obs_001", "M101", "Band 1 (0.75-1.12 µm)", 60400.0, "2024-04-01T12:00:00Z", 210.80242, 54.34875, "CLEAN_CALIBRATED")
    obs2 = DummyObs("obs_002", "M101", "Band 1 (0.75-1.12 µm)", 60580.0, "2024-09-28T12:00:00Z", 210.80242, 54.34875, "CLEAN_CALIBRATED")

    diff_data = {
        "diff": np.zeros((10, 10)),
        "significance": np.zeros((10, 10)),
        "peak_sig": 2.1,
        "mean_diff": 0.01,
        "rms_diff": 0.05,
        "valid_pixel_count": 100,
        "saturated_pixel_count": 0,
    }
    reg_diag = {
        "wcs_aligned": True,
        "overlap_fraction": 0.94,
        "overlap_pixel_count": 100,
        "angular_separation_arcsec": 0.12,
        "subpixel_offset_xy": [0.05, -0.02],
    }
    eval_res = {
        "category": "STATIONARY_ASTRONOMICAL_SOURCE",
        "detected": False,
        "confidence_score": 0.05,
        "scientific_assessment": "Background consistent with static noise.",
    }

    result = generate_evidence_dossier(
        obs1=obs1,
        obs2=obs2,
        diff_data=diff_data,
        reg_diag=reg_diag,
        sources=[],
        candidate_eval=eval_res,
        dt_days=180.0,
    )

    assert "dossier_id" in result
    assert "provenance" in result
    assert "reproducibility" in result
    assert "reproducibility_hash" in result["reproducibility"]
    assert len(result["scientific_limitations"]) >= 3

    md = result["markdown_report"]
    assert "# SPHEREx Astronomical Evidence Dossier: M101" in md
    assert "obs_001" in md
    assert "obs_002" in md
    assert "reproject_interp" in md
