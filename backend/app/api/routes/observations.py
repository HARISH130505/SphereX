"""
Observation catalog and target discovery routes.
"""
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException
from app.schemas.observation import ObservationSchema, TargetSchema, TargetTimelineResponse, TimelineItemSchema
from app.services.storage.repository import repository, TARGETS_METADATA
from app.config import CACHE_DIR

router = APIRouter(prefix="/sky", tags=["Observations"])

@router.get("/targets", response_model=List[TargetSchema])
def get_targets():
    return repository.get_targets()

@router.get("/observations", response_model=List[ObservationSchema])
def get_observations(
    target: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    band: Optional[str] = Query(None),
):
    obs = repository.get_all(target=target, status=status)
    if target and not any(name.casefold() == target.casefold() for name in TARGETS_METADATA):
        raise HTTPException(404, detail='Target is not in the predefined catalog.')
    if band:
        obs = [o for o in obs if o.band.lower() == band.lower()]
    return obs

@router.get("/timeline/{target}", response_model=TargetTimelineResponse)
def get_target_timeline(target: str):
    # Case-insensitive target lookup
    matched_name = None
    matched_meta = None
    for name, meta in TARGETS_METADATA.items():
        if name.lower() == target.lower():
            matched_name = name
            matched_meta = meta
            break

    if not matched_name or not matched_meta:
        raise HTTPException(status_code=404, detail=f"Target '{target}' not found in registry.")

    raw_obs = repository.get_all(target=matched_name)
    raw_obs.sort(key=lambda o: o.obs_time_mjd)

    coverage_status = "NO_LOCAL_RECORDS_SEARCH_INCOMPLETE" if len(raw_obs) == 0 else "LOCAL_CATALOG_RECORDS_AVAILABLE"

    items: List[TimelineItemSchema] = []
    eligible_count = 0

    for o in raw_obs:
        # Extract product filename from cutout_url
        url = o.cutout_url or ""
        if ".fits" in url:
            fname = url.split("?")[0].split("/")[-1]
        else:
            fname = f"{o.obs_id}_{o.band}.fits"

        # Check local cache
        cached_file = (CACHE_DIR / f"{o.obs_id}_{o.band}.fits".replace("/", "_").replace(":", "_")).exists()

        is_failed = o.screening_status == "FAILED_DOWNLOAD" or not o.fits_valid
        is_geom = o.screening_status == "REJECTED_GEOMETRY"
        is_sat = o.screening_status == "REJECTED_SATURATED"
        is_clean = o.screening_status == "PASSED_CLEAN"
        is_caveat = o.screening_status == "FEASIBLE_WITH_CAVEATS"

        eligible = o.fits_valid and o.band != 'UNKNOWN' and (is_clean or is_caveat) and not is_geom
        if eligible:
            eligible_count += 1

        if o.screening_status == 'NOT_VALIDATED':
            elig_reason = 'Observation has not yet passed scientific validation.'
            dq = 'Observation not yet validated'
        elif is_failed:
            elig_reason = f"Ineligible for comparison: {o.rejection_reason or 'Archive product retrieval failed'}"
            dq = "Corrupted / Failed Archive Retrieval"
        elif is_geom:
            elig_reason = "Ineligible for comparison: Target coordinates fall outside image cutout FOV"
            dq = "Target Outside Sub-Array Footprint"
        elif is_sat:
            elig_reason = "Eligible with caveats: Central core saturated; WCS reprojection & difference masking will isolate outer halo"
            dq = "Saturated Detector Core (SUR Overflow)"
        elif is_caveat:
            elig_reason = "Eligible with caveats: Elevated background or non-critical calibration flags"
            dq = "Usable with Photometric Caveats"
        else:
            elig_reason = "Fully eligible for differential photometry and transient source extraction"
            dq = "Clean Calibrated Sky Photometry"

        release = o.collection or ("QR2" if matched_name == "M101" else "QR3")
        prov = f"IPAC IRSA SPHEREx {release} Level 2b ({'Locally Cached' if cached_file else 'Remote Archive'})"

        items.append(TimelineItemSchema(
            product_id=o.product_id,
            archive_product_id=o.archive_product_id,
            obs_id=o.obs_id,
            band=o.band,
            obs_time_mjd=o.obs_time_mjd,
            obs_time_iso=o.obs_time_iso,
            product_identifier=fname,
            image_shape=o.image_shape,
            screening_status=o.screening_status,
            rejection_reason=o.rejection_reason,
            data_quality=dq,
            provenance=prov,
            comparison_eligible=eligible,
            eligibility_reason=elig_reason,
        ))

    return TargetTimelineResponse(
        target=matched_name,
        category=matched_meta["cat"],
        ra=matched_meta["ra"],
        dec=matched_meta["dec"],
        coverage_status=coverage_status,
        observation_count=len(raw_obs),
        eligible_count=eligible_count,
        timeline=items,
    )

@router.get("/spectral/m101")
def get_m101_spectral():
    points = repository.get_m101_photometry()
    snrs = [p["snr"] for p in points]
    median_snr = sorted(snrs)[len(snrs) // 2] if snrs else 0.0
    return {
        "target": "M101",
        "ra": 210.80227,
        "dec": 54.34895,
        "total_points": len(points),
        "wavelength_range_um": [0.737, 5.0],
        "bands": ["SPHEREx-D1", "SPHEREx-D2", "SPHEREx-D3", "SPHEREx-D4", "SPHEREx-D5", "SPHEREx-D6"],
        "points": points,
        "median_snr": round(median_snr, 1),
    }
