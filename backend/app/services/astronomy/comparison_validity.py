"""Necessary comparison guards; passing them is not astrophysical validation."""
import numpy as np
from app.config import MIN_COMPARISON_OVERLAP
from app.services.product_identity import product_id
from app.services.astronomy.registration import celestial_wcs_error


def metadata_failures(obs1, obs2):
    failures = []
    def fail(code, message):
        failures.append({"code": code, "message": message})
    if obs1.target.casefold() != obs2.target.casefold():
        fail("TARGET_MISMATCH", "Comparison products must belong to the same target.")
    same_key = product_id(obs1.obs_id, obs1.band) == product_id(obs2.obs_id, obs2.band)
    archive1, archive2 = getattr(obs1, "archive_product_id", None), getattr(obs2, "archive_product_id", None)
    if same_key or (archive1 and archive1 == archive2):
        fail("SAME_PRODUCT", "Two distinct observation products are required.")
    if obs1.band != obs2.band or obs1.band in ('UNKNOWN', 'UNKNOWN BAND', ''):
        fail("INCOMPATIBLE_BANDS", "Scientific comparison requires the same spectral band.")
    dt = obs2.obs_time_mjd - obs1.obs_time_mjd
    if not np.isfinite(dt) or dt == 0:
        fail("INVALID_EPOCH_BASELINE", "Two distinct finite observation epochs are required.")
    return failures


def evaluate_comparison_validity(obs1, obs2, m1, m2, registration,
                                 min_overlap_fraction=MIN_COMPARISON_OVERLAP):
    if not np.isfinite(min_overlap_fraction) or not 0 < min_overlap_fraction <= 1:
        raise ValueError("Minimum overlap must be finite and in (0, 1]")
    failures = metadata_failures(obs1, obs2)
    diag = registration["diagnostics"]
    if not diag.get("wcs_aligned"):
        failures.append({"code": "REGISTRATION_FAILED", "message": diag.get("warning", "Celestial registration did not succeed.")})
    overlap = diag.get("overlap_fraction", 0)
    if not np.isfinite(overlap) or overlap < min_overlap_fraction:
        failures.append({"code": "INSUFFICIENT_OVERLAP", "message": f"Usable overlap must be at least {min_overlap_fraction:.1%} of the reference grid."})
    for index, (model, obs) in enumerate(((m1, obs1), (m2, obs2)), 1):
        wcs_error = celestial_wcs_error(model)
        if wcs_error:
            failures.append({"code": "INVALID_WCS", "message": f"Epoch {index}: {wcs_error}"})
        if model.get("quality_verified") is not True:
            failures.append({"code": "UNVERIFIED_QUALITY_FLAGS", "message": f"Epoch {index} FLAGS plane or definitions are missing/unverified."})
        if model.get("science_units_verified") is not True:
            failures.append({"code": "UNVERIFIED_SCIENCE_UNITS", "message": f"Epoch {index} science/variance units are unverified."})
        if model.get("variance_provenance") != "MEASURED":
            failures.append({"code": "UNVERIFIED_VARIANCE", "message": f"Epoch {index} requires measured variance for scientific analysis."})
        if obs.screening_status not in {"PASSED_CLEAN", "FEASIBLE_WITH_CAVEATS"}:
            failures.append({"code": "PRODUCT_QUALITY_BLOCKED", "message": f"Epoch {index} screening status is {obs.screening_status}."})
    return {"status": "VALID_FOR_REGISTERED_COMPARISON" if not failures else "NON_SCIENTIFIC_VISUAL_COMPARISON",
            "scientific_analysis_allowed": not failures, "failure_reasons": failures,
            "min_overlap_fraction": min_overlap_fraction,
            "overlap_fraction": float(overlap) if np.isfinite(overlap) else None,
            "overlap_definition": "quality-valid science and measured positive variance in both epochs / all epoch-1 pixels"}
