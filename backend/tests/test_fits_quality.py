"""SIMULATION FITS tests except the explicitly named real cached-product checks."""
from copy import deepcopy
from types import SimpleNamespace
import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS
from app.services.astronomy import fits_io
from app.services.astronomy.difference import compute_difference_map
from app.services.astronomy.registration import register_observation_pair
from app.services.astronomy.source_matching import extract_epoch_sources
from app.services.storage.repository import repository

DEFINITIONS = {"TRANSIENT": 0, "OVERFLOW": 1, "SUR_ERROR": 2, "NONFUNC": 6,
               "MISSING_DATA": 9, "SOURCE": 21, "BLOOM": 26}


def fixture_hdus(flags=True, variance=True, definitions=DEFINITIONS, celestial=True):
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [16, 16]
    wcs.wcs.cdelt = [-1/3600, 1/3600]
    wcs.wcs.crval = [10, 20]
    if celestial: wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    header = wcs.to_header()
    header["BUNIT"] = "MJy / sr"
    hdus = [fits.PrimaryHDU(), fits.ImageHDU(np.full((32,32),5.), header=header, name="IMAGE")]
    if flags:
        plane = fits.ImageHDU(np.zeros((32,32), np.int32), name="FLAGS")
        for name, bit in definitions.items(): plane.header[f"HIERARCH MP_{name}"] = bit
        hdus.append(plane)
    if variance:
        plane = fits.ImageHDU(np.full((32,32),4.), name="VARIANCE")
        plane.header["BUNIT"] = "MJy2 / sr2"
        hdus.append(plane)
    return fits.HDUList(hdus)


def load_fixture(monkeypatch, tmp_path, hdus, url="fixture://synthetic"):
    path = tmp_path / "synthetic.fits"
    hdus.writeto(path, overwrite=True)
    hdus.close()
    monkeypatch.setattr(fits_io, "fetch_or_load_fits_file", lambda obs: path)
    return fits_io.load_fits_image(SimpleNamespace(cutout_url=url, target_x=16, target_y=16))


def test_flag_definitions_come_from_the_product_not_global_bit_positions(monkeypatch, tmp_path):
    hdus = fixture_hdus(definitions={"SOURCE": 2, "OVERFLOW": 21})
    hdus["FLAGS"].data[10,10] = 1 << 21
    hdus["FLAGS"].data[11,11] = 1 << 2
    model = load_fixture(monkeypatch, tmp_path, hdus)
    assert model["quality_summary"]["definitions_source"] == "FITS_MP_HEADERS"
    assert not model["valid_mask"][10,10]
    assert model["quality_masks"]["overflow"][10,10]
    assert model["valid_mask"][11,11]
    assert model["quality_masks"]["source"][11,11]
    assert model["flags_raw"][10,10] == 1 << 21


def test_distinct_detector_states_and_unknown_bits_are_preserved(monkeypatch, tmp_path):
    hdus = fixture_hdus()
    flags = hdus["FLAGS"].data
    for x, bit in enumerate([0,1,2,9,26,30,21], 5): flags[10,x] = 1 << bit
    original = flags.copy()
    model = load_fixture(monkeypatch, tmp_path, hdus)
    assert np.array_equal(model["flags_raw"], original)
    for x, name in enumerate(["glitch","overflow","sur_error","missing_data","bloom","unknown_bits","source"],5):
        assert model["quality_masks"][name][10,x]
    assert not model["valid_mask"][10,5:11].any()
    assert model["valid_mask"][10,11]  # SOURCE is informative, not a bad detector pixel.
    assert "saturated" not in model["quality_masks"]


@pytest.mark.parametrize("failure", ["missing_flags", "missing_definitions", "bad_flags_shape", "conflicting_definitions"])
def test_unverified_quality_blocks_native_science(monkeypatch, tmp_path, failure):
    hdus = fixture_hdus(flags=failure != "missing_flags", definitions={} if failure == "missing_definitions" else DEFINITIONS)
    if failure == "bad_flags_shape": hdus["FLAGS"].data = np.zeros((4,4),np.int32)
    if failure == "conflicting_definitions": hdus["FLAGS"].header["HIERARCH MP_BLOOM"] = 1
    model = load_fixture(monkeypatch, tmp_path, hdus)
    assert not model["quality_verified"]
    assert not model["valid_mask"].any()
    assert extract_epoch_sources(model) == []


def test_recognized_qr3_metadata_uses_documented_schema(monkeypatch, tmp_path):
    model = load_fixture(monkeypatch, tmp_path, fixture_hdus(definitions={}),
                         "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/test.fits")
    assert model["quality_verified"]
    assert model["quality_summary"]["definitions_source"] == "DOCUMENTED_RELEASE_SCHEMA"
    assert model["flag_definitions"][0] == "TRANSIENT"
    assert model["flag_definitions"][1] == "OVERFLOW"
    assert model["flag_definitions"][2] == "SUR_ERROR"


@pytest.mark.parametrize("failure", ["missing", "wrong_shape", "all_invalid", "unknown_units"])
def test_missing_or_invalid_variance_never_gets_constant_replacement(monkeypatch, tmp_path, failure):
    hdus = fixture_hdus(variance=failure != "missing")
    if failure == "wrong_shape": hdus["VARIANCE"].data = np.ones((4,4))
    if failure == "all_invalid": hdus["VARIANCE"].data[:] = -1
    if failure == "unknown_units": del hdus["VARIANCE"].header["BUNIT"]
    model = load_fixture(monkeypatch, tmp_path, hdus)
    assert not model["valid_mask"].any()
    assert extract_epoch_sources(model) == []
    if failure == "missing":
        assert model["variance_provenance"] == "UNAVAILABLE"
        assert model["variance_raw"] is None
        assert np.isnan(model["variance"]).all()
    elif failure == "wrong_shape":
        assert model["variance_raw"].shape == (4,4)
        assert np.isnan(model["variance"]).all()
    elif failure == "all_invalid":
        assert (model["variance"] == -1).all()
    else:
        assert not model["science_units_verified"]


def test_partial_invalid_variance_stays_invalid(monkeypatch, tmp_path):
    hdus = fixture_hdus()
    hdus["VARIANCE"].data[10,5:8] = [0,-1,np.nan]
    model = load_fixture(monkeypatch, tmp_path, hdus)
    assert model["variance_provenance"] == "MEASURED"
    assert model["variance"][10,5] == 0 and model["variance"][10,6] == -1
    assert np.isnan(model["variance"][10,7])
    assert not model["valid_mask"][10,5:8].any()
    assert model["variance_summary"]["invalid_pixel_count"] == 3


def test_bilinear_variance_uses_squared_weights(monkeypatch, tmp_path):
    first = load_fixture(monkeypatch, tmp_path, fixture_hdus())
    second = deepcopy(first)
    second["wcs"].wcs.crpix += 0.5
    second["image"] = np.indices((32,32))[1] + 5.
    result = register_observation_pair(first, second)
    assert result["valid_footprint"][10,10]
    # Four weights of 1/4, each input variance 4: variance = 4 * (1/4)^2 * 4 = 1.
    assert result["registered_var2"][10,10] == pytest.approx(1.,abs=1e-7)
    assert result["registered_img2"][10,10] == pytest.approx(15.5,abs=1e-7)
    diff = compute_difference_map(result["registered_img1"], result["registered_img2"],
        result["registered_var1"], result["registered_var2"], valid_mask=result["valid_footprint"],
        variance_provenance=("MEASURED","MEASURED"))
    assert diff["total_variance"][10,10] == pytest.approx(5.,abs=1e-7)
    assert diff["significance"][10,10] == pytest.approx(10.5/np.sqrt(5),abs=1e-7)


def test_every_flagged_interpolation_contributor_vetoes_output(monkeypatch, tmp_path):
    first = load_fixture(monkeypatch, tmp_path, fixture_hdus())
    hdus = fixture_hdus()
    for (y,x),bit in zip([(10,10),(10,11),(11,10),(11,11)], [0,1,2,9]):
        hdus["FLAGS"].data[y,x] = 1 << bit
    second = load_fixture(monkeypatch, tmp_path, hdus)
    second["wcs"].wcs.crpix += 0.5
    result = register_observation_pair(first, second)
    assert not result["valid_footprint"][10,10]
    assert np.isnan(result["registered_img2"][10,10])
    assert np.isnan(result["registered_var2"][10,10])
    assert result["registered_flags2"][10,10] == sum(1 << bit for bit in [0,1,2,9])
    for name in ("glitch","overflow","sur_error","missing_data"):
        assert result["registered_masks2"][name][10,10]
    assert result["valid_footprint"][20,20]


@pytest.mark.parametrize("provenance", [None, ("MEASURED","ESTIMATED"), ("MEASURED","UNAVAILABLE")])
def test_unverified_variance_cannot_generate_significance(provenance):
    image = np.ones((5,5))
    result = compute_difference_map(image,image*100,image,image,variance_provenance=provenance)
    assert not result["variance_propagation_verified"]
    assert result["valid_pixel_count"] == 0
    assert np.isnan(result["significance"]).all()
    assert result["peak_sig"] is None


def test_invalid_variance_excluded_without_floors_or_fabricated_saturation():
    image = np.ones((5,5))
    variance = np.full((5,5),1e-12)
    variance[0,:3] = [0,-1,np.nan]
    other = np.ones((5,5))*2
    other[1,1] = np.nan
    result = compute_difference_map(image,other,variance,variance,variance_provenance=("MEASURED","MEASURED"))
    assert np.isnan(result["significance"][0,:3]).all()
    assert result["significance"][3,3] == pytest.approx(1/np.sqrt(2e-12))
    assert result["saturated_pixel_count"] == 0
    assert result["nonfinite_image_pixel_count"] == 1


def test_real_qr2_flags_and_variance_are_unchanged_from_fits():
    obs = repository.get_by_id("TAP_M101_002")
    model = fits_io.load_fits_image(obs)
    with fits.open(fits_io.fetch_or_load_fits_file(obs)) as hdus:
        assert np.array_equal(model["flags_raw"],hdus["FLAGS"].data)
        assert np.array_equal(model["variance_raw"],hdus["VARIANCE"].data,equal_nan=True)
        definitions = {int(value): key[3:] for key,value in hdus["FLAGS"].header.items() if key.startswith("MP_")}
    assert model["flag_definitions"] == definitions
    assert model["quality_summary"]["definitions_source"] == "FITS_MP_HEADERS"
    assert model["quality_verified"] and model["science_units_verified"]


def test_real_qr3_flags_preserve_bloom_and_overflow_separately():
    model = fits_io.load_fits_image(repository.get_by_id("2026W32_2A_0147_1::SPHEREx-D1"))
    assert model["quality_summary"]["definitions_source"] == "DOCUMENTED_RELEASE_SCHEMA"
    assert model["quality_masks"]["bloom"].any()
    assert model["quality_masks"]["overflow"].any()
    assert model["quality_masks"]["sur_error"].any()
    assert model["quality_masks"]["nonfinite_image"].any()
    assert not model["valid_mask"][model["quality_masks"]["bloom"]].any()


def test_missing_wcs_remains_missing_with_quality_metadata(monkeypatch, tmp_path):
    model = load_fixture(monkeypatch,tmp_path,fixture_hdus(celestial=False))
    assert model["quality_verified"]
    assert extract_epoch_sources(model) == []


@pytest.mark.parametrize("failure,code", [("flags","UNVERIFIED_QUALITY_FLAGS"),
    ("definitions","UNVERIFIED_QUALITY_FLAGS"), ("variance","UNVERIFIED_VARIANCE"),
    ("units","UNVERIFIED_SCIENCE_UNITS")])
def test_mutated_real_fits_cannot_reach_scientific_processing(monkeypatch, tmp_path, failure, code):
    """Real cached FITS structure with deliberately removed metadata; no science truth claim."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.routes import comparisons
    pair = [repository.get_by_id(key) for key in ("TAP_M101_002","TAP_M101_221")]
    first = fits_io.load_fits_image(pair[0])
    with fits.open(fits_io.fetch_or_load_fits_file(pair[1])) as original:
        hdus = fits.HDUList([original[0].copy(),original["IMAGE"].copy(),original["FLAGS"].copy(),original["VARIANCE"].copy()])
    if failure == "flags": del hdus["FLAGS"]
    if failure == "variance": del hdus["VARIANCE"]
    if failure == "units": del hdus["VARIANCE"].header["BUNIT"]
    if failure == "definitions":
        for key in list(hdus["FLAGS"].header):
            if key.startswith("MP_"): del hdus["FLAGS"].header[key]
    second = load_fixture(monkeypatch,tmp_path,hdus)
    monkeypatch.setattr(comparisons,"load_fits_image",lambda obs: first if obs.product_id == pair[0].product_id else second)
    for name in ("compute_difference_map","detect_residual_sources","investigate_epoch_motion","assess_candidate"):
        monkeypatch.setattr(comparisons,name,lambda *a,**k: pytest.fail("Unverified FITS reached scientific processing"))
    with TestClient(app) as client:
        response = client.post("/api/epoch/compare",json={"epoch_1_product_id":pair[0].product_id,"epoch_2_product_id":pair[1].product_id})
    assert response.status_code == 200
    data = response.json()
    assert not data["comparison_validity"]["scientific_analysis_allowed"]
    assert code in {reason["code"] for reason in data["comparison_validity"]["failure_reasons"]}
    assert data["difference_statistics"] is None and data["significance_image_base64"] is None
    assert not data["motion_detected"]
    assert data["data_quality"] == data["evidence_dossier"]["data_quality"]


def test_invalid_variance_contributor_vetoes_every_affected_output(monkeypatch,tmp_path):
    first = load_fixture(monkeypatch,tmp_path,fixture_hdus())
    hdus = fixture_hdus()
    hdus["VARIANCE"].data[10,10] = 0
    second = load_fixture(monkeypatch,tmp_path,hdus)
    second["wcs"].wcs.crpix += 0.5
    result = register_observation_pair(first,second)
    for y,x in [(9,9),(9,10),(10,9),(10,10)]:
        assert not result["valid_footprint"][y,x]
        assert result["registered_masks2"]["invalid_variance"][y,x]
        assert np.isnan(result["registered_var2"][y,x])
    assert result["valid_footprint"][20,20]


def test_very_small_measured_variance_survives_registration(monkeypatch,tmp_path):
    hdus = fixture_hdus()
    hdus["VARIANCE"].data[:] = 1e-50
    first = load_fixture(monkeypatch,tmp_path,hdus)
    second = deepcopy(first)
    second["wcs"].wcs.crpix += 0.5
    result = register_observation_pair(first,second)
    assert result["valid_footprint"][10,10]
    assert result["registered_var2"][10,10] == pytest.approx(2.5e-51,rel=1e-7,abs=0)


def test_explicit_saturation_flag_remains_distinct_from_overflow_and_nan(monkeypatch,tmp_path):
    hdus = fixture_hdus(definitions={**DEFINITIONS,"SATURATED":8})
    hdus["FLAGS"].data[10,10] = 1 << 8
    hdus["FLAGS"].data[11,11] = 1 << 1
    hdus["IMAGE"].data[12,12] = np.nan
    model = load_fixture(monkeypatch,tmp_path,hdus)
    assert model["quality_masks"]["saturated"].sum() == 1
    assert model["quality_masks"]["overflow"].sum() == 1
    assert model["quality_masks"]["nonfinite_image"].sum() == 1
    assert not model["valid_mask"][[10,11,12],[10,11,12]].any()


def test_infinite_science_pixels_stay_invalid_without_corrupting_summary(monkeypatch,tmp_path):
    hdus = fixture_hdus()
    hdus["IMAGE"].data[16,16] = np.inf
    model = load_fixture(monkeypatch,tmp_path,hdus)
    assert not model["valid_mask"][16,16]
    assert model["center_val"] is None
    assert model["min_val"] == model["max_val"] == 5.
    assert model["quality_masks"]["nonfinite_image"].sum() == 1


@pytest.mark.parametrize("variance", [0.,-1.,np.nan])
def test_legacy_variability_helper_cannot_floor_invalid_variance(variance):
    from app.services.astronomy.detection import evaluate_variability
    result = evaluate_variability(1.,100.,variance,variance,variance_provenance=("MEASURED","MEASURED"))
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["variability_significance_sigma"] is None
    assert not result["is_statistically_variable"]


def test_legacy_variability_helper_requires_declared_provenance():
    from app.services.astronomy.detection import evaluate_variability
    result = evaluate_variability(1.,100.,1.,1.)
    assert result["variability_significance_sigma"] is None
    measured = evaluate_variability(1.,10.,1.,1.,variance_provenance=("MEASURED","MEASURED"))
    assert measured["variability_significance_sigma"] == pytest.approx(9/np.sqrt(2),abs=0.01)
