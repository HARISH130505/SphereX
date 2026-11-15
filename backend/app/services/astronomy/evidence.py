"""Structured evidence with a single Markdown renderer and stable SHA-256 provenance."""
from datetime import datetime, timezone
from typing import Dict, Any, List
import json
import numpy as np
from app.services.astronomy.provenance import (
    make_reproducibility, observation_record, seal_dossier, normalize,
)

CLASSIFICATIONS = {"STATIONARY_ASTRONOMICAL_SOURCE", "VARIABLE_SOURCE", "DETECTOR_ARTIFACT",
                   "POSSIBLE_MOVING_OBJECT_CANDIDATE", "INSUFFICIENT_EVIDENCE"}
KNOWN_LIMITATIONS = [
    "Bilinear resampling creates covariance between neighboring output pixels; only diagonal variance is modeled. Native pixel independence is an assumption.",
    "Same-band exposures can have different PSFs; no PSF-matching kernel is applied.",
    "Detector masks are conservative; unknown bits are excluded. The 3000 MJy/sr brightness screen does not establish physical saturation.",
    "Two-epoch associations are provisional and require additional epochs and catalog vetting to confirm motion.",
    "PSF width and astrometric/photometric floors are modeling assumptions, not calibrated survey-wide precision.",
    "Passing software tests does not establish astrophysical truth, completeness, or survey false-positive rates.",
]


def authoritative_assessment(candidate, validity):
    candidate = dict(candidate or {})
    category = candidate.get("category", "INSUFFICIENT_EVIDENCE")
    allowed = bool(validity and validity.get("scientific_analysis_allowed"))
    if category not in CLASSIFICATIONS or not allowed:
        category = "INSUFFICIENT_EVIDENCE"
    detected = bool(allowed and candidate.get("detected") and category in {
        "VARIABLE_SOURCE", "POSSIBLE_MOVING_OBJECT_CANDIDATE"})
    candidate.update(category=category, detected=detected, confidence_score_calibrated=False)
    assessment = {"classification": category, "detected": detected,
        "motion_detected": detected and category == "POSSIBLE_MOVING_OBJECT_CANDIDATE",
        "scientific_validity_status": validity.get("status", "NOT_EVALUATED") if validity else "NOT_EVALUATED",
        "scientific_assessment": candidate.get("scientific_assessment", "Insufficient evidence for an astronomical conclusion."),
        "confidence_probability": None, "confidence_probability_calibrated": False}
    if not allowed and category == "INSUFFICIENT_EVIDENCE":
        reasons = [item["message"] for item in (validity or {}).get("failure_reasons", [])]
        assessment["scientific_assessment"] = "Scientific analysis blocked: " + " ".join(reasons) if reasons else "Scientific comparison validity has not been established."
        candidate["scientific_assessment"] = assessment["scientific_assessment"]
    return candidate, assessment


def _statistics(diff_data):
    if diff_data is None:
        return None
    return normalize({key: value for key, value in diff_data.items() if not isinstance(value, np.ndarray)})


def _build_dossier(obs1, obs2, diff_data, diagnostics, sources, candidate, dt_days,
                   motion_analysis, validity, data_quality, input_models, processing_context):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    reproducibility = make_reproducibility(obs1, obs2, input_models, processing_context, timestamp)
    candidate, assessment = authoritative_assessment(candidate, validity)
    limitations = list(KNOWN_LIMITATIONS)
    if reproducibility["provenance_status"] != "COMPLETE":
        limitations.append("Provenance is partial: missing FITS content hashes or processing configuration prevent a claim of identical pixel inputs/configuration.")
    if validity and not validity["scientific_analysis_allowed"]:
        limitations.extend(item["message"] for item in validity["failure_reasons"])
    provenance = {"target": obs1.target, "epoch_1": observation_record(obs1),
                  "epoch_2": observation_record(obs2), "baseline_days": dt_days,
                  "archive_origin": "NASA/IPAC Infrared Science Archive (IRSA) SPHEREx Level 2b"}
    for index in (1, 2):
        provenance[f"epoch_{index}"]["fits_content"] = reproducibility["manifest"]["inputs"][index-1]["fits_content"]
    dossier = seal_dossier({"schema_version": "spherex-evidence-dossier-v1",
        "dossier_id": reproducibility["reproducibility_hash"], "target": obs1.target,
        "provenance": provenance, "data_quality": data_quality, "comparison_validity": validity,
        "registration": diagnostics, "difference_statistics": _statistics(diff_data),
        "sources": sources, "candidate_assessment": candidate, "assessment": assessment,
        "motion_analysis": motion_analysis, "reproducibility": reproducibility,
        "scientific_limitations": limitations})
    dossier["markdown_report"] = render_dossier_markdown(dossier)
    return dossier


def _display(value, digits=3):
    return "Unavailable" if value is None else (f"{value:.{digits}f}" if isinstance(value, (float, int)) else str(value))


def _cell(value):
    return str(value if value is not None else "Unavailable").replace("|", "\|").replace("\n", " ")


def render_dossier_markdown(dossier):
    """Every displayed verdict is read from the same sealed JSON assessment."""
    assessment, reproducibility = dossier["assessment"], dossier["reproducibility"]
    validity = dossier.get("comparison_validity") or {}
    inputs = reproducibility["manifest"]["inputs"]
    lines = [f"# SPHEREx Astronomical Evidence Dossier: {dossier['target']}", "",
        f"**Dossier Reference:** `{dossier['dossier_id']}`",
        f"**Generated:** {reproducibility['generated_at_utc']}",
        f"**Provenance status:** `{reproducibility['provenance_status']}`",
        f"**Manifest SHA-256:** `{reproducibility['manifest_sha256']}`",
        f"**Evidence SHA-256:** `{reproducibility['evidence_sha256']}`", "",
        "## 1. Evidence Assessment", "",
        f"**Primary Classification:** `{assessment['classification']}`",
        f"**Scientific Validity:** `{assessment['scientific_validity_status']}`",
        f"**Astrometric Motion Detected:** `{'YES' if assessment['motion_detected'] else 'NO'}`",
        f"**Detection Reported:** `{'YES' if assessment['detected'] else 'NO'}`",
        "**Detection confidence probability:** Not calibrated; no probability is asserted.",
        f"**Scientific Assessment:** {assessment['scientific_assessment']}", "",
        "## 2. Observation Provenance", "",
        "| Parameter | Epoch 1 | Epoch 2 |", "| --- | --- | --- |"]
    for label, key in (("Application product ID", "product_id"), ("Archive product ID", "archive_product_id"),
                       ("Original observation ID", "obs_id"), ("Spectral band", "band"),
                       ("Epoch MJD", "mjd"), ("Original cutout URL", "cutout_url")):
        lines.append(f"| {label} | {_cell(inputs[0].get(key))} | {_cell(inputs[1].get(key))} |")
    lines.append(f"| FITS content SHA-256 | {_cell(inputs[0]['fits_content'].get('sha256'))} | {_cell(inputs[1]['fits_content'].get('sha256'))} |")
    lines.extend(["", "## 3. Registration, Processing and Quality", "",
        f"- Registration method: `{dossier['registration'].get('method', 'NOT_RECORDED')}` (configured engine: `reproject_interp`).",
        f"- Usable overlap fraction: {_display(dossier['registration'].get('overlap_fraction'))}",
        f"- Required minimum overlap: {_display(validity.get('min_overlap_fraction'))}"])
    for epoch, metadata in (dossier.get("data_quality") or {}).items():
        quality, variance = metadata["quality"], metadata["variance"]
        lines.extend([f"- {epoch}: FLAGS `{quality['status']}`, source `{quality['definitions_source']}`; variance `{variance['provenance']}`.",
                      f"- {epoch} named mask counts: `{json.dumps(quality['mask_counts'], sort_keys=True)}`"])
    lines.extend(["", "## 4. Difference Imaging", ""])
    statistics = dossier.get("difference_statistics")
    if statistics is None:
        lines.append("Difference imaging, source extraction and motion assessment were not run. Original frames are for visual inspection only.")
    else:
        lines.extend(["D = I2_registered - I1; Var(D) = Var(I1) + Var(I2_registered).",
                      "Statistics use valid masked pixels and diagonal independent-exposure variance.",
                      "```json", json.dumps(statistics, sort_keys=True, indent=2, ensure_ascii=False), "```"])
    lines.extend(["", "## 5. Residual Sources", ""])
    if not dossier["sources"]:
        lines.append("No residual components reported. This does not establish the absence of astrophysical variability or motion.")
    else:
        lines.extend(["| Source | RA, Dec (deg) | Peak significance | Classification | Evidence |", "| --- | --- | --- | --- | --- |"])
        for source in dossier["sources"]:
            lines.append(f"| {_cell(source.get('source_id'))} | {_cell(source.get('ra_deg'))}, {_cell(source.get('dec_deg'))} | {_cell(source.get('peak_significance'))} | {_cell(source.get('classification'))} | {_cell(source.get('classification_rationale'))} |")
    motion = dossier.get("motion_analysis") or {}
    lines.extend(["", "## 6. Independent Epoch Source Associations", "",
        f"- Motion analysis status: `{motion.get('status', 'NOT_EVALUATED')}`",
        f"- Stationary references: {_display(motion.get('reference_source_count'), 0)}",
        f"- Relative registration error (arcsec): {_display(motion.get('registration_error_arcsec'))}",
        "", "| Epoch 1 source | Epoch 2 source | Displacement (arcsec) | Uncertainty (arcsec) | Classification | Evidence |",
        "| --- | --- | --- | --- | --- | --- |"])
    for association in motion.get("associations", []):
        first, second = association.get("epoch_1_source") or {}, association.get("epoch_2_source") or {}
        lines.append(f"| {_cell(first.get('source_id'))} | {_cell(second.get('source_id'))} | {_cell(association.get('angular_displacement_arcsec'))} | {_cell(association.get('displacement_uncertainty_arcsec'))} | {_cell(association.get('classification'))} | {_cell(association.get('rationale'))} |")
    lines.extend(["", "## 7. Known Limitations", ""] + [f"- {item}" for item in dossier["scientific_limitations"]])
    lines.extend(["", "## 8. Machine-Readable Evidence", "",
        "This block is the same JSON dossier exported separately. The manifest records full WCS, hashes, processing parameters and software versions.",
        "Generation time and Markdown formatting are excluded from both stable digests. Hashes identify content; they do not authenticate an archive or validate an astronomical claim.",
        "```json", json.dumps({key: value for key, value in dossier.items() if key != "markdown_report"},
                              sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False), "```"])
    return "\n".join(lines)


def generate_evidence_dossier(obs1, obs2, diff_data: Dict[str, Any], reg_diag: Dict[str, Any],
    sources: List[Dict[str, Any]], candidate_eval: Dict[str, Any], dt_days: float,
    motion_analysis=None, comparison_validity=None, data_quality=None,
    input_models=None, processing_context=None):
    return _build_dossier(obs1, obs2, diff_data, reg_diag, sources, candidate_eval, dt_days,
                          motion_analysis, comparison_validity, data_quality, input_models, processing_context)


def generate_visual_comparison_dossier(obs1, obs2, validity, diagnostics, data_quality=None,
                                       *, input_models=None, processing_context=None, motion_analysis=None):
    candidate = {"category": "INSUFFICIENT_EVIDENCE", "detected": False, "peak_sig": None}
    if motion_analysis is None:
        motion_analysis = {"status": "INSUFFICIENT_EVIDENCE", "inputs_valid": False,
            "failure_reasons": [item["message"] for item in validity["failure_reasons"]],
            "parameters": (processing_context or {}).get("source_matching", {}),
            "epoch_1_sources": [], "epoch_2_sources": [], "associations": [],
            "reference_source_count": 0, "reference_frame_verified": False, "registration_error_arcsec": None}
    return _build_dossier(obs1, obs2, None, diagnostics, [], candidate,
        abs(obs2.obs_time_mjd-obs1.obs_time_mjd), motion_analysis, validity, data_quality, input_models, processing_context)
