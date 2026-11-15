"""Cold-cache deployment check: restore genuine bundled FITS; forbid archive calls."""
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from deployment_data import restore


def main():
    with tempfile.TemporaryDirectory(prefix='spherex-deployment-') as scratch:
        cache = Path(scratch) / 'cache'
        restore(cache)
        os.environ['ENVIRONMENT'] = 'production'
        os.environ['SPHEREX_CACHE_DIR'] = str(cache)
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from fastapi.testclient import TestClient
        from app.main import app
        with patch('requests.get', side_effect=AssertionError('Archive requests forbidden in deployment check')):
            with TestClient(app) as client:
                targets = client.get('/api/sky/targets').json()
                assert len(targets) == 7
                assert client.get('/api/health').status_code == 200
                for target in ('M101', 'M51', 'M33', 'NGC 253'):
                    rows = client.get('/api/sky/observations', params={'target':target}).json()
                    valid = [row for row in rows if row['fits_valid']]
                    a, b = next((a,b) for i,a in enumerate(valid) for b in valid[i+1:]
                                if a['band'] == b['band'] and a['obs_time_mjd'] != b['obs_time_mjd'])
                    for row in (a,b):
                        result = client.get('/api/sky/cutout/' + row['product_id'])
                        assert result.status_code == 200, result.text
                        assert result.json()['png_base64']
                    result = client.post('/api/epoch/compare', json={'epoch_1_product_id':a['product_id'], 'epoch_2_product_id':b['product_id']})
                    assert result.status_code == 200, result.text
                    evidence = result.json()
                    assert evidence['comparison_validity']['scientific_analysis_allowed']
                    assert evidence['difference_image_base64'] and evidence['significance_image_base64']
                    assert evidence['evidence_dossier'] and evidence['evidence_report_markdown']
                    print(f'PASS {target}: 2 genuine renders, valid difference/significance, dossier export; no archive download', flush=True)
                spectrum = client.get('/api/spectral/m101').json()
                assert spectrum['total_points'] == 370
                print('PASS 7 predefined targets; 370 genuine M101 photometry points; isolated writable cache', flush=True)


if __name__ == '__main__':
    main()
