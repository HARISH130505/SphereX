"""Retrieve bounded real archive products and retain only validated demo pairs."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
import numpy as np
from app.config import DEMO_DIR
from app.schemas.observation import ObservationSchema
from app.services.astronomy.fits_io import load_fits_image, get_fits_cache_path
from app.services.astronomy.registration import register_observation_pair
from app.services.astronomy.comparison_validity import evaluate_comparison_validity

root = Path(__file__).resolve().parents[1]
discovery = json.loads((root/'data/demo_discovery.json').read_text())
destination = DEMO_DIR/'verified_targets.json'
output = json.loads(destination.read_text()) if destination.exists() else {}
for name in ('M51', 'M81', 'M33', 'NGC 253', 'NGC 2403', 'NGC 6946'):
    if name in output or name not in discovery:
        continue
    ra, dec = discovery[name]['coordinates']
    rows = [r for c in discovery[name]['collections'].values() for r in c['rows']]
    rows.sort(key=lambda r: (r['obs_collection'] != 'spherex_qr3', r['energy_bandpassname'], float(r['t_min'])))
    accepted = []
    for row in rows[:12]:
        url = row['access_url'] + f'?center={ra},{dec}&size=0.12'
        obs = ObservationSchema(obs_id=row['obs_collection']+'_'+row['obs_id'],
            obs_publisher_did=row['obs_publisher_did'], target=name,
            band=row['energy_bandpassname'], obs_time_mjd=float(row['t_min']),
            ra=ra, dec=dec, cutout_url=url, download_status='SUCCESS', fits_valid=True,
            extensions_found='', image_shape='', target_inside_cutout=False,
            center_pixel_finite=False, screening_status='FEASIBLE_WITH_CAVEATS', rejection_reason='')
        try:
            model = load_fits_image(obs)
            x,y = model['wcs'].celestial.world_to_pixel_values(ra,dec)
            valid = model['valid_mask']
            if not (0 <= x < valid.shape[1] and 0 <= y < valid.shape[0]) or valid.mean() < .6:
                continue
            obs.target_inside_cutout=True
            obs.image_shape=str(valid.shape)
            obs.center_pixel_finite=bool(np.isfinite(model['image'][int(y),int(x)]))
            for previous, old_model in accepted:
                if previous.band != obs.band or previous.obs_time_mjd == obs.obs_time_mjd:
                    continue
                registration=register_observation_pair(old_model,model)
                validity=evaluate_comparison_validity(previous,obs,old_model,model,registration)
                if validity['scientific_analysis_allowed']:
                    output[name]={'ra':ra,'dec':dec,'observations':[previous.model_dump(),obs.model_dump()],
                                  'comparison_validity':validity}
                    destination.write_text(json.dumps(output,indent=2),encoding='utf-8')
                    print('VALIDATED',name, previous.product_id,obs.product_id,validity,flush=True)
                    break
            if name in output:
                break
            accepted.append((obs,model))
            print('IMAGE',name,obs.product_id,float(valid.mean()),flush=True)
        except Exception as error:
            print('FAILED',name,obs.obs_id,str(error)[:200],flush=True)
    if len(output)>=3:
        break
