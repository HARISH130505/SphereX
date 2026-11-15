"""
Epoch comparison and differential imaging routes.
Uses genuine FITS observations, WCS-based celestial reprojection,
variance-propagated difference imaging, and strict separation between
detector saturation telemetry and astronomical candidate detection.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException
import numpy as np

from app.schemas.comparison import EpochComparisonRequest, EpochComparisonResponse
from app.schemas.observation import ObservationSchema
from app.services.storage.repository import repository
from app.services.astronomy.fits_io import load_fits_image, render_png_base64, render_overlap_mask_base64
from app.services.astronomy.registration import register_observation_pair
from app.services.astronomy.difference import compute_difference_map
from app.services.astronomy.detection import assess_candidate, detect_residual_sources, DEFAULT_RESIDUAL_THRESHOLD_SIGMA, DEFAULT_RESIDUAL_MIN_PIXELS
from app.services.astronomy.quality import BRIGHTNESS_THRESHOLD_MJY_SR
from app.services.astronomy.provenance import processing_configuration
from app.services.astronomy.evidence import generate_evidence_dossier, generate_visual_comparison_dossier
from app.services.astronomy.comparison_validity import metadata_failures, evaluate_comparison_validity
from app.config import MIN_COMPARISON_OVERLAP
from app.services.astronomy.source_matching import investigate_epoch_motion

router = APIRouter(prefix="/epoch", tags=["Comparisons"])

@router.get("/groups/{target}")
def get_epochs(target: str = "M101"):
    obs_list = repository.get_all(target=target)
    if not obs_list:
        raise HTTPException(status_code=404, detail="No observations found.")
    obs_list.sort(key=lambda x: x.obs_time_mjd)
    # Temporal clustering into epochs (>30 days separation)
    groups = []
    curr = []
    last_t = None
    for o in obs_list:
        if last_t is None or (o.obs_time_mjd - last_t) > 30.0:
            if curr:
                groups.append(curr)
            curr = [o]
        else:
            curr.append(o)
        last_t = o.obs_time_mjd
    if curr:
        groups.append(curr)

    res = []
    for i, grp in enumerate(groups, 1):
        mjds = [o.obs_time_mjd for o in grp]
        res.append({
            "epoch_id": i,
            "name": f"Survey Epoch {i}",
            "mjd_min": min(mjds),
            "mjd_max": max(mjds),
            "date_label": grp[0].obs_time_iso or f"MJD {min(mjds):.0f}",
            "observation_count": len(grp),
            "bands": list(dict.fromkeys(o.band for o in grp)),
            "observations": grp,
        })
    return res

@router.post("/compare", response_model=EpochComparisonResponse)
def compare_epochs(req: EpochComparisonRequest):
    obs1 = repository.get_by_id(req.epoch_1_product_id)
    obs2 = repository.get_by_id(req.epoch_2_product_id)
    if not obs1 or not obs2:
        raise HTTPException(status_code=404, detail="Observation(s) not found.")

    failures = metadata_failures(obs1, obs2)
    if failures:
        raise HTTPException(status_code=422, detail={
            "code": "INVALID_COMPARISON", "status": "INVALID_COMPARISON",
            "scientific_analysis_allowed": False,
            "message": " ".join(item["message"] for item in failures),
            "failure_reasons": failures, "min_overlap_fraction": MIN_COMPARISON_OVERLAP,
        })

    try:
        m1 = load_fits_image(obs1)
        m2 = load_fits_image(obs2)
    except FileNotFoundError as fnf_err:
        raise HTTPException(status_code=404, detail=f"Observation FITS product unavailable: {str(fnf_err)}")
    except Exception as err:
        raise HTTPException(status_code=502, detail=f"Failed to load FITS data for comparison: {str(err)}")

    dt_days = abs(obs2.obs_time_mjd - obs1.obs_time_mjd)

    # 1. Genuine WCS Astronomical Image Registration on Common Celestial Reference Grid
    reg_result = register_observation_pair(m1, m2, reference="epoch_1")
    img1 = reg_result["registered_img1"]
    var1 = reg_result["registered_var1"]
    img2_reg = reg_result["registered_img2"]
    var2_reg = reg_result["registered_var2"]
    valid_footprint = reg_result["valid_footprint"]
    diag = reg_result["diagnostics"]
    validity = evaluate_comparison_validity(obs1, obs2, m1, m2, reg_result)
    data_quality = {f"epoch_{i}": {"quality": model["quality_summary"], "variance": model["variance_summary"],
                    "science_valid_pixel_count": int(np.count_nonzero(model["valid_mask"]))}
                    for i, model in enumerate((m1, m2), 1)}
    if not validity["scientific_analysis_allowed"]:
        # No difference calculation or source/motion routines are invoked here.
        originals = [render_png_base64(model["image"], stretch=req.stretch, colormap="plasma")
                     for model in (m1, m2)]
        processing = processing_configuration(req, validity, diag)
        dossier = generate_visual_comparison_dossier(obs1, obs2, validity, diag, data_quality,
            input_models=(m1, m2), processing_context=processing)
        reasons = [item["message"] for item in validity["failure_reasons"]]
        explanation = "Scientific analysis blocked: " + " ".join(reasons)
        return EpochComparisonResponse(
            comparison_validity=validity, data_quality=data_quality, epoch_1_meta=obs1, epoch_2_meta=obs2,
            time_delta_days=dt_days, epoch_1_image_base64=originals[0], epoch_2_image_base64=originals[1],
            epoch_1_original_image_base64=originals[0], epoch_2_original_image_base64=originals[1],
            motion_detected=False, scientific_summary="NON_SCIENTIFIC_VISUAL_COMPARISON. " + explanation,
            registration_diagnostics=diag,
            candidate_assessment=dossier["candidate_assessment"],
            motion_analysis=dossier["motion_analysis"],
            detected_sources=[], evidence_dossier={k: v for k, v in dossier.items() if k != "markdown_report"},
            evidence_report_markdown=dossier["markdown_report"])

    # 2. Variance-Propagated Difference Imaging
    # D = I2 - I1, Var(D) = Var(I1) + Var(I2), S = D / sqrt(Var(D))
    is_saturated = (
        obs1.screening_status == "REJECTED_SATURATED" or
        obs2.screening_status == "REJECTED_SATURATED"
    )

    motion_analysis = investigate_epoch_motion(m1, m2, obs1, obs2, diag)

    combined_masks = {name: np.asarray(reg_result.get("registered_masks1", {}).get(name, np.zeros(img1.shape, bool))) |
                      np.asarray(reg_result.get("registered_masks2", {}).get(name, np.zeros(img1.shape, bool)))
                      for name in set(reg_result.get("registered_masks1", {})) | set(reg_result.get("registered_masks2", {}))}
    diff_data = compute_difference_map(
        img1,
        img2_reg,
        var1,
        var2_reg,
        valid_mask=valid_footprint if motion_analysis["inputs_valid"] else np.zeros_like(valid_footprint),
        saturation_threshold_mjy_sr=BRIGHTNESS_THRESHOLD_MJY_SR,
        variance_provenance=(m1["variance_provenance"], m2["variance_provenance"]),
        quality_masks=combined_masks,
    )

    # 3. Source Extraction on Difference Significance Map
    ref_coord = (obs1.ra, obs1.dec) if (obs1.ra is not None and obs1.dec is not None) else None
    ps_val = m1.get("wcs_info", {}).get("pixel_scale_arcsec", 6.2)
    residual_sources = detect_residual_sources(
        diff_data["significance"],
        wcs=m1.get("wcs"),
        threshold_sigma=DEFAULT_RESIDUAL_THRESHOLD_SIGMA,
        min_pixels=DEFAULT_RESIDUAL_MIN_PIXELS,
        diff_map=diff_data["diff"],
        total_var=diff_data["total_variance"],
        img1=img1,
        img2=img2_reg,
        pixel_scale_arcsec=ps_val,
        ref_target_coord=ref_coord,
        is_saturated=is_saturated,
    ) if motion_analysis["inputs_valid"] else []

    # 4. Scientific Candidate Assessment (Separating telemetry vs astronomical sources)
    candidate_eval = assess_candidate(
        peak_sig=diff_data["peak_sig"],
        dt_days=dt_days,
        is_saturated=is_saturated,
        motion_analysis=motion_analysis,
    )

    # 5. Base64 PNG Rendering with aperture overlays on reference center
    t1_xy = m1.get("target_xy", [img1.shape[1] / 2.0, img1.shape[0] / 2.0])
    t2_orig_xy = m2.get("target_xy", [m2["image"].shape[1] / 2.0, m2["image"].shape[0] / 2.0])

    img1_b64 = render_png_base64(img1, stretch=req.stretch, colormap="plasma", aperture_center=tuple(t1_xy))
    img2_b64 = render_png_base64(img2_reg, stretch=req.stretch, colormap="plasma", aperture_center=tuple(t1_xy))
    img1_orig_b64 = render_png_base64(m1["image"], stretch=req.stretch, colormap="plasma", aperture_center=tuple(t1_xy))
    img2_orig_b64 = render_png_base64(m2["image"], stretch=req.stretch, colormap="plasma", aperture_center=tuple(t2_orig_xy))
    diff_b64 = render_png_base64(diff_data["diff"], stretch="linear", colormap=req.colormap, aperture_center=tuple(t1_xy))
    sig_b64 = render_png_base64(diff_data["significance"], stretch="asinh", colormap="inferno", aperture_center=tuple(t1_xy))
    mask_b64 = render_overlap_mask_base64(valid_footprint, diff_data.get("sat_mask"))

    # 6. Generate Scientific Evidence Dossier (Reproducible JSON & Markdown)
    dossier_result = generate_evidence_dossier(
        obs1=obs1,
        obs2=obs2,
        diff_data=diff_data,
        reg_diag=diag,
        sources=residual_sources,
        candidate_eval=candidate_eval,
        dt_days=dt_days,
        motion_analysis=motion_analysis,
        comparison_validity=validity,
        data_quality=data_quality,
        input_models=(m1, m2),
        processing_context=processing_configuration(req, validity, diag, motion_analysis=motion_analysis, pixel_scale_arcsec=ps_val),
    )

    # Calculate mean flux ratio over valid overlap
    valid_i1 = img1[valid_footprint]
    valid_i2 = img2_reg[valid_footprint]
    flux1 = float(np.nanmean(valid_i1)) if len(valid_i1) > 0 else 1.0
    flux2 = float(np.nanmean(valid_i2)) if len(valid_i2) > 0 else 1.0
    ratio = flux2 / flux1 if flux1 > 0 else 1.0

    # The compatibility vector is available only for one measured source pair.
    movers = [a for a in motion_analysis["associations"]
              if a["classification"] == "POSSIBLE_MOVING_OBJECT_CANDIDATE"]
    motion_vec = None
    if len(movers) == 1:
        motion_vec = {key: movers[0][key] for key in
                      ("delta_ra_arcsec", "delta_dec_arcsec", "proper_motion_arcsec_per_yr")}

    # 8. Formulate Scientifically Accurate Summary
    method_str = "WCS celestial reprojection (reproject_interp)" if diag.get("wcs_aligned") else "dimension-slicing fallback"
    summary = (
        f"Differential photometry between {obs1.obs_id} and {obs2.obs_id} ({dt_days:.1f} days baseline). "
        f"Alignment method: {method_str} ({diag.get('overlap_fraction', 0)*100:.1f}% footprint overlap). "
        f"Peak residual significance: {diff_data['peak_sig']:.2f}σ. "
    )
    if is_saturated:
        summary += (
            "WARNING: Central detector saturation (SUR overflow) detected in one or both epochs. "
            "Residual significance reflects masked saturation boundaries and CANNOT be interpreted as an astronomical moving object or Planet Nine."
        )
    else:
        summary += candidate_eval["scientific_assessment"]

    return EpochComparisonResponse(
        comparison_validity=validity,
        data_quality=data_quality,
        epoch_1_meta=obs1,
        epoch_2_meta=obs2,
        time_delta_days=round(dt_days, 2),
        epoch_1_image_base64=img1_b64,
        epoch_2_image_base64=img2_b64,
        difference_image_base64=diff_b64,
        significance_image_base64=sig_b64,
        flux_ratio=round(ratio, 4),
        transient_score=round(candidate_eval["confidence_score"], 3),
        motion_detected=bool(candidate_eval["detected"] and candidate_eval["category"] == "POSSIBLE_MOVING_OBJECT_CANDIDATE"),
        motion_vector_arcsec=motion_vec,
        scientific_summary=summary,
        registration_diagnostics=diag,
        difference_statistics={
            "mean_diff": diff_data["mean_diff"],
            "median_diff": diff_data["median_diff"],
            "rms_diff": diff_data["rms_diff"],
            "valid_pixel_count": diff_data["valid_pixel_count"],
            "saturated_pixel_count": diff_data["saturated_pixel_count"],
            "brightness_threshold_pixel_count": diff_data["brightness_threshold_pixel_count"],
            "invalid_variance_pixel_count": diff_data["invalid_variance_pixel_count"],
            "quality_mask_counts": diff_data["quality_mask_counts"],
            "variance_provenance": diff_data["variance_provenance"],
            "variance_propagation_verified": diff_data["variance_propagation_verified"],
            "detected_residual_sources_count": len(residual_sources),
        },
        candidate_assessment=candidate_eval,
        motion_analysis=motion_analysis,
        epoch_1_original_image_base64=img1_orig_b64,
        epoch_2_original_image_base64=img2_orig_b64,
        overlap_mask_image_base64=mask_b64,
        detected_sources=residual_sources,
        evidence_dossier={k: v for k, v in dossier_result.items() if k != "markdown_report"},
        evidence_report_markdown=dossier_result.get("markdown_report"),
    )
