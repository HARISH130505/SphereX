import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from app.api.routes.comparisons import compare_epochs
from app.schemas.comparison import EpochComparisonRequest
from app.services.astronomy.fits_io import get_fits_cache_path, load_fits_image
from app.services.astronomy.evidence import generate_visual_comparison_dossier
from app.services.astronomy.provenance import (
    CANONICALIZATION,
    MANIFEST_SCHEMA,
    array_record,
    canonical_json,
    make_reproducibility,
    normalize,
    verify_dossier,
)
from app.services.storage.repository import repository


def _request():
    return EpochComparisonRequest(
        epoch_1_obs_id=repository.get_by_id("TAP_M101_002").product_id,
        epoch_2_obs_id=repository.get_by_id("TAP_M101_221").product_id,
        stretch="asinh",
        colormap="coolwarm",
    )


def test_canonical_json_is_strict_stable_and_valid_json():
    left = {"z": np.float64(float("nan")), "a": np.int64(4), "zero": -0.0}
    right = {"zero": 0.0, "a": 4, "z": {"__nonfinite_float__": "nan"}}
    assert canonical_json(left) == canonical_json(right)
    assert json.loads(canonical_json(left))["a"] == 4
    with pytest.raises(TypeError):
        normalize(object())
    with pytest.raises(TypeError):
        canonical_json({1: "not a string key"})


def test_native_array_hash_is_independent_of_layout_and_endianness():
    native = np.arange(12, dtype="<f8").reshape(3, 4)
    big_endian_fortran = np.asfortranarray(native.astype(">f8"))
    assert array_record(native)["sha256"] == array_record(big_endian_fortran)["sha256"]
    changed = native.copy()
    changed[0, 0] = 99
    assert array_record(native)["sha256"] != array_record(changed)["sha256"]


def test_fits_hash_covers_exact_complete_file_snapshot():
    obs = repository.get_by_id("TAP_M101_002")
    model = load_fits_image(obs)
    source = get_fits_cache_path(obs.obs_id, obs.band)
    assert model["fits_provenance"] == {
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "byte_count": source.stat().st_size,
        "status": "AVAILABLE",
        "scope": "complete_fits_file_bytes",
    }


def test_manifest_changes_for_scientifically_relevant_inputs():
    obs1 = repository.get_by_id("TAP_M101_002")
    obs2 = repository.get_by_id("TAP_M101_221")
    model1, model2 = load_fits_image(obs1), load_fits_image(obs2)
    base = {
        "configuration_status": "RECORDED",
        "residual_detection": {"threshold_sigma": 5.0},
        "registration": {"min_overlap_fraction": 0.5},
    }
    first = make_reproducibility(obs1, obs2, (model1, model2), base, "time-a")
    second = make_reproducibility(obs1, obs2, (model1, model2), copy.deepcopy(base), "time-b")
    assert first["reproducibility_hash"] == second["reproducibility_hash"]
    assert first["manifest"]["schema_version"] == MANIFEST_SCHEMA
    assert first["canonicalization"] == CANONICALIZATION

    changed = copy.deepcopy(base)
    changed["residual_detection"]["threshold_sigma"] = 6.0
    changed_id = make_reproducibility(obs1, obs2, (model1, model2), changed, "time-c")
    assert changed_id["reproducibility_hash"] != first["reproducibility_hash"]

    altered_model = dict(model1)
    altered_model["image"] = np.array(model1["image"], copy=True)
    altered_model["image"][0, 0] += 1
    altered_id = make_reproducibility(obs1, obs2, (altered_model, model2), base, "time-d")
    assert altered_id["reproducibility_hash"] != first["reproducibility_hash"]


def test_real_dossier_is_sealed_and_markdown_embeds_same_json():
    response = compare_epochs(_request())
    dossier = response.evidence_dossier
    assert verify_dossier(dossier)
    assert dossier["reproducibility"]["provenance_status"] == "COMPLETE"
    assert re.fullmatch(r"spx-sha256-[0-9a-f]{64}", dossier["dossier_id"])
    inputs = dossier["reproducibility"]["manifest"]["inputs"]
    assert all(re.fullmatch(r"[0-9a-f]{64}", item["fits_content"]["sha256"]) for item in inputs)
    assert all(item["native_wcs"]["status"] == "SERIALIZED" for item in inputs)
    assert dossier["assessment"]["classification"] == dossier["candidate_assessment"]["category"]
    machine_json = response.evidence_report_markdown.split("```json")[-1].split("```", 1)[0].strip()
    expected = {key: value for key, value in dossier.items() if key != "markdown_report"}
    assert json.loads(machine_json) == expected


def test_tampering_is_detected():
    dossier = compare_epochs(_request()).evidence_dossier
    assert verify_dossier(dossier)
    modified = copy.deepcopy(dossier)
    modified["assessment"]["classification"] = "VARIABLE_SOURCE"
    assert not verify_dossier(modified)
    modified = copy.deepcopy(dossier)
    modified["reproducibility"]["manifest"]["processing"]["presentation"]["stretch"] = "linear"
    assert not verify_dossier(modified)


def test_visual_only_json_and_markdown_share_insufficient_evidence_verdict():
    def observation(name, mjd):
        return SimpleNamespace(
            obs_id=name, band="SPHEREx-D1", cutout_url=f"https://example.test/{name}.fits",
            target="M101", obs_time_mjd=mjd, obs_time_iso=None, ra=1.0, dec=2.0,
            screening_status="PASSED_CLEAN", fits_valid=True, obs_publisher_did=None,
        )
    validity = {
        "status": "NON_SCIENTIFIC_VISUAL_COMPARISON",
        "scientific_analysis_allowed": False,
        "failure_reasons": [{"code": "NO_OVERLAP", "message": "Insufficient celestial overlap."}],
        "min_overlap_fraction": 0.5,
        "overlap_fraction": 0.0,
        "overlap_definition": "usable celestial footprint",
    }
    processing = {"configuration_status": "RECORDED", "scientific_steps_executed": False,
                  "source_matching": {}}
    dossier = generate_visual_comparison_dossier(
        observation("A", 1.0), observation("B", 2.0), validity,
        {"method": "wcs_failed", "overlap_fraction": 0.0},
        input_models=(None, None), processing_context=processing,
    )
    assert dossier["assessment"]["classification"] == "INSUFFICIENT_EVIDENCE"
    assert dossier["candidate_assessment"]["category"] == "INSUFFICIENT_EVIDENCE"
    assert "`INSUFFICIENT_EVIDENCE`" in dossier["markdown_report"]
    assert verify_dossier(dossier)


def test_reproducibility_id_is_stable_across_python_processes(tmp_path):
    script = tmp_path / "check_id.py"
    script.write_text(
        'from app.api.routes.comparisons import compare_epochs\n'
        'from app.schemas.comparison import EpochComparisonRequest\n'
        'from app.services.storage.repository import repository\n'
        'a=repository.get_by_id("TAP_M101_002").product_id\n'
        'b=repository.get_by_id("TAP_M101_221").product_id\n'
        'r=compare_epochs(EpochComparisonRequest(epoch_1_obs_id=a,epoch_2_obs_id=b,stretch="asinh",colormap="coolwarm"))\n'
        'd=r.evidence_dossier\n'
        'print(d["dossier_id"], d["reproducibility"]["evidence_sha256"], sep="\\n")\n',
        encoding="utf-8",
    )
    backend = str(Path(__file__).resolve().parents[1])
    outputs = []
    for seed in ("17", "991"):
        env = os.environ.copy()
        env.update(PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=backend)
        completed = subprocess.run(
            [sys.executable, str(script)], cwd=tmp_path, env=env,
            text=True, capture_output=True, check=True, timeout=180,
        )
        outputs.append(completed.stdout.strip().splitlines())
    assert outputs[0] == outputs[1]
    assert re.fullmatch(r"spx-sha256-[0-9a-f]{64}", outputs[0][0])
