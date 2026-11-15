"""Deployment paths, production environment precedence, and exact FITS restoration."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

BACKEND = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('deployment_data', BACKEND / 'scripts' / 'deployment_data.py')
deployment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deployment)


def test_production_config_uses_backend_data_and_hosted_gemini_environment(tmp_path):
    env = dict(os.environ, ENVIRONMENT='production', GEMINI_MODEL='hosted-model', GEMINI_API_KEY='test-hosted-value',
               SPHEREX_CACHE_DIR=str(tmp_path / 'cache'), PYTHONPATH=str(BACKEND))
    env.pop('SPHEREX_DATA_DIR', None)
    code = "from app.config import BASE_DIR,DATA_DIR,CACHE_DIR; import os,json; print(json.dumps({'base':str(BASE_DIR),'data':str(DATA_DIR),'cache':str(CACHE_DIR),'model':os.getenv('GEMINI_MODEL'),'hosted_key_preserved':os.getenv('GEMINI_API_KEY')=='test-hosted-value'}))"
    result = subprocess.run([sys.executable, '-c', code], cwd=tmp_path, env=env, capture_output=True, text=True, check=True)
    values = json.loads(result.stdout)
    assert Path(values['base']) == BACKEND
    assert Path(values['data']) == BACKEND / 'data'
    assert Path(values['cache']) == tmp_path / 'cache'
    assert values['model'] == 'hosted-model' and values['hosted_key_preserved']


def test_exact_fits_bundle_restores_all_existing_products(tmp_path):
    deployment.restore(tmp_path)
    manifest = json.loads((deployment.BUNDLE / 'manifest.json').read_text())
    assert len(manifest['products']) == 38
    assert len(manifest['unavailable_products']) == 3
    for record in manifest['products']:
        path = tmp_path / record['filename']
        assert path.stat().st_size == record['byte_count']
        assert deployment.hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']
    deployment.restore(tmp_path)  # repeat deploy does not replace matching data


def test_restore_refuses_conflicting_cache_bytes(tmp_path):
    manifest = json.loads((deployment.BUNDLE / 'manifest.json').read_text())
    original = tmp_path / manifest['products'][0]['filename']
    original.write_bytes(b'existing-unexpected-data')
    with pytest.raises(ValueError, match='refusing to overwrite'):
        deployment.restore(tmp_path)
    assert original.read_bytes() == b'existing-unexpected-data'


def test_restore_rejects_corrupted_bundle(tmp_path):
    manifest = json.loads((deployment.BUNDLE / 'manifest.json').read_text())
    first = manifest['products'][0]
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    (bundle / 'manifest.json').write_text(json.dumps(manifest))
    (bundle / (first['filename'] + '.gz')).write_bytes(deployment.gzip.compress(b'corrupt-data'))
    with pytest.raises(ValueError, match='integrity check failed'):
        deployment.restore(tmp_path / 'cache', bundle_dir=bundle)
