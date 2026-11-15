from fastapi import APIRouter, Query
from app.services.archive.coverage import coverage_report
from app.services.archive.coverage import position_inside_model
from app.services.archive.coverage import sedna_ephemerides
from app.services.archive.release_coverage import EphemerisPoint, search_release_coverage
from app.services.storage.repository import repository
from app.services.astronomy.fits_io import get_fits_cache_path, load_fits_image
from app.config import CACHE_DIR

router = APIRouter(prefix="/coverage", tags=["Coverage"])


@router.get("/Sedna/release-search")
def search_sedna_releases(
    start_mjd: float = Query(...), end_mjd: float = Query(...),
    step_days: float = Query(1.0, gt=0, le=30), live: bool = Query(False),
):
    """Plan or execute a resumable DR1/QR3 metadata-only footprint search.

    The public release-wide date bounds have not yet been independently
    established from complete archive metadata, so this endpoint never marks
    a negative search complete merely because caller-supplied bounds finished.
    """
    if end_mjd <= start_mjd:
        return {"status": "EPHEMERIS_UNAVAILABLE", "detail": "end_mjd must be greater than start_mjd"}
    epochs = []
    value = start_mjd
    while value < end_mjd:
        epochs.append(value)
        value += step_days
    epochs.append(end_mjd)
    if not live:
        return {"status": "ARCHIVE_QUERY_INCOMPLETE", "execution": "preview",
                "observer_reference": "geocenter (500@399), approximation",
                "search_date_range_mjd": [start_mjd, end_mjd],
                "ephemeris_sample_count": len(epochs),
                "detail": "Set live=true to contact Horizons and IRSA; no archive query was made."}
    try:
        positions = [EphemerisPoint(row["mjd"], row["ra_deg"], row["dec_deg"])
                     for row in sedna_ephemerides(epochs)]
    except Exception as error:
        return {"status": "EPHEMERIS_UNAVAILABLE", "detail": f"Horizons query failed: {type(error).__name__}"}
    checkpoint = CACHE_DIR / 'checkpoints' / 'sedna_release_coverage.json'
    return search_release_coverage(positions, checkpoint, temporal_range_verified=False)


@router.get("/{target}")
def get_coverage(target: str, live: bool = Query(False)):
    observations = repository.get_all()
    epochs = sorted({row.obs_time_mjd for row in observations})
    report = coverage_report(target, live_search=live, epochs=epochs)
    if target != "Sedna" or not report.get("ephemerides"):
        return report
    positions = {row["mjd"]: row for row in report["ephemerides"]}
    tests = []
    for observation in observations:
        if not get_fits_cache_path(observation.obs_id, observation.band).exists():
            continue
        position = positions.get(observation.obs_time_mjd)
        if not position:
            continue
        try:
            model = load_fits_image(observation)
            inside = position_inside_model(model, position["ra_deg"], position["dec_deg"])
        except Exception:
            inside = None
        tests.append({"product_id": observation.product_id, "mjd": observation.obs_time_mjd,
            "predicted_ra_deg": position["ra_deg"], "predicted_dec_deg": position["dec_deg"],
            "footprint_intersection": inside,
            "product_status": observation.screening_status})
    report["local_footprint_tests"] = tests
    matches = [row for row in tests if row["footprint_intersection"] is True]
    report["local_footprint_matches"] = matches
    report["status"] = "LOCAL_FOOTPRINT_MATCHES_FOUND" if matches else "NO_FOOTPRINT_INTERSECTION_IN_LOCAL_PRODUCTS"
    report["detail"] = (f"Tested {len(tests)} locally available products at exact epochs; "
        f"found {len(matches)} intersections. Full release-wide archive search remains incomplete.")
    return report
