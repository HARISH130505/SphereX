import io
from pathlib import Path

import pytest
from astropy.io.votable import from_table, writeto
from astropy.io.votable.tree import Info
from astropy.table import Table

from app.services.archive.release_coverage import (
    CheckpointStore, EphemerisPoint, PartitionResult, SEARCHABLE_COLLECTIONS,
    SIAClient, SearchPartition, angular_distance_deg, build_corridor_partitions,
    evaluate_record, interpolate_ephemeris, parse_sia_votable,
    point_in_spherical_polygon, search_release_coverage, stable_product_key,
)


def test_ephemeris_interpolation_crosses_ra_wrap():
    point = interpolate_ephemeris([EphemerisPoint(1, 359, 0), EphemerisPoint(3, 1, 0)], 2)
    assert min(point.ra_deg, 360 - point.ra_deg) < 1e-6


def test_ephemeris_interpolation_is_stable_near_pole():
    point = interpolate_ephemeris([EphemerisPoint(1, 0, 89), EphemerisPoint(3, 180, 89)], 2)
    assert point.dec_deg == pytest.approx(90)


def test_corridor_is_deterministic_and_contains_endpoints():
    points = [EphemerisPoint(1, 359.9, 10), EphemerisPoint(2, .1, 10)]
    a = build_corridor_partitions(points, ["spherex_dr1"], .01)
    b = build_corridor_partitions(reversed(points), ["spherex_dr1"], .01)
    assert a == b
    assert angular_distance_deg(a[0].center_ra_deg, a[0].center_dec_deg, 359.9, 10) < a[0].radius_deg
    assert "CIRCLE" in a[0].request_params(20)["POS"]
    assert a[0].request_params(20)["COLLECTION"] == "spherex_dr1"


def test_unverified_collection_is_rejected():
    with pytest.raises(ValueError, match="unverified"):
        build_corridor_partitions([EphemerisPoint(1, 1, 1), EphemerisPoint(2, 2, 2)], ["made_up"])


def test_spherical_polygon_wrap_boundary_and_polar_geometry():
    wrap = [(359, -1), (1, -1), (1, 1), (359, 1)]
    assert point_in_spherical_polygon(0, 0, wrap)
    assert point_in_spherical_polygon(359, 0, wrap)  # boundary
    assert not point_in_spherical_polygon(180, 0, wrap)
    polar = [(0, 85), (120, 85), (240, 85)]
    assert point_in_spherical_polygon(45, 89, polar)


def _votable(overflow=False):
    table = Table({
        "obs_collection": ["spherex_dr1"], "obs_id": ["one"],
        "obs_publisher_did": ["ivo://one"], "access_url": ["https://example/one.fits"],
        "s_region": ["POLYGON ICRS 359 -1 1 -1 1 1 359 1"],
        "t_min": [1.0], "t_max": [2.0],
    })
    votable = from_table(table)
    if overflow:
        votable.resources[0].infos.append(Info(name="QUERY_STATUS", value="OVERFLOW"))
    stream = io.BytesIO()
    writeto(votable, stream)
    return stream.getvalue()


def test_genuine_votable_parsing_and_overflow():
    records, overflow = parse_sia_votable(_votable(True))
    assert overflow
    assert records[0]["publisher_did"] == "ivo://one"
    assert records[0]["t_max"] == 2.0


class Response:
    def __init__(self, status, content=b""):
        self.status_code, self.content = status, content
    def raise_for_status(self):
        if self.status_code >= 400:
            raise __import__("requests").HTTPError(str(self.status_code))


def test_retry_exhaustion_records_failure_without_infinite_retry():
    calls = []
    client = SIAClient(lambda *a, **k: (calls.append(1) or Response(502)), max_retries=2, sleep=lambda _: None)
    result = client.query(SearchPartition("spherex_dr1", 1, 2, 0, 0, 1))
    assert len(calls) == 3
    assert result.retry_count == 2
    assert not result.complete
    assert result.http_status == 502


def test_observation_interval_midpoint_and_endpoints_are_tested():
    ephemeris = [EphemerisPoint(1, 359.5, 0), EphemerisPoint(2, .5, 0)]
    record = {"collection": "spherex_dr1", "obs_id": "x", "t_min": 1, "t_max": 2,
              "s_region": "POLYGON ICRS 359 -1 1 -1 1 1 359 1"}
    result = evaluate_record(record, ephemeris)
    assert result["intersection"] is True
    assert result["tested_epochs_mjd"][0] == 1.0
    assert 1.5 in result["tested_epochs_mjd"]
    assert result["tested_epochs_mjd"][-1] == 2.0


def test_deduplication_identity_includes_collection():
    assert stable_product_key({"collection": "a", "obs_id": "same"}) != stable_product_key({"collection": "b", "obs_id": "same"})


class FixtureClient:
    def __init__(self, content=_votable(False)):
        self.calls = 0
        self.content = content
    def query(self, partition, max_records):
        self.calls += 1
        records, overflow = parse_sia_votable(self.content)
        return PartitionResult(partition, partition.request_params(max_records), 200, len(records), overflow, 0,
                               not overflow, None, records)


def test_checkpoint_resume_avoids_completed_request(tmp_path):
    points = [EphemerisPoint(1, 359.5, 0), EphemerisPoint(2, .5, 0)]
    client = FixtureClient()
    path = tmp_path / "checkpoint.json"
    first = search_release_coverage(points, path, client, ["spherex_dr1"], temporal_range_verified=True, corridor_verified=True)
    second = search_release_coverage(points, path, client, ["spherex_dr1"], temporal_range_verified=True, corridor_verified=True)
    assert client.calls == 1
    assert first["status"] == second["status"] == "COVERAGE_CONFIRMED"


def test_complete_and_incomplete_negative_are_distinct(tmp_path):
    points = [EphemerisPoint(1, 20, 0), EphemerisPoint(2, 21, 0)]
    client = FixtureClient()
    complete = search_release_coverage(points, tmp_path / "a.json", client, ["spherex_dr1"], temporal_range_verified=True, corridor_verified=True)
    incomplete = search_release_coverage(points, tmp_path / "b.json", client, ["spherex_dr1"], temporal_range_verified=False)
    assert complete["status"] == "NO_INTERSECTION_IN_SEARCHED_RELEASES"
    assert incomplete["status"] == "ARCHIVE_QUERY_INCOMPLETE"


def test_missing_footprint_is_uncertain_not_negative(tmp_path):
    table = Table({"obs_collection": ["spherex_dr1"], "obs_id": ["x"], "t_min": [1.0], "t_max": [2.0]})
    votable = from_table(table); stream = io.BytesIO(); writeto(votable, stream)
    result = search_release_coverage(
        [EphemerisPoint(1, 0, 0), EphemerisPoint(2, 1, 0)], tmp_path / "c.json",
        FixtureClient(stream.getvalue()), ["spherex_dr1"], temporal_range_verified=True,
    )
    assert result["status"] == "FOOTPRINT_UNAVAILABLE"
