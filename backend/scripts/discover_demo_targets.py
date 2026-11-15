"""Bounded SPHEREx SIA discovery for submission demo candidates."""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import requests
from pathlib import Path

TARGETS = {
    "M51": (202.4696, 47.1952),
    "M81": (148.8882, 69.0653),
    "M33": (23.4621, 30.6599),
    "NGC 253": (11.8880, -25.2882),
    "NGC 2403": (114.2142, 65.6026),
    "NGC 6946": (308.7180, 60.1539),
}
COLLECTIONS = ("spherex_dr1", "spherex_qr3")
ENDPOINT = "https://irsa.ipac.caltech.edu/SIA"


def query(target, ra, dec, collection):
    params = urllib.parse.urlencode({
        "REQUEST": "queryData", "COLLECTION": collection,
        "POS": f"CIRCLE {ra} {dec} 0.02", "MAXREC": "30",
        "RESPONSEFORMAT": "votable",
    })
    url = f"{ENDPOINT}?{params}"
    last = None
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=35)
            response.raise_for_status()
            body = response.content
            status = response.status_code
            return parse(body), {"status": status, "attempt": attempt + 1, "url": url}
        except Exception as error:
            last = f"{type(error).__name__}: {error}"
            time.sleep(1.5 * (2 ** attempt))
    return [], {"status": None, "attempt": 3, "url": url, "error": last}


def parse(body):
    root = ET.fromstring(body)
    fields = []
    for field in root.iter():
        if field.tag.endswith("FIELD"):
            fields.append(field.attrib.get("name") or field.attrib.get("ID") or field.attrib.get("ucd") or f"col_{len(fields)}")
    rows = []
    for tr in root.iter():
        if not tr.tag.endswith("TR"):
            continue
        values = [(td.text or "").strip() for td in tr if td.tag.endswith("TD")]
        rows.append(dict(zip(fields, values)))
    return rows


def main():
    output = {}
    for target, (ra, dec) in TARGETS.items():
        output[target] = {"coordinates": [ra, dec], "collections": {}}
        for collection in COLLECTIONS:
            rows, request = query(target, ra, dec, collection)
            output[target]["collections"][collection] = {"request": request, "rows": rows}
            checkpoint = Path(__file__).resolve().parents[1] / 'data' / 'demo_discovery.json'
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            checkpoint.write_text(json.dumps(output, indent=2), encoding='utf-8')
            print(target, collection, request.get("status"), len(rows), flush=True)
    print("DISCOVERY_JSON_BEGIN")
    print(json.dumps(output))


if __name__ == "__main__":
    main()
