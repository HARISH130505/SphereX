import inspect

from fastapi.testclient import TestClient

from app.main import app
from app.services.astronomy import fits_io


client = TestClient(app)


def test_spectral_highest_flux_uses_microjansky_field():
    body = client.get("/api/spectral/m101").json()
    assert body["highest_flux_point"]["flux_ujy"] == max(point["flux_ujy"] for point in body["points"])


def test_candidate_simulator_applies_selected_fatal_pixel_tolerance():
    base = {"center_finite": True, "center_flags_raw": 0, "aperture_fatal_count": 2,
            "aperture_total_pixels": 29, "bg_usable_pixels": 128,
            "variance_available": True, "target_inside": True}
    rejected = client.post("/api/candidates/evaluate", json={**base, "aperture_fatal_tolerance": 1}).json()
    accepted = client.post("/api/candidates/evaluate", json={**base, "aperture_fatal_tolerance": 2}).json()
    assert rejected["status"] == "REJECTED_SIMULATED_TOLERANCE"
    assert not rejected["usable"]
    assert accepted["status"] == "FEASIBLE_WITH_CAVEATS"
    assert accepted["usable"]


def test_archive_download_does_not_disable_tls_verification():
    source = inspect.getsource(fits_io.fetch_or_load_fits_file)
    assert "CERT_NONE" not in source
    assert "check_hostname = False" not in source
    assert "verify=False" not in source
