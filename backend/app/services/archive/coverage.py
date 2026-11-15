"""Time-dependent moving-target footprint checks with explicit search completeness."""
from dataclasses import dataclass
import csv
import io
import requests
import warnings

HORIZONS_ENDPOINT = "https://ssd.jpl.nasa.gov/api/horizons.api"
SEDNA_COMMAND = "90377"


def sedna_ephemerides(mjds, request_get=requests.get):
    """Return geocentric ICRF Sedna positions for exact observation MJDs."""
    times = [float(value) for value in mjds]
    if not times:
        return []
    params = {"format": "json", "COMMAND": SEDNA_COMMAND, "OBJ_DATA": "NO",
        "MAKE_EPHEM": "YES", "EPHEM_TYPE": "OBSERVER", "CENTER": "500@399",
        "TLIST": " ".join(str(value) for value in times), "TLIST_TYPE": "MJD",
        "QUANTITIES": "1", "ANG_FORMAT": "DEG", "CSV_FORMAT": "YES", "EXTRA_PREC": "YES"}
    response = request_get(HORIZONS_ENDPOINT, params=params, timeout=30)
    response.raise_for_status()
    result = response.json().get("result", "")
    if "$$SOE" not in result or "$$EOE" not in result:
        raise ValueError("JPL Horizons response contains no ephemeris table")
    rows = []
    table = result.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    for mjd, row in zip(times, csv.reader(io.StringIO(table.strip()))):
        values = [value.strip() for value in row]
        numeric = [float(value) for value in values if value and _is_float(value)]
        if len(numeric) < 2:
            raise ValueError("JPL Horizons row lacks decimal RA/Dec")
        rows.append({"mjd": mjd, "ra_deg": numeric[-2], "dec_deg": numeric[-1],
                     "observer": "geocenter (500@399)", "source": HORIZONS_ENDPOINT})
    if len(rows) != len(times):
        raise ValueError("JPL Horizons returned a different number of epochs")
    return rows


def _is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


def position_inside_model(model, ra_deg, dec_deg):
    wcs = model.get("wcs")
    image = model.get("image")
    if wcs is None or image is None:
        return None
    try:
        # Far-outside sky positions can trigger expected WCS convergence warnings.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            warnings.simplefilter("ignore", category=UserWarning)
            x, y = wcs.celestial.world_to_pixel_values(ra_deg, dec_deg)
        return bool(0 <= x < image.shape[1] and 0 <= y < image.shape[0])
    except Exception:
        return None


def coverage_report(target, releases=("QR2", "QR3"), live_search=False, epochs=None):
    base = {"target": target, "searched_releases": list(releases),
        "archive_tables": ["IVOA ObsCore / SPHEREx spectral-image collections"],
        "footprint_rule": "Predicted ICRF position must transform inside the product IMAGE WCS at its epoch",
        "search_complete": False}
    if target == "Planet 9 Candidate Field":
        return {**base, "status": "HYPOTHETICAL_SEARCH_REGION", "search_mode": "FIXED_COORDINATE_REGION",
            "coordinates_deg": [65.250, 15.500],
            "detail": "A bounded hypothetical region, not a known moving object or permanently unsurveyed sky location."}
    if target != "Sedna":
        return {**base, "status": "UNSUPPORTED_TARGET"}
    if not live_search:
        return {**base, "status": "SEARCH_INCOMPLETE_OR_UNAVAILABLE", "search_mode": "TIME_DEPENDENT_EPHEMERIS",
            "fixed_coordinate_reference_deg": [55.438, 7.892],
            "detail": "Live JPL Horizons and archive footprint evaluation was not requested; fixed-coordinate catalog results are not a coverage conclusion."}
    try:
        positions = sedna_ephemerides(epochs or [])
    except Exception as error:
        return {**base, "status": "SEARCH_INCOMPLETE_OR_UNAVAILABLE", "search_mode": "TIME_DEPENDENT_EPHEMERIS",
            "detail": f"JPL Horizons query failed: {type(error).__name__}"}
    return {**base, "status": "NO_MATCHING_RECORDS_IN_SEARCHED_CATALOG" if not positions else "EPHEMERIDES_AVAILABLE_ARCHIVE_QUERY_REQUIRED",
        "search_mode": "TIME_DEPENDENT_EPHEMERIS", "ephemerides": positions,
        "detail": "Positions were calculated, but a complete release-wide product footprint query is not implemented in this local catalog endpoint."}
