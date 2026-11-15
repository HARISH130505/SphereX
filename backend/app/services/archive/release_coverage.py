"""Resumable SIA2 moving-target footprint search.

Metadata discovery is intentionally separate from FITS retrieval.  The search
is conservative: failed, overflowing, or geometrically ambiguous partitions
can never produce a complete negative result.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable, Iterable
import io
import json
import math
import random
import time

import requests
from astropy.io.votable import parse
from astropy.time import Time

SIA_ENDPOINT = "https://irsa.ipac.caltech.edu/SIA"
SEARCHABLE_COLLECTIONS = (
    "spherex_dr1", "spherex_dr1_deep", "spherex_qr3", "spherex_qr3_deep"
)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
FINAL_STATES = {
    "COVERAGE_CONFIRMED", "NO_INTERSECTION_IN_SEARCHED_RELEASES",
    "POSSIBLE_INTERSECTION_UNVERIFIED", "ARCHIVE_QUERY_INCOMPLETE",
    "EPHEMERIS_UNAVAILABLE", "FOOTPRINT_UNAVAILABLE",
}


@dataclass(frozen=True)
class EphemerisPoint:
    mjd: float
    ra_deg: float
    dec_deg: float


@dataclass(frozen=True)
class SearchPartition:
    collection: str
    time_min_mjd: float
    time_max_mjd: float
    center_ra_deg: float
    center_dec_deg: float
    radius_deg: float
    depth: int = 0

    @property
    def key(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return sha256(raw.encode()).hexdigest()[:24]

    def request_params(self, max_records: int) -> dict[str, str]:
        return {
            "REQUEST": "queryData", "COLLECTION": self.collection,
            "POS": f"CIRCLE {self.center_ra_deg:.10f} {self.center_dec_deg:.10f} {self.radius_deg:.10f}",
            "TIME": f"{self.time_min_mjd:.9f} {self.time_max_mjd:.9f}",
            "MAXREC": str(max_records), "RESPONSEFORMAT": "votable",
        }


@dataclass
class PartitionResult:
    partition: SearchPartition
    request_params: dict[str, str]
    http_status: int | None = None
    record_count: int = 0
    overflow: bool = False
    retry_count: int = 0
    complete: bool = False
    error: str | None = None
    records: list[dict] = field(default_factory=list)

    def serializable(self) -> dict:
        value = asdict(self)
        value["partition_key"] = self.partition.key
        return value


def normalize_ra(ra_deg: float) -> float:
    return float(ra_deg) % 360.0


def angular_distance_deg(ra1, dec1, ra2, dec2) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    cosine = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def interpolate_ephemeris(points: Iterable[EphemerisPoint], mjd: float) -> EphemerisPoint:
    ordered = sorted(points, key=lambda p: p.mjd)
    if not ordered or mjd < ordered[0].mjd or mjd > ordered[-1].mjd:
        raise ValueError("epoch lies outside ephemeris range")
    for point in ordered:
        if math.isclose(point.mjd, mjd, abs_tol=1e-12):
            return point
    right = next(i for i, point in enumerate(ordered) if point.mjd > mjd)
    a, b = ordered[right - 1], ordered[right]
    f = (mjd - a.mjd) / (b.mjd - a.mjd)
    # Interpolate unit vectors, avoiding the RA=0 discontinuity and remaining
    # stable near the poles.
    def vector(p):
        ra, dec = math.radians(p.ra_deg), math.radians(p.dec_deg)
        return (math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec))
    av, bv = vector(a), vector(b)
    v = tuple((1 - f) * x + f * y for x, y in zip(av, bv))
    norm = math.sqrt(sum(x * x for x in v))
    x, y, z = (x / norm for x in v)
    return EphemerisPoint(mjd, normalize_ra(math.degrees(math.atan2(y, x))), math.degrees(math.asin(z)))


def build_corridor_partitions(points: Iterable[EphemerisPoint], collections=SEARCHABLE_COLLECTIONS,
                              margin_deg: float = 0.05) -> list[SearchPartition]:
    """Make deterministic time-bounded cones whose union contains each arc.

    The cone radius is half the endpoint separation plus a configurable safety
    margin. Spherical midpoint interpolation supplies the center.
    """
    ordered = sorted(points, key=lambda p: p.mjd)
    if len(ordered) < 2:
        raise ValueError("at least two ephemeris points are required")
    partitions = []
    for collection in sorted(set(collections)):
        if collection not in SEARCHABLE_COLLECTIONS:
            raise ValueError(f"unverified SIA collection: {collection}")
        for a, b in zip(ordered, ordered[1:]):
            mid = interpolate_ephemeris((a, b), (a.mjd + b.mjd) / 2)
            radius = angular_distance_deg(a.ra_deg, a.dec_deg, b.ra_deg, b.dec_deg) / 2 + margin_deg
            partitions.append(SearchPartition(collection, a.mjd, b.mjd, mid.ra_deg, mid.dec_deg, radius))
    return partitions


def _value(row, *names):
    lookup = {str(name).lower(): name for name in row.colnames}
    for name in names:
        if name.lower() in lookup:
            value = row[lookup[name.lower()]]
            if getattr(value, "mask", False):
                return None
            if isinstance(value, bytes):
                value = value.decode("utf-8", "replace")
            return value.item() if hasattr(value, "item") else value
    return None


def parse_sia_votable(content: bytes) -> tuple[list[dict], bool]:
    votable = parse(io.BytesIO(content))
    table = votable.get_first_table()
    infos = list(getattr(votable, "infos", []) or [])
    for resource in votable.resources:
        infos.extend(list(getattr(resource, "infos", []) or []))
        infos.extend(list(getattr(table, "infos", []) or []))
    overflow = any(str(getattr(info, "name", "")).upper() == "QUERY_STATUS" and
                   str(getattr(info, "value", "")).upper() == "OVERFLOW" for info in infos)
    records = []
    for row in table.to_table():
        record = {
            "collection": _value(row, "obs_collection", "collection"),
            "obs_id": _value(row, "obs_id"),
            "publisher_did": _value(row, "obs_publisher_did", "publisher_did"),
            "access_url": _value(row, "access_url"),
            "s_region": _value(row, "s_region"),
            "t_min": _value(row, "t_min"), "t_max": _value(row, "t_max"),
        }
        records.append(record)
    return records, overflow


class CheckpointStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = {"version": 1, "partitions": {}}
        if self.path.exists():
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if loaded.get("version") == 1:
                self.data = loaded

    def get_complete(self, key: str):
        item = self.data["partitions"].get(key)
        return item if item and item.get("complete") and not item.get("overflow") else None

    def save(self, result: PartitionResult):
        self.data["partitions"][result.partition.key] = result.serializable()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.path)


class SIAClient:
    def __init__(self, request_get=requests.get, timeout=30.0, max_retries=4,
                 backoff_seconds=0.5, sleep: Callable[[float], None] = time.sleep):
        self.request_get = request_get
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.sleep = sleep

    def query(self, partition: SearchPartition, max_records=5000) -> PartitionResult:
        params = partition.request_params(max_records)
        result = PartitionResult(partition, params)
        for attempt in range(self.max_retries + 1):
            result.retry_count = attempt
            try:
                response = self.request_get(SIA_ENDPOINT, params=params, timeout=self.timeout)
                result.http_status = response.status_code
                if response.status_code in RETRYABLE_STATUS and attempt < self.max_retries:
                    self.sleep(self.backoff_seconds * (2 ** attempt) + random.uniform(0, .1))
                    continue
                response.raise_for_status()
                result.records, result.overflow = parse_sia_votable(response.content)
                result.record_count = len(result.records)
                result.complete = not result.overflow
                if result.overflow:
                    result.error = "SIA QUERY_STATUS=OVERFLOW"
                return result
            except (requests.RequestException, ValueError, OSError) as error:
                result.error = f"{type(error).__name__}: {str(error)[:300]}"
                if attempt < self.max_retries:
                    self.sleep(self.backoff_seconds * (2 ** attempt) + random.uniform(0, .1))
                    continue
        return result


def subdivide_partition(partition: SearchPartition) -> tuple[SearchPartition, SearchPartition]:
    midpoint = (partition.time_min_mjd + partition.time_max_mjd) / 2
    values = asdict(partition)
    values["depth"] += 1
    left = SearchPartition(**{**values, "time_max_mjd": midpoint})
    right = SearchPartition(**{**values, "time_min_mjd": midpoint})
    return left, right


def parse_polygon(region: str | None) -> list[tuple[float, float]] | None:
    if not region:
        return None
    tokens = str(region).replace(",", " ").split()
    if len(tokens) < 8 or tokens[0].upper() != "POLYGON":
        return None
    start = 2 if tokens[1].upper() in {"ICRS", "FK5"} else 1
    try:
        numbers = [float(value) for value in tokens[start:]]
    except ValueError:
        return None
    if len(numbers) < 6 or len(numbers) % 2:
        return None
    return [(normalize_ra(numbers[i]), numbers[i + 1]) for i in range(0, len(numbers), 2)]


def point_in_spherical_polygon(ra_deg: float, dec_deg: float,
                               polygon: list[tuple[float, float]], tolerance_deg=1e-8) -> bool:
    """Tangent-plane containment for archive-sized spherical polygons.

    A gnomonic projection about the polygon's vector centroid handles RA wrap
    and polar fields without selecting the antipodal complement.
    """
    def unit(ra, dec):
        r, d = math.radians(ra), math.radians(dec)
        return (math.cos(d)*math.cos(r), math.cos(d)*math.sin(r), math.sin(d))
    def dot(a, b): return sum(x*y for x, y in zip(a, b))
    def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
    vertices = [unit(*vertex) for vertex in polygon]
    centroid = tuple(sum(v[i] for v in vertices) for i in range(3))
    length = math.sqrt(dot(centroid, centroid))
    if not length:
        return False
    center = tuple(value / length for value in centroid)
    reference = (0.0, 0.0, 1.0) if abs(center[2]) < .9 else (1.0, 0.0, 0.0)
    east = cross(reference, center)
    east_len = math.sqrt(dot(east, east)); east = tuple(value/east_len for value in east)
    north = cross(center, east)
    def project(vector):
        denominator = dot(vector, center)
        if denominator <= 0:  # not in the archive polygon's local hemisphere
            return None
        return (dot(vector, east)/denominator, dot(vector, north)/denominator)
    point = project(unit(ra_deg, dec_deg))
    projected = [project(vertex) for vertex in vertices]
    if point is None or any(vertex is None for vertex in projected):
        return False
    x, y = point
    inside = False
    tolerance = math.radians(tolerance_deg)
    for a, b in zip(projected, projected[1:] + projected[:1]):
        ax, ay = a; bx, by = b
        dx, dy = bx-ax, by-ay
        segment_length_sq = dx*dx + dy*dy
        if segment_length_sq:
            t = max(0.0, min(1.0, ((x-ax)*dx + (y-ay)*dy)/segment_length_sq))
            if math.hypot(x-(ax+t*dx), y-(ay+t*dy)) <= tolerance:
                return True
        if (ay > y) != (by > y) and x < dx*(y-ay)/(dy if dy else 1e-300) + ax:
            inside = not inside
    return inside


def stable_product_key(record: dict) -> str:
    identity = record.get("publisher_did") or record.get("obs_id") or record.get("access_url")
    if not identity:
        identity = sha256(json.dumps(record, sort_keys=True, default=str).encode()).hexdigest()
    return f"{record.get('collection') or 'unknown'}::{identity}"


def evaluate_record(record: dict, ephemeris: list[EphemerisPoint]) -> dict:
    polygon = parse_polygon(record.get("s_region"))
    try:
        t_min, t_max = float(record["t_min"]), float(record["t_max"])
        if t_max < t_min:
            raise ValueError
        start = interpolate_ephemeris(ephemeris, t_min)
        end = interpolate_ephemeris(ephemeris, t_max)
        # Sample the exposure trajectory at no more than 0.05 degrees between
        # tests (and always include a midpoint). For Sedna exposures this will
        # normally reduce to the endpoints and midpoint.
        count = max(2, math.ceil(angular_distance_deg(
            start.ra_deg, start.dec_deg, end.ra_deg, end.dec_deg) / .05))
        count = min(count, 1000)
        epochs = [t_min + (t_max-t_min)*i/(count*2) for i in range(count*2 + 1)]
        positions = [interpolate_ephemeris(ephemeris, epoch) for epoch in epochs]
    except (TypeError, ValueError, KeyError):
        return {**record, "intersection": None, "reason": "invalid or uncovered observation interval"}
    if not polygon:
        return {**record, "intersection": None, "reason": "footprint unavailable or invalid"}
    hits = [point_in_spherical_polygon(p.ra_deg, p.dec_deg, polygon) for p in positions]
    return {**record, "intersection": any(hits), "tested_epochs_mjd": epochs,
            "reason": "endpoint and midpoint trajectory samples tested"}


def search_release_coverage(ephemeris: list[EphemerisPoint], checkpoint_path: Path,
                            client: SIAClient | None = None, collections=SEARCHABLE_COLLECTIONS,
                            max_records=5000, max_depth=8, corridor_margin_deg=.05,
                            temporal_range_verified=False, corridor_verified=False) -> dict:
    client, store = client or SIAClient(), CheckpointStore(checkpoint_path)
    queue = build_corridor_partitions(ephemeris, collections, corridor_margin_deg)
    results: list[dict] = []
    records: dict[str, dict] = {}
    while queue:
        partition = queue.pop(0)
        cached = store.get_complete(partition.key)
        if cached:
            result_dict = cached
        else:
            result = client.query(partition, max_records)
            store.save(result)
            result_dict = result.serializable()
        if result_dict.get("overflow") and partition.depth < max_depth:
            queue[0:0] = list(subdivide_partition(partition))
            results.append(result_dict)
            continue
        results.append(result_dict)
        for record in result_dict.get("records", []):
            record["collection"] = record.get("collection") or partition.collection
            records[stable_product_key(record)] = record
    evaluated = [evaluate_record(record, ephemeris) for record in records.values()]
    confirmed = [row for row in evaluated if row["intersection"] is True]
    uncertain = [row for row in evaluated if row["intersection"] is None]
    complete = temporal_range_verified and corridor_verified and all(
        row.get("complete") and not row.get("overflow") for row in results)
    if confirmed:
        status = "COVERAGE_CONFIRMED"
    elif uncertain and all(row.get("reason") == "footprint unavailable or invalid" for row in uncertain):
        status = "FOOTPRINT_UNAVAILABLE"
    elif uncertain:
        status = "POSSIBLE_INTERSECTION_UNVERIFIED"
    elif complete:
        status = "NO_INTERSECTION_IN_SEARCHED_RELEASES"
    else:
        status = "ARCHIVE_QUERY_INCOMPLETE"
    return {
        "status": status, "observer_reference": "geocenter (500@399), approximation",
        "collections_searched": sorted(set(collections)),
        "search_date_range_mjd": [ephemeris[0].mjd, ephemeris[-1].mjd],
        "partition_count": len(results),
        "completed_partitions": sum(bool(row.get("complete")) for row in results),
        "failed_partitions": sum(not bool(row.get("complete")) for row in results),
        "unique_products_evaluated": len(evaluated),
        "confirmed_intersections": len(confirmed), "uncertain_intersections": len(uncertain),
        "search_complete": complete, "temporal_range_verified": temporal_range_verified,
        "corridor_verified": corridor_verified,
        "products": evaluated, "partition_results": results,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Geocentric Horizons coordinates are an explicit approximation; spacecraft parallax is not yet validated.",
            "Corridor completeness requires independently validated ephemeris sampling and uncertainty margins.",
            "A negative result is permitted only when every partition and the release temporal range are verified complete.",
            "No FITS products are downloaded during metadata discovery.",
        ],
    }
