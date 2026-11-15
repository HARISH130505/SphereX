"""
Unit tests for data storage repository.
"""
from app.services.storage.repository import repository

def test_load_m101_photometry():
    pts = repository.get_m101_photometry()
    assert len(pts) > 0
    assert pts[0]["wavelength_um"] >= 0.7

def test_repository_observations():
    obs = repository.get_all()
    assert len(obs) >= 35

def test_repository_targets():
    targets = repository.get_targets()
    assert len(targets) >= 4


def test_only_predefined_targets_are_exposed_and_search_routes_removed():
    from fastapi.testclient import TestClient
    from app.main import app
    expected = {'M101', 'M51', 'M33', 'NGC 253', 'Mira', 'Delta Cephei', 'Algol'}
    with TestClient(app) as client:
        targets = client.get('/api/sky/targets').json()
        assert {target['name'] for target in targets} == expected
        assert all(not target['id'].startswith('field-') for target in targets)
        assert client.post('/api/sky/explore', json={}).status_code == 404
        assert client.get('/api/sky/explore/jobs/old-job').status_code == 404
        assert client.post('/api/sky/explore/validate/old-product').status_code == 404
        assert client.get('/api/sky/observations', params={'target': 'field-old'}).status_code == 404
        for target in targets:
            if target['name'] in {'Mira', 'Delta Cephei', 'Algol'}:
                assert target['exploration_status'] != 'READY FOR EXPLORATION'
        assert all(record.target in expected for record in repository.get_all())


def test_qualified_product_ids_resolve_every_band():
    observations = repository.get_all()
    keys = [f"{o.obs_id}::{o.band}" for o in observations]
    assert len(keys) == len(set(keys))
    for observation, key in zip(observations, keys):
        assert repository.get_by_id(key) is observation


def test_qualified_product_id_never_falls_back_to_another_band():
    shared_id = "2026W32_2A_0147_1"
    assert repository.get_by_id(f"{shared_id}::SPHEREx-D1").band == "SPHEREx-D1"
    assert repository.get_by_id(f"{shared_id}::SPHEREx-D4").band == "SPHEREx-D4"
    assert repository.get_by_id(f"{shared_id}::UNKNOWN") is None
