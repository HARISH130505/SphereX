"""SIMULATION tests unless explicitly marked real FITS integration.

These establish software behavior for known truth, not survey-wide validation.
"""
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.wcs import WCS
import astropy.units as u
from app.services.astronomy.source_matching import (
    MatchingParameters, extract_epoch_sources, investigate_epoch_motion,
    associate_epoch_sources,
)
from app.services.astronomy.detection import assess_candidate, detect_residual_sources
from app.services.astronomy.registration import register_observation_pair


def make_wcs(offset=(0, 0)):
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [48 + offset[0], 48 + offset[1]]
    wcs.wcs.cdelt = [-6.2 / 3600, 6.2 / 3600]
    wcs.wcs.crval = [210.8, 54.35]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    return wcs


def render(wcs, sources, seed=1):
    yy, xx = np.indices((96, 96))
    image = 5 + np.random.default_rng(seed).normal(0, 0.1, (96, 96))
    for coordinate, amplitude in sources:
        x, y = wcs.world_to_pixel(coordinate)
        image += amplitude * np.exp(-((xx-x)**2+(yy-y)**2)/(2*0.8**2))
    return {"image": image, "variance": np.full_like(image, 0.01), "wcs": wcs,
            "variance_provenance": "MEASURED", "quality_verified": True,
            "science_units_verified": True, "valid_mask": np.ones(image.shape, bool), "wcs_info": {}}


def observations():
    common = dict(target="test field", band="SPHEREx-D1", screening_status="PASSED_CLEAN")
    return (SimpleNamespace(obs_id="a", obs_time_mjd=60000., **common),
            SimpleNamespace(obs_id="b", obs_time_mjd=60180., **common))


def scene(motion=0, amplitude=100, dither=(0.37, -0.28)):
    w1, w2 = make_wcs(), make_wcs(dither)
    anchors = [(w1.pixel_to_world(x, y), 100.) for x,y in [(18,18),(72,18),(18,72),(72,72)]]
    first = anchors + [(w1.pixel_to_world(45,45),100.)]
    second = anchors + [(w1.pixel_to_world(45+motion,45),amplitude)]
    return render(w1,first), render(w2,second,seed=2)


def investigate(m1, m2, parameters=MatchingParameters()):
    o1,o2=observations()
    reg=register_observation_pair(m1,m2)
    assert reg["diagnostics"]["wcs_aligned"] is True
    return investigate_epoch_motion(m1,m2,o1,o2,reg["diagnostics"],parameters)


def test_stationary_sources_remain_stationary_across_dither():
    result=investigate(*scene())
    assert result["status"] == "VALID_FOR_SOURCE_ASSOCIATION"
    assert result["reference_source_count"] == 5
    assert len(result["associations"]) == 5
    assert {a["classification"] for a in result["associations"]} == {"STATIONARY_ASTRONOMICAL_SOURCE"}
    assert max(a["angular_displacement_arcsec"] for a in result["associations"]) < 0.5


def test_injected_moving_source_uses_two_measured_positions():
    result=investigate(*scene(motion=2.0))
    movers=[a for a in result["associations"] if a["classification"] == "POSSIBLE_MOVING_OBJECT_CANDIDATE"]
    assert len(movers)==1
    mover=movers[0]
    assert mover["displacement_significance"] >= 5
    assert mover["angular_displacement_arcsec"] == pytest.approx(12.4, abs=0.5)
    assert mover["proper_motion_arcsec_per_yr"] == pytest.approx(12.4/(180/365.25),abs=1)
    assert mover["epoch_1_source"]["ra_deg"] != mover["epoch_2_source"]["ra_deg"]
    verdict=assess_candidate(100,180,motion_analysis=result)
    assert verdict["category"] == "POSSIBLE_MOVING_OBJECT_CANDIDATE"


def test_variable_but_stationary_source_is_not_moving():
    result=investigate(*scene(amplitude=200))
    assert sum(a["classification"]=="VARIABLE_SOURCE" for a in result["associations"]) == 1
    assert not any(a["classification"]=="POSSIBLE_MOVING_OBJECT_CANDIDATE" for a in result["associations"])
    assert assess_candidate(100,180,motion_analysis=result)["category"] == "VARIABLE_SOURCE"


def test_target_and_pointing_offsets_are_not_motion_evidence():
    sig=np.zeros((30,30));sig[10:12,10:12]=25
    residual=detect_residual_sources(sig,wcs=make_wcs(),ref_target_coord=(0.,0.))[0]
    assert residual["classification"] == "INSUFFICIENT_EVIDENCE"
    assert assess_candidate(100,180,angular_displacement_arcsec=10000)["category"] == "INSUFFICIENT_EVIDENCE"
    m1,m2=scene()
    o1,o2=observations()
    reg=register_observation_pair(m1,m2)["diagnostics"]
    baseline=investigate_epoch_motion(m1,m2,o1,o2,reg)
    reg["angular_separation_arcsec"]=100000
    reg["subpixel_offset_xy"]=[1e6,1e6]
    assert investigate_epoch_motion(m1,m2,o1,o2,reg)==baseline


@pytest.mark.parametrize("count",[4,16,49])
def test_stationary_source_density(count):
    w1,w2=make_wcs(),make_wcs((0.2,-0.3))
    side=int(np.sqrt(count))
    positions=np.linspace(12,82,side)
    sources=[(w1.pixel_to_world(x,y),100.) for x in positions for y in positions]
    result=investigate(render(w1,sources),render(w2,sources,seed=2))
    assert result["status"] == "VALID_FOR_SOURCE_ASSOCIATION"
    assert len(result["associations"])==count
    assert all(a["classification"]=="STATIONARY_ASTRONOMICAL_SOURCE" for a in result["associations"])


def test_ambiguous_displaced_counterparts_are_insufficient():
    m1,m2=scene(motion=2)
    first,second=extract_epoch_sources(m1),extract_epoch_sources(m2)
    moving=max(second,key=lambda s:s["centroid_xy"][0] if 35<s["centroid_xy"][1]<55 else -1)
    duplicate=dict(moving,source_id=999,ra_deg=moving["ra_deg"]+0.0001)
    result=associate_epoch_sources(first,second+[duplicate],180)
    assert result["reference_frame_verified"] is True
    assert not any(a["classification"]=="POSSIBLE_MOVING_OBJECT_CANDIDATE" for a in result["associations"])
    assert sum(a["classification"]=="INSUFFICIENT_EVIDENCE" for a in result["associations"])>=3


def test_unmatched_new_source_is_not_motion():
    m1,m2=scene()
    w2=m2["wcs"]
    extra=render(w2,[(make_wcs().pixel_to_world(45,70),100.)],seed=3)["image"]-5
    m2["image"]+=extra
    result=investigate(m1,m2)
    assert any(a["association_status"]=="UNMATCHED_OR_AMBIGUOUS" for a in result["associations"])
    assert not any(a["classification"]=="POSSIBLE_MOVING_OBJECT_CANDIDATE" for a in result["associations"])


def test_uncertainty_changes_displacement_evidence():
    m1,m2=scene(motion=2)
    result=investigate(m1,m2,replace(MatchingParameters(),astrometric_floor_arcsec=5.0))
    assert not any(a["classification"]=="POSSIBLE_MOVING_OBJECT_CANDIDATE" for a in result["associations"])


def test_too_few_reference_sources_prevents_motion():
    w=make_wcs()
    m1=render(w,[(w.pixel_to_world(30,30),100)])
    m2=render(w,[(w.pixel_to_world(32,30),100)])
    result=investigate(m1,m2)
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert all(a["classification"]=="INSUFFICIENT_EVIDENCE" for a in result["associations"])


@pytest.mark.parametrize("failure",["wcs","registration","overlap","same_epoch","same_product","target","band","variance","saturation"])
def test_invalid_motion_inputs_block_extraction(failure,monkeypatch):
    import app.services.astronomy.source_matching as module
    m1,m2=scene();o1,o2=observations()
    diagnostics={"wcs_aligned":True,"overlap_fraction":0.9}
    if failure=="wcs": m2["wcs"]=None
    if failure=="registration": diagnostics["wcs_aligned"]=False
    if failure=="overlap": diagnostics["overlap_fraction"]=0.1
    if failure=="same_epoch": o2.obs_time_mjd=o1.obs_time_mjd
    if failure=="same_product": o2.obs_id=o1.obs_id
    if failure=="target": o2.target="other"
    if failure=="band": o2.band="SPHEREx-D4"
    if failure=="variance": m2["variance_provenance"]="ESTIMATED"
    if failure=="saturation": o2.screening_status="REJECTED_SATURATED"
    monkeypatch.setattr(module,"extract_epoch_sources",lambda *a:pytest.fail("Extraction must be blocked"))
    result=module.investigate_epoch_motion(m1,m2,o1,o2,diagnostics)
    assert result["status"]=="INSUFFICIENT_EVIDENCE"
    assert result["failure_reasons"]
    assert result["associations"]==[]


def test_invalid_variance_pixels_are_not_sources():
    m1,_=scene();m1["variance"][:]=np.nan
    assert extract_epoch_sources(m1)==[]


def test_reversing_epochs_reverses_measured_motion_vector():
    m1,m2=scene(motion=2)
    first,second=extract_epoch_sources(m1),extract_epoch_sources(m2)
    forward=associate_epoch_sources(first,second,180)
    reverse=associate_epoch_sources(second,first,-180)
    f=next(a for a in forward["associations"] if a["classification"]=="POSSIBLE_MOVING_OBJECT_CANDIDATE")
    r=next(a for a in reverse["associations"] if a["classification"]=="POSSIBLE_MOVING_OBJECT_CANDIDATE")
    assert r["delta_ra_arcsec"]==pytest.approx(-f["delta_ra_arcsec"],abs=1e-3)
    assert r["east_motion_arcsec_per_yr"]==pytest.approx(f["east_motion_arcsec_per_yr"],abs=1e-3)


def test_real_fits_measurements_use_each_native_wcs():
    """REAL FITS integration, no claim of known source motion truth."""
    from app.services.storage.repository import repository
    from app.services.astronomy.fits_io import load_fits_image
    o1,o2=repository.get_by_id("TAP_M101_002"),repository.get_by_id("TAP_M101_221")
    m1,m2=load_fits_image(o1),load_fits_image(o2)
    reg=register_observation_pair(m1,m2)
    result=investigate_epoch_motion(m1,m2,o1,o2,reg["diagnostics"])
    assert result["inputs_valid"]
    assert result["epoch_1_sources"] and result["epoch_2_sources"]
    for key,model in [("epoch_1_sources",m1),("epoch_2_sources",m2)]:
        for source in result[key]:
            coordinate=model["wcs"].celestial.pixel_to_world(*source["centroid_xy"])
            measured=SkyCoord(source["ra_deg"]*u.deg,source["dec_deg"]*u.deg)
            assert coordinate.separation(measured).arcsec < 1e-6
    for pair in result["associations"]:
        if pair["association_status"]=="MATCHED":
            a,b=pair["epoch_1_source"],pair["epoch_2_source"]
            actual=SkyCoord(a["ra_deg"]*u.deg,a["dec_deg"]*u.deg).separation(SkyCoord(b["ra_deg"]*u.deg,b["dec_deg"]*u.deg)).arcsec
            assert pair["angular_displacement_arcsec"]==pytest.approx(actual)


def test_nonfinite_overlap_blocks_extraction(monkeypatch):
    from app.services.astronomy import source_matching as module
    m1, m2 = scene()
    o1, o2 = observations()
    monkeypatch.setattr(module, "extract_epoch_sources", lambda *a: pytest.fail("Extraction must be blocked"))
    result = investigate_epoch_motion(m1, m2, o1, o2, {"wcs_aligned": True, "overlap_fraction": float("nan")})
    assert not result["inputs_valid"]
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_real_fits_api_exposes_consistent_motion_evidence():
    """REAL FITS HTTP integration; does not establish astrophysical ground truth."""
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        response = client.post("/api/epoch/compare", json={
            "epoch_1_obs_id": "TAP_M101_002", "epoch_2_obs_id": "TAP_M101_221"})
    assert response.status_code == 200
    result = response.json()
    analysis = result["motion_analysis"]
    assert analysis["epoch_1_sources"] and analysis["epoch_2_sources"]
    assert result["evidence_dossier"]["motion_analysis"] == analysis
    assert analysis["status"] in result["evidence_report_markdown"]
    if not analysis["reference_frame_verified"]:
        assert result["candidate_assessment"]["category"] == "INSUFFICIENT_EVIDENCE"
        assert not result["motion_detected"]
