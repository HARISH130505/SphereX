"""Package/restore exact existing NASA FITS bytes for reproducible Render builds.

No archive requests and no image generation. Uses only Python's standard library.
Local `pack` reads the active catalog/cache; Render's build uses `restore`.
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
BUNDLE = DATA / 'deployment_fits'
CATALOG = DATA / 'demo'
MAX_FILE_BYTES = 128 * 1024 * 1024


def catalog_records():
    with (CATALOG / 'screening_results.csv').open(encoding='utf-8-sig', newline='') as source:
        records = list(csv.DictReader(source))
    for entry in json.loads((CATALOG / 'verified_targets.json').read_text(encoding='utf-8')).values():
        if entry.get('comparison_validity', {}).get('scientific_analysis_allowed'):
            records.extend(entry['observations'])
    return records


def cache_filename(record):
    return f"{record['obs_id']}_{record['band']}.fits".replace('/', '_').replace(':', '_')


def pack(cache_dir):
    records = catalog_records()
    manifest = {'format': 'spherex-exact-fits-v1', 'products': [], 'unavailable_products': []}
    # Known failed retrievals stay explicit catalog limitations; never invent files.
    missing = [row for row in records if not (cache_dir / cache_filename(row)).is_file()]
    unexpected = [cache_filename(row) for row in missing if row.get('screening_status') != 'FAILED_DOWNLOAD']
    if unexpected:
        raise ValueError(f'Missing genuine cache files for otherwise available products: {unexpected}')
    manifest['unavailable_products'] = [{'filename':cache_filename(row), 'target':row['target'],
        'obs_id':row['obs_id'], 'band':row['band'], 'status':'HISTORICAL_DOWNLOAD_FAILED'} for row in missing]
    BUNDLE.mkdir(parents=True, exist_ok=True)
    for row in records:
        filename = cache_filename(row)
        if not (cache_dir / filename).is_file():
            continue
        content = (cache_dir / filename).read_bytes()
        if not content.startswith(b'SIMPLE') or not 1000 < len(content) <= MAX_FILE_BYTES:
            raise ValueError(f'Not a bounded FITS file: {filename}')
        (BUNDLE / (filename + '.gz')).write_bytes(gzip.compress(content, compresslevel=9, mtime=0))
        manifest['products'].append({'filename': filename, 'obs_id': row['obs_id'], 'band': row['band'],
            'target': row['target'], 'archive_url': row['cutout_url'],
            'obs_publisher_did': row.get('obs_publisher_did') or None,
            'byte_count': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
    (BUNDLE / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    size = sum(path.stat().st_size for path in BUNDLE.iterdir() if path.is_file())
    print(f'Packaged {len(manifest["products"])} genuine FITS files: {size / 1024**2:.2f} MiB compressed. {len(missing)} historical failed downloads retained as unavailable. Original cache unchanged.')


def restore(cache_dir, bundle_dir=BUNDLE):
    manifest = json.loads((bundle_dir / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 'spherex-exact-fits-v1':
        raise ValueError('Unsupported deployment FITS manifest')
    expected = {cache_filename(row) for row in catalog_records()}
    if {row['filename'] for row in manifest['products'] + manifest.get('unavailable_products', [])} != expected:
        raise ValueError('Deployment FITS bundle does not match the active catalog. Re-run pack locally.')
    cache_dir.mkdir(parents=True, exist_ok=True)
    for row in manifest['products']:
        filename = row['filename']
        if Path(filename).name != filename or '/' in filename or '\\' in filename or not filename.endswith('.fits'):
            raise ValueError('Invalid deployment cache filename')
        if not 1000 < row['byte_count'] <= MAX_FILE_BYTES:
            raise ValueError(f'Invalid byte count: {filename}')
        destination = cache_dir / filename
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() == row['sha256']:
                continue
            raise ValueError(f'Existing cache differs; refusing to overwrite genuine data: {filename}')
        with gzip.open(bundle_dir / (filename + '.gz'), 'rb') as source:
            content = source.read(row['byte_count'] + 1)
        if len(content) != row['byte_count'] or hashlib.sha256(content).hexdigest() != row['sha256']:
            raise ValueError(f'Deployment FITS integrity check failed: {filename}')
        temporary = destination.with_suffix('.restore')
        temporary.write_bytes(content)
        temporary.replace(destination)
    print(f'Verified/restored {len(manifest["products"])} genuine FITS products into {cache_dir}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('pack', 'restore'))
    parser.add_argument('--cache-dir', type=Path, default=Path(os.getenv('SPHEREX_CACHE_DIR', str(DATA / 'cache'))))
    arguments = parser.parse_args()
    if arguments.action == 'pack':
        pack(arguments.cache_dir)
    else:
        restore(arguments.cache_dir)
