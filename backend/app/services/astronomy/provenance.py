"""Versioned canonical SHA-256 identity for scientific inputs and processing."""
from dataclasses import asdict
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
import math
from pathlib import Path
import platform
from typing import Any
import numpy as np
from app.services.product_identity import product_id, archive_product_id
from app.services.astronomy.detection import DEFAULT_RESIDUAL_THRESHOLD_SIGMA, DEFAULT_RESIDUAL_MIN_PIXELS
from app.services.astronomy.source_matching import DEFAULT_MATCHING_PARAMETERS
from app.services.astronomy.quality import POLICY_VERSION, INFORMATIONAL_FLAGS, BRIGHTNESS_THRESHOLD_MJY_SR
from app.services.astronomy.registration import WCS_ROUNDTRIP_TOLERANCE_PIXEL
from app.services.astronomy.resampling import INTEGER_SNAP_TOLERANCE_PIXEL

MANIFEST_SCHEMA = "spherex-evidence-manifest-v1"
CANONICALIZATION = "spherex-canonical-json-v1"
PIPELINE_VERSION = "2.1.0"
PIPELINE_NAME = "SPHEREx-Explorer Multi-Epoch Evidence Engine"


def normalize(value: Any):
    """Strict JSON types; explicit nonfinite tags; reject repr()/object identities."""
    if isinstance(value, np.ndarray):
        return normalize(value.tolist())
    if isinstance(value, np.generic):
        return normalize(value.item())
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return {"__nonfinite_float__": "nan" if math.isnan(value) else ("+inf" if value > 0 else "-inf")}
        return 0.0 if value == 0 else value
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Canonical JSON requires string dictionary keys")
        return {key: normalize(item) for key, item in value.items()}
    raise TypeError(f"Unsupported canonical value type: {type(value).__name__}")


def canonical_json(value) -> str:
    return json.dumps(normalize(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def sha256_json(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def array_record(array):
    if array is None:
        return {"status": "ABSENT", "sha256": None}
    array = np.asarray(array)
    if array.dtype.kind not in "biufc":
        return {"status": "UNSUPPORTED_DTYPE", "sha256": None, "dtype": str(array.dtype)}
    dtype = array.dtype.newbyteorder("<")
    contiguous = np.ascontiguousarray(array.astype(dtype, copy=False))
    metadata = {"shape": list(array.shape), "dtype": dtype.str, "order": "C"}
    digest = hashlib.sha256(canonical_json(metadata).encode("utf-8") + b"\0" + contiguous.tobytes()).hexdigest()
    return {"status": "AVAILABLE", "sha256": digest, **metadata}


def wcs_record(model):
    if model is None or model.get("wcs") is None:
        return {"status": "ABSENT", "header": None}
    try:
        header = model["wcs"].celestial.to_header(relax=True)
        return {"status": "SERIALIZED", "header": header.tostring(sep="\n", endcard=False, padding=False)}
    except Exception as exc:
        return {"status": "INVALID", "header": None, "error_type": type(exc).__name__}


def observation_record(obs):
    return {"obs_id": obs.obs_id, "product_id": product_id(obs.obs_id, obs.band),
            "archive_product_id": archive_product_id(obs.cutout_url, getattr(obs, "obs_publisher_did", None)),
            "cutout_url": obs.cutout_url, "target": obs.target, "band": obs.band,
            "mjd": obs.obs_time_mjd, "date_iso": getattr(obs, "obs_time_iso", None),
            "ra_deg": getattr(obs, "ra", None), "dec_deg": getattr(obs, "dec", None),
            "screening_status": getattr(obs, "screening_status", None),
            "fits_valid": getattr(obs, "fits_valid", None),
            "collection": getattr(obs, 'collection', None),
            "archive_obs_id": getattr(obs, 'archive_obs_id', None),
            "access_url": getattr(obs, 'access_url', None),
            "footprint": getattr(obs, 'footprint', None)}


def input_record(obs, model):
    record = observation_record(obs)
    model = model or {}
    record.update(fits_content=model.get("fits_provenance", {"status": "UNAVAILABLE", "sha256": None, "byte_count": None}),
                  native_wcs=wcs_record(model),
                  native_arrays={key: array_record(model.get(key)) for key in ("image", "variance", "flags_raw", "valid_mask")},
                  target_pixel_xy=model.get("target_xy"),
                  image_unit=model.get("bunit"), variance_unit=model.get("var_bunit"),
                  variance_provenance=model.get("variance_provenance", "UNVERIFIED"),
                  quality_configuration=model.get("quality_summary"),
                  variance_configuration=model.get("variance_summary"))
    return normalize(record)


def software_record():
    packages = ("numpy", "astropy", "scipy", "reproject", "astropy-iers-data", "pyerfa",
                "dask", "dask-image", "fastapi", "pydantic", "Pillow", "matplotlib")
    dependencies = {}
    for name in packages:
        try:
            dependencies[name] = version(name)
        except PackageNotFoundError:
            dependencies[name] = "NOT_INSTALLED"
    app_root = Path(__file__).resolve().parents[2]
    source_files = {"app/" + path.relative_to(app_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted(app_root.rglob("*.py"))}
    return {"pipeline": PIPELINE_NAME, "pipeline_version": PIPELINE_VERSION,
            "python_version": platform.python_version(), "python_implementation": platform.python_implementation(),
            "platform": {"system": platform.system(), "machine": platform.machine()},
            "dependencies": dependencies, "source_files_sha256": source_files,
            "source_tree_sha256": sha256_json(source_files)}


def processing_configuration(request, validity, diagnostics, *, motion_analysis=None, pixel_scale_arcsec=None):
    matching = asdict(DEFAULT_MATCHING_PARAMETERS)
    if motion_analysis:
        matching.update(motion_analysis.get("parameters", {}))
    allowed = validity["scientific_analysis_allowed"]
    return {"configuration_status": "RECORDED", "scientific_steps_executed": allowed,
        "executed_steps": ["fits_loading", "registration_attempt", "visual_rendering"] + (["difference", "residual_detection", "native_epoch_sources", "source_association", "candidate_assessment"] if allowed else []),
        "reference_grid": "epoch_1", "registration": {
            "method": diagnostics.get("method"), "science_interpolation": "bilinear",
            "variance_resampling": "sum_squared_bilinear_weights", "mask_resampling": "OR_nonzero_contributors",
            "wcs_roundtrip_tolerance_pixel": WCS_ROUNDTRIP_TOLERANCE_PIXEL,
            "integer_snap_tolerance_pixel": INTEGER_SNAP_TOLERANCE_PIXEL,
            "reference_shape": diagnostics.get("reference_shape"), "source_shape": diagnostics.get("source_shape"),
            "min_overlap_fraction": validity["min_overlap_fraction"],
            "overlap_definition": validity.get("overlap_definition"), "reference_direction": "epoch_2_to_epoch_1"},
        "difference": {"formula": "I2_registered - I1", "variance_formula": "Var(I1) + Var(I2_registered)",
            "required_variance_provenance": "MEASURED", "variance_floor": None,
            "brightness_threshold_mjy_sr": BRIGHTNESS_THRESHOLD_MJY_SR,
            "output_pixel_covariance_modeled": False},
        "residual_detection": {"threshold_sigma": DEFAULT_RESIDUAL_THRESHOLD_SIGMA,
            "min_pixels": DEFAULT_RESIDUAL_MIN_PIXELS, "connectivity": 4,
            "polarity": "absolute_significance", "pixel_scale_arcsec": pixel_scale_arcsec},
        "source_matching": matching,
        "quality_mask": {"policy_version": POLICY_VERSION, "informational_flags": sorted(INFORMATIONAL_FLAGS),
            "unknown_bits": "EXCLUDE", "missing_or_unverified_flags": "BLOCK_SCIENCE"},
        "presentation": {"stretch": request.stretch, "difference_colormap": request.colormap,
            "epoch_colormap": "plasma", "significance_colormap": "inferno", "png_scale_factor": 6}}


def make_reproducibility(obs1, obs2, models, processing, generated_at):
    models = models if models is not None else (None, None)
    inputs = [input_record(obs, model) for obs, model in zip((obs1, obs2), models)]
    if len(inputs) != 2:
        raise ValueError("Two epoch input records are required")
    missing_hashes = [index for index, row in enumerate(inputs, 1) if not row["fits_content"].get("sha256")]
    provenance_status = "COMPLETE" if not missing_hashes and processing is not None and processing.get("configuration_status") == "RECORDED" else "PARTIAL"
    manifest = normalize({"schema_version": MANIFEST_SCHEMA, "canonicalization": CANONICALIZATION,
        "inputs": inputs, "processing": processing or {"configuration_status": "NOT_PROVIDED"},
        "software": software_record()})
    digest = sha256_json(manifest)
    return {"algorithm": "SHA-256", "canonicalization": CANONICALIZATION,
        "pipeline": PIPELINE_NAME, "pipeline_version": PIPELINE_VERSION,
        "provenance_status": provenance_status, "missing_fits_hash_epochs": missing_hashes,
        "generated_at_utc": generated_at, "manifest": manifest, "manifest_sha256": digest,
        "reproducibility_hash": "spx-sha256-" + digest}


EVIDENCE_FIELDS = ("assessment", "candidate_assessment", "comparison_validity", "provenance", "data_quality",
                   "registration", "difference_statistics", "sources", "motion_analysis", "scientific_limitations")


def evidence_content(dossier):
    return {"manifest_sha256": dossier["reproducibility"]["manifest_sha256"],
            **{key: dossier.get(key) for key in EVIDENCE_FIELDS}}


def seal_dossier(dossier):
    dossier = normalize(dossier)
    dossier["reproducibility"]["evidence_hash_fields"] = list(EVIDENCE_FIELDS)
    dossier["reproducibility"]["evidence_sha256"] = sha256_json(evidence_content(dossier))
    return dossier


def verify_dossier(dossier) -> bool:
    try:
        reproducibility = dossier["reproducibility"]
        digest = sha256_json(reproducibility["manifest"])
        return (reproducibility["algorithm"] == "SHA-256" and
                reproducibility["canonicalization"] == CANONICALIZATION and
                reproducibility["manifest"].get("schema_version") == MANIFEST_SCHEMA and
                reproducibility["manifest"].get("canonicalization") == CANONICALIZATION and
                reproducibility["manifest_sha256"] == digest and
                reproducibility["reproducibility_hash"] == "spx-sha256-" + digest and
                dossier["dossier_id"] == "spx-sha256-" + digest and
                reproducibility["evidence_hash_fields"] == list(EVIDENCE_FIELDS) and
                reproducibility["evidence_sha256"] == sha256_json(evidence_content(dossier)))
    except (KeyError, ValueError, TypeError):
        return False
