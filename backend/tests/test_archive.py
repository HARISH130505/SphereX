"""
Unit tests for archive queries and client configuration.
"""
from app.services.archive.query import build_cone_search_adql
from app.services.archive.products import construct_cutout_url

def test_cone_search_query():
    adql = build_cone_search_adql(ra=210.802, dec=54.349, radius_deg=0.1)
    assert "210.802" in adql
    assert "54.349" in adql
    assert "ivoa.ObsCore" in adql

def test_cutout_url():
    url = construct_cutout_url("https://irsa.ipac.caltech.edu/level2.fits", ra=210.8, dec=54.3, size_deg=0.1)
    assert "center=210.8%2C54.3" in url
    assert "size=0.1" in url
