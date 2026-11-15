"""Identity regressions using the actual catalog and cached FITS, plus isolated cache tests."""
from collections import Counter
from urllib.parse import quote, urlsplit
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.storage.repository import repository
from app.services.product_identity import AmbiguousObservationError, product_id
from app.services.astronomy import fits_io


def test_all_duplicate_legacy_ids_are_rejected_and_unique_ids_stay_compatible():
    counts = Counter(o.obs_id for o in repository.get_all())
    assert any(n > 1 for n in counts.values())
    for o in repository.get_all():
        assert repository.get_by_id(o.product_id) is o
        if counts[o.obs_id] > 1:
            with pytest.raises(AmbiguousObservationError) as error:
                repository.get_by_id(o.obs_id)
            assert o.product_id in error.value.product_ids
        else:
            assert repository.get_by_id(o.obs_id) is o


def test_identity_and_archive_provenance_are_separate():
    records = repository.get_all()
    assert len({o.product_id for o in records}) == len(records)
    for o in records:
        data = o.model_dump()
        assert data["product_id"] == product_id(o.obs_id, o.band)
        if o.obs_publisher_did:
            assert o.archive_product_id == o.obs_publisher_did
        else:
            assert urlsplit(o.archive_product_id).path == urlsplit(o.cutout_url).path
            assert "?" not in o.archive_product_id
        assert data["obs_id"] == o.obs_id
    original = records[0].model_copy(update={"obs_publisher_did": "ivo://archive/original-product"})
    assert original.archive_product_id == "ivo://archive/original-product"


def test_product_components_cannot_collide_at_separator():
    assert product_id("a::b", "c") != product_id("a", "b::c")


@pytest.mark.parametrize("endpoint", ["cutout", "comparison"])
def test_ambiguous_api_requests_rejected_before_fits_loading(monkeypatch, endpoint):
    from app.api.routes import images, comparisons
    monkeypatch.setattr(images, "load_fits_image", lambda *a: pytest.fail("Must reject before loading"))
    monkeypatch.setattr(comparisons, "load_fits_image", lambda *a: pytest.fail("Must reject before loading"))
    with TestClient(app) as client:
        if endpoint == "cutout":
            response = client.get("/api/sky/cutout/2026W32_2A_0147_1")
        else:
            response = client.post("/api/epoch/compare", json={
                "epoch_1_obs_id": "2026W32_2A_0147_1", "epoch_2_obs_id": "TAP_M101_221"})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "AMBIGUOUS_OBSERVATION_ID"
    assert "2026W32_2A_0147_1::SPHEREx-D4" in detail["product_ids"]


def test_real_cutouts_resolve_exact_band_and_do_not_share_render_cache():
    with TestClient(app) as client:
        results = []
        for band in ["SPHEREx-D1", "SPHEREx-D4", "SPHEREx-D1"]:
            key = product_id("2026W32_2A_0147_1", band)
            response = client.get(f"/api/sky/cutout/{quote(key, safe='')}")
            assert response.status_code == 200
            data = response.json()
            assert data["band"] == band and data["product_id"] == key
            assert f"_{band}.fits" in data["source_file"]
            assert data["archive_product_id"] == repository.get_by_id(key).archive_product_id
            results.append(data)
    assert results[0]["image_shape"] == [44, 58]
    assert results[1]["image_shape"] == [55, 58]
    assert results[0] == results[2]
    assert results[0]["png_base64"] != results[1]["png_base64"]


def test_comparison_uses_selected_products_and_exports_identity():
    records = repository.get_all(target="Mira")
    pair = [o for o in records if o.band == "SPHEREx-D4"][:2]
    assert len(pair) == 2
    with TestClient(app) as client:
        response = client.post("/api/epoch/compare", json={
            "epoch_1_product_id": pair[0].product_id, "epoch_2_product_id": pair[1].product_id})
    assert response.status_code == 200, response.text[:300]
    data = response.json()
    for i, obs in enumerate(pair, 1):
        assert data[f"epoch_{i}_meta"]["product_id"] == obs.product_id
        assert data[f"epoch_{i}_meta"]["band"] == "SPHEREx-D4"
        provenance = data["evidence_dossier"]["provenance"][f"epoch_{i}"]
        assert provenance["archive_product_id"] == obs.archive_product_id
        assert provenance["product_id"] == obs.product_id
        assert obs.product_id in data["evidence_report_markdown"]


def test_timeline_and_catalog_issue_same_product_identity():
    with TestClient(app) as client:
        catalog = client.get("/api/sky/observations?target=Mira").json()
        timeline = client.get("/api/sky/timeline/Mira").json()["timeline"]
    by_id = {o["product_id"]: o for o in catalog}
    assert len(by_id) == len(catalog) == len(timeline)
    for row in timeline:
        assert row["archive_product_id"] == by_id[row["product_id"]]["archive_product_id"]


def test_conflicting_request_fields_rejected():
    with TestClient(app) as client:
        response = client.post("/api/epoch/compare", json={
            "epoch_1_product_id": "a", "epoch_1_obs_id": "b", "epoch_2_product_id": "c"})
    assert response.status_code == 422


def test_bandless_cache_is_never_used(monkeypatch, tmp_path):
    monkeypatch.setattr(fits_io, "CACHE_DIR", tmp_path)
    obs = repository.get_by_id("2026W32_2A_0147_1::SPHEREx-D4").model_copy(update={"cutout_url": ""})
    (tmp_path / f"{obs.obs_id}.fits").write_bytes(b"unverified" * 200)
    with pytest.raises(FileNotFoundError, match="No valid archive"):
        fits_io.fetch_or_load_fits_file(obs)
