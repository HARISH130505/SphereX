"""
Unit tests for quality bitmask decoding and vetting.
"""
from app.services.astronomy.quality import decode_flags, evaluate_quality

def test_flag_decoding():
    flags = decode_flags(2097152)  # bit 21 = SOURCE
    assert "SOURCE" in flags

    sat_flags = decode_flags(69206022)
    assert "BLOOM" in sat_flags
    assert "OVERFLOW" in sat_flags
    assert "SUR_ERROR" in sat_flags
    assert "SATURATED" not in sat_flags
    assert "SOURCE" in sat_flags

def test_evaluate_quality_clean():
    res = evaluate_quality(
        center_finite=True,
        center_flags_raw=2097152,
        aperture_fatal_count=0,
        aperture_total_pixels=29,
        bg_usable_pixels=128,
        variance_available=True,
        target_inside=True,
    )
    assert res["status"] == "PASSED_CLEAN"
    assert res["usable"] is True


def test_legacy_decoder_uses_correct_public_image_flag_names():
    from app.services.screening_service import decode_spherex_flags
    assert decode_spherex_flags(1) == ["TRANSIENT"]
    assert decode_spherex_flags(2) == ["OVERFLOW"]
    assert decode_spherex_flags(4) == ["SUR_ERROR"]
    assert "SATURATED" not in decode_spherex_flags(69206022)
