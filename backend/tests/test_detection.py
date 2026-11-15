"""
Unit and scientific validation tests for source detection, candidate assessment,
and strict separation from detector telemetry flags.
"""
import numpy as np
import pytest
from app.services.astronomy.detection import (
    compute_reflex_parallax,
    estimate_apparent_distance_from_motion,
    detect_residual_sources,
    cross_epoch_positional_match,
    evaluate_variability,
    assess_candidate,
    evaluate_transient_candidate,
)


def test_reflex_parallax_sedna_and_planet9():
    """Verify 6-month Earth reflex parallax calculations for outer solar system probes."""
    # Sedna at ~84 AU: theta_reflex = 2 AU * 206265 / 84 AU ~ 4911 arcsec (overall baseline)
    p_sedna = compute_reflex_parallax(84.0, baseline_au=2.0)
    assert round(p_sedna, 1) == 4911.1

    # Planet 9 candidate at ~400 AU:
    p_p9 = compute_reflex_parallax(400.0, baseline_au=2.0)
    assert round(p_p9, 1) == 1031.3

    # Reverse distance estimation
    est_dist = estimate_apparent_distance_from_motion(delta_arcsec=1031.3, dt_days=182.6)
    assert est_dist is not None
    assert abs(est_dist - 400.0) < 2.0


def test_detector_saturation_not_misidentified_as_candidate():
    """Verify detector saturation / SUR overflow flags are NEVER classified as Planet 9 or moving objects."""
    # Saturated target (e.g. Mira, Algol) with high residual significance from masked core
    cand = assess_candidate(
        peak_sig=45.0,
        dt_days=180.0,
        is_saturated=True,
        angular_displacement_arcsec=15.0,
    )

    assert cand["detected"] is False
    assert cand["category"] == "DETECTOR_ARTIFACT"
    assert cand["proper_motion_arcsec_per_yr"] is None
    assert "detector saturation" in cand["scientific_assessment"].lower()
    assert "cannot be interpreted as an astronomical transient" in cand["scientific_assessment"].lower()


def test_stationary_flux_transient_vs_moving_candidate():
    """Regression: scalar offsets cannot distinguish a variable from a mover.

    Previous expectations encoded the scientific defect. Measured stationary,
    variable, and moving associations are tested in test_source_matching.py.
    """
    for separation in (0.8, 12.4):
        candidate = assess_candidate(peak_sig=9.2, dt_days=180.0,
                                     angular_displacement_arcsec=separation)
        assert candidate["detected"] is False
        assert candidate["category"] == "INSUFFICIENT_EVIDENCE"
        assert candidate["proper_motion_arcsec_per_yr"] is None


def test_detect_residual_sources_clustering():
    """Verify connected component centroiding and source extraction from significance map."""
    sig_map = np.zeros((30, 30), dtype=np.float32)
    # Inject a 3x3 8.0-sigma transient at (15, 20)
    sig_map[14:17, 19:22] = 8.0

    sources = detect_residual_sources(sig_map, threshold_sigma=5.0)
    assert len(sources) == 1
    src = sources[0]
    assert src["pixel_count"] == 9
    assert abs(src["centroid_xy"][0] - 20.0) < 0.2
    assert abs(src["centroid_xy"][1] - 15.0) < 0.2
    assert src["peak_significance"] == 8.0
    assert src["nature"] == "positive_excess"


def test_cross_epoch_positional_match():
    """Verify angular separation matching against SPHEREx resolution threshold."""
    # Stationary match (1.2 arcsec offset, within 3.1" half-beam)
    m_stat = cross_epoch_positional_match((210.8000, 54.3480), (210.8003, 54.3482), match_radius_arcsec=3.1)
    assert m_stat["is_spatially_coincident"] is True
    assert m_stat["classification"] == "stationary_source"

    # Moving offset (15.0 arcsec offset)
    m_move = cross_epoch_positional_match((210.8000, 54.3480), (210.8050, 54.3500), match_radius_arcsec=3.1)
    assert m_move["is_spatially_coincident"] is False
    assert m_move["classification"] == "spatially_displaced"
