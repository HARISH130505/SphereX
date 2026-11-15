"""Bounded checks through the running Next proxy, using genuine existing products."""
import requests
from urllib.parse import quote
BASE='http://127.0.0.1:3000/api'

def main():
    with requests.Session() as session:
        targets=session.get(BASE+'/sky/targets',timeout=30).json()
        expected={'M101','M51','M33','NGC 253','Mira','Delta Cephei','Algol'}
        assert {t['name'] for t in targets}==expected
        print('PREDEFINED_SELECTOR', [t['name'] for t in targets],flush=True)
        assert session.post(BASE+'/sky/explore',json={},timeout=15).status_code==404
        for target in ('M101','M51','M33','NGC 253'):
            response=session.get(BASE+'/sky/observations',params={'target':target},timeout=30)
            response.raise_for_status()
            rows=response.json()
            print('CATALOG',target,len(rows),flush=True)
            usable=[r for r in rows if r['fits_valid']]
            pair=next(((a,b) for i,a in enumerate(usable) for b in usable[i+1:] if a['band']==b['band'] and a['obs_time_mjd']!=b['obs_time_mjd']),None)
            for row in pair or usable[:1]:
                response=session.get(BASE+'/sky/cutout/'+quote(row['product_id'],safe=''),timeout=60)
                data=response.json()
                assert response.status_code==200 and data.get('fits_valid') and data.get('png_base64')
                print('FITS',target,row['product_id'],response.status_code,len(data.get('png_base64','')),flush=True)
            if pair:
                response=session.post(BASE+'/epoch/compare',json={'epoch_1_product_id':pair[0]['product_id'],'epoch_2_product_id':pair[1]['product_id']},timeout=90)
                data=response.json()
                assert response.status_code==200 and data['comparison_validity']['scientific_analysis_allowed']
                assert data['difference_image_base64'] and data['significance_image_base64']
                assert data['evidence_dossier'] and data['evidence_report_markdown']
                print('COMPARE_EXPORT',target,response.status_code,data.get('comparison_validity',{}).get('scientific_analysis_allowed'),len(data.get('evidence_report_markdown','')),flush=True)

if __name__=='__main__': main()
