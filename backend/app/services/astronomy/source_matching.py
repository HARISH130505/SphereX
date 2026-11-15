"""Independent-epoch source measurements and conservative celestial association.

No target position or pointing-center offset enters this module. Thresholds are
explicit in MatchingParameters and exported with every result. See
 docs/source_motion_methodology.md for assumptions and completeness limits.
"""
from dataclasses import asdict, dataclass
from app.config import MIN_COMPARISON_OVERLAP
from app.services.astronomy.quality import BRIGHTNESS_THRESHOLD_MJY_SR
from app.services.astronomy.registration import celestial_wcs_error
from typing import Any
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.stats import sigma_clipped_stats
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
import astropy.units as u
from scipy.ndimage import label, maximum_filter


@dataclass(frozen=True)
class MatchingParameters:
    detection_sigma: float = 5.0
    min_pixels: int = 2
    psf_fwhm_arcsec: float = 6.2
    astrometric_floor_arcsec: float = 0.3
    stationary_match_sigma: float = 3.0
    motion_significance_sigma: float = 5.0
    motion_search_radius_arcsec: float = 31.0
    variability_sigma: float = 3.0
    photometric_fractional_floor: float = 0.05
    motion_flux_fractional_tolerance: float = 0.20
    min_reference_sources: int = 3
    min_overlap_fraction: float = MIN_COMPARISON_OVERLAP
    aperture_radius_fwhm: float = 2.0
    background_inner_fwhm: float = 3.0
    background_outer_fwhm: float = 5.0
    saturation_threshold_mjy_sr: float = BRIGHTNESS_THRESHOLD_MJY_SR

    def __post_init__(self):
        for key, value in asdict(self).items():
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be finite and positive")
        if self.min_overlap_fraction > 1:
            raise ValueError("min_overlap_fraction must be <= 1")
        if self.motion_significance_sigma <= self.stationary_match_sigma:
            raise ValueError("Motion threshold must exceed stationary matching threshold")


DEFAULT_MATCHING_PARAMETERS = MatchingParameters()


def extract_epoch_sources(model: dict, parameters=DEFAULT_MATCHING_PARAMETERS) -> list[dict]:
    """Measure positive connected detections in one ORIGINAL epoch/WCS.

    Uses measured positive variance only. A complete unmasked circular aperture
    and a source-masked local background annulus are required for reliable flux.
    Blends, extended components and edge detections remain visible but ineligible.
    """
    image = np.asarray(model["image"], dtype=float)
    variance = model.get("variance")
    wcs = model.get("wcs")
    if (celestial_wcs_error(model) is not None or
            variance is None or model.get("variance_provenance") != "MEASURED" or
            model.get("quality_verified") is not True or model.get("science_units_verified") is not True):
        return []
    variance = np.asarray(variance, dtype=float)
    if variance.shape != image.shape or image.ndim != 2:
        return []
    wcs = wcs.celestial
    scales = np.abs(proj_plane_pixel_scales(wcs)) * 3600
    if not np.all(np.isfinite(scales)) or np.any(scales <= 0):
        return []
    scale = float(np.sqrt(np.prod(scales)))
    # Surface brightness -> flux density, using the projected pixel solid angle.
    pixel_sr = abs(float(np.linalg.det(wcs.pixel_scale_matrix))) * (np.pi / 180)**2
    flux_factor = 1e6 * pixel_sr
    valid = (np.isfinite(image) & np.isfinite(variance) & (variance > 0) &
             (image < parameters.saturation_threshold_mjy_sr))
    if model.get("valid_mask") is not None:
        valid &= np.asarray(model["valid_mask"], dtype=bool)
    if np.count_nonzero(valid) < 12:
        return []
    _, background, _ = sigma_clipped_stats(image[valid], sigma=3.0)
    significance = np.zeros_like(image)
    significance[valid] = (image[valid] - background) / np.sqrt(variance[valid])
    components, count = label(significance >= parameters.detection_sigma)
    yy, xx = np.indices(image.shape)
    radius = parameters.aperture_radius_fwhm * parameters.psf_fwhm_arcsec / scale
    annulus_inner = parameters.background_inner_fwhm * parameters.psf_fwhm_arcsec / scale
    annulus_outer = parameters.background_outer_fwhm * parameters.psf_fwhm_arcsec / scale
    peaks = ((significance == maximum_filter(significance, size=3)) &
             (significance >= parameters.detection_sigma))
    sources = []
    for index in range(1, count + 1):
        component = components == index
        pixel_count = int(np.count_nonzero(component))
        if pixel_count < parameters.min_pixels:
            continue
        weights = np.maximum(image[component] - background, 0)
        cx = float(np.average(xx[component], weights=weights))
        cy = float(np.average(yy[component], weights=weights))
        world = wcs.pixel_to_world(cx, cy)
        if not np.isfinite(world.ra.deg) or not np.isfinite(world.dec.deg):
            continue
        distance2 = (xx - cx)**2 + (yy - cy)**2
        aperture = distance2 <= radius**2
        source_mask = model.get("quality_masks", {}).get("source", np.zeros(image.shape, bool))
        annulus = (~source_mask & (distance2 >= annulus_inner**2) & (distance2 <= annulus_outer**2) &
                   valid & (components == 0))
        reasons = []
        if (cx < radius or cy < radius or cx + radius >= image.shape[1] - 1 or
                cy + radius >= image.shape[0] - 1 or not np.all(valid[aperture])):
            reasons.append("Aperture crosses image edge or invalid pixels")
        if np.any((components[aperture] != 0) & (components[aperture] != index)):
            reasons.append("Neighbor contaminates photometric aperture")
        _, peak_count = label(peaks & component)
        if peak_count != 1:
            reasons.append("Blended or non-unique source peak")
        moment = float(np.average(distance2[component], weights=weights) / 2)
        measured_fwhm = 2.355 * np.sqrt(max(moment, 0)) * scale
        if measured_fwhm > 2.5 * parameters.psf_fwhm_arcsec:
            reasons.append("Extended component; point-source astrometry unsupported")
        flux = flux_err = None
        if np.count_nonzero(annulus) >= 12 and np.all(valid[aperture]):
            clipped_mean, local_bg, local_std = sigma_clipped_stats(image[annulus], sigma=3.0)
            n_ap = int(aperture.sum())
            bg_var = max(float(local_std)**2, float(np.median(variance[annulus])))
            bg_mean_var = (1.2533**2 * bg_var) / int(annulus.sum())
            flux = float(np.sum(image[aperture] - local_bg) * flux_factor)
            flux_err = float(np.sqrt(np.sum(variance[aperture]) + n_ap**2 * bg_mean_var) * flux_factor)
        else:
            reasons.append("Insufficient uncontaminated background or aperture variance")
        peak_snr = float(np.max(significance[component]))
        fwhm = max(parameters.psf_fwhm_arcsec, measured_fwhm)
        astrometric_error = float(np.hypot(fwhm / (2 * peak_snr), parameters.astrometric_floor_arcsec))
        sources.append({
            "source_id": index, "centroid_xy": [cx, cy],
            "ra_deg": float(world.ra.deg), "dec_deg": float(world.dec.deg),
            "peak_significance": peak_snr, "pixel_count": pixel_count,
            "flux_jy": flux, "flux_err_jy": flux_err,
            "astrometric_uncertainty_arcsec": astrometric_error,
            "fwhm_arcsec": float(measured_fwhm), "aperture_radius_pixels": radius,
            "reliable": not reasons, "limitations": reasons,
        })
    return sources


def _coordinates(catalog):
    return SkyCoord([s["ra_deg"] for s in catalog] * u.deg,
                    [s["dec_deg"] for s in catalog] * u.deg, frame="icrs")


def associate_epoch_sources(first: list[dict], second: list[dict], dt_days: float,
                            parameters=DEFAULT_MATCHING_PARAMETERS) -> dict:
    """Associate all plausible pairs; reject ambiguous matches, do not force one.

    Stationary matches anchor the relative astrometric error. Remaining sources
    can be possible movers only if both have unique partners in the bounded
    search, significant displacement, and compatible aperture fluxes.
    """
    result: dict[str, Any] = {"associations": [], "reference_source_count": 0,
                              "registration_error_arcsec": None,
                              "reference_frame_verified": False}
    if not first or not second or not np.isfinite(dt_days) or dt_days == 0:
        for epoch, catalog in [(1, first), (2, second)]:
            for s in catalog:
                result["associations"].append(_unmatched(s, epoch, "No independently measured counterpart or nonzero baseline"))
        return result
    c1, c2 = _coordinates(first), _coordinates(second)
    separation = c1[:, None].separation(c2[None, :]).arcsec
    uncertainty = np.hypot(np.array([s["astrometric_uncertainty_arcsec"] for s in first])[:, None],
                           np.array([s["astrometric_uncertainty_arcsec"] for s in second])[None, :])
    reliable = (np.array([s["reliable"] for s in first])[:, None] &
                np.array([s["reliable"] for s in second])[None, :])
    match_radius = np.maximum(parameters.psf_fwhm_arcsec / 2,
                              parameters.stationary_match_sigma * uncertainty)
    near = separation <= match_radius
    # Crowding checks count unreliable detections too: a blend is not an anchor.
    stationary = near & reliable & (separation <= parameters.stationary_match_sigma * uncertainty)
    anchors = [(i, j) for i, j in zip(*np.where(stationary))
               if near[i].sum() == 1 and near[:, j].sum() == 1]
    rms = float(np.sqrt(np.mean([separation[i, j]**2 for i, j in anchors]))) if anchors else None
    verified = (len(anchors) >= parameters.min_reference_sources and rms is not None and
                rms <= parameters.psf_fwhm_arcsec / 4)
    result.update(reference_source_count=len(anchors), registration_error_arcsec=rms,
                  reference_frame_verified=verified)
    used1, used2 = set(), set()
    for i, j in anchors:
        used1.add(i); used2.add(j)
        result["associations"].append(_matched(first[i], second[j], c1[i], c2[j], dt_days,
            uncertainty[i, j], rms or 0.0, verified, parameters, stationary=True))
    # Exclude already stationary sources; unmatched neighbors still count as ambiguity.
    candidates = separation <= parameters.motion_search_radius_arcsec
    for i in used1:
        candidates[i, :] = False
    for j in used2:
        candidates[:, j] = False
    for i, j in zip(*np.where(candidates)):
        if candidates[i].sum() != 1 or candidates[:, j].sum() != 1 or not reliable[i, j]:
            continue
        used1.add(int(i)); used2.add(int(j))
        result["associations"].append(_matched(first[i], second[j], c1[i], c2[j], dt_days,
            uncertainty[i, j], rms or 0.0, verified, parameters, stationary=False))
    for epoch, catalog, used in [(1, first, used1), (2, second, used2)]:
        for i, source in enumerate(catalog):
            if i not in used:
                result["associations"].append(_unmatched(source, epoch,
                    "No unique reliable counterpart within the search radius; unmatched or ambiguous detection"))
    return result


def _unmatched(source, epoch, reason):
    return {"epoch_1_source": source if epoch == 1 else None,
            "epoch_2_source": source if epoch == 2 else None,
            "association_status": "UNMATCHED_OR_AMBIGUOUS",
            "classification": "INSUFFICIENT_EVIDENCE", "rationale": reason,
            "angular_displacement_arcsec": None, "displacement_significance": None,
            "proper_motion_arcsec_per_yr": None}


def _matched(first, second, c1, c2, dt_days, pair_uncertainty, registration_error,
             verified, parameters, stationary):
    separation = float(c1.separation(c2).arcsec)
    uncertainty = float(np.hypot(pair_uncertainty, registration_error))
    significance = separation / uncertainty
    east, north = c1.spherical_offsets_to(c2)
    f1, f2 = first["flux_jy"], second["flux_jy"]
    e1, e2 = first["flux_err_jy"], second["flux_err_jy"]
    photometric_error = float(np.sqrt(e1**2 + e2**2 +
        (parameters.photometric_fractional_floor * f1)**2 +
        (parameters.photometric_fractional_floor * f2)**2))
    flux_significance = abs(f2 - f1) / photometric_error
    category = "INSUFFICIENT_EVIDENCE"
    reason = "Too few consistent stationary references to verify relative astrometry"
    if verified:
        if stationary:
            category = "VARIABLE_SOURCE" if flux_significance >= parameters.variability_sigma else "STATIONARY_ASTRONOMICAL_SOURCE"
            reason = "Unique celestial counterpart consistent with stationary coordinates; aperture fluxes compared with propagated errors"
        elif significance >= parameters.motion_significance_sigma:
            flux_tolerance = parameters.stationary_match_sigma * np.hypot(e1, e2) + parameters.motion_flux_fractional_tolerance * max(abs(f1), abs(f2))
            if abs(f2 - f1) <= flux_tolerance:
                category = "POSSIBLE_MOVING_OBJECT_CANDIDATE"
                reason = "Unique bounded-search counterpart with compatible flux and significant measured displacement; two-epoch association requires follow-up"
            else:
                reason = "Displaced detections have incompatible aperture fluxes; association unverified"
        else:
            reason = "Displacement lies between stationary-consistency and motion-evidence thresholds"
    moving = category == "POSSIBLE_MOVING_OBJECT_CANDIDATE"
    return {"epoch_1_source": first, "epoch_2_source": second,
            "association_status": "MATCHED", "classification": category, "rationale": reason,
            "angular_displacement_arcsec": separation, "displacement_uncertainty_arcsec": uncertainty,
            "displacement_significance": significance, "flux_change_significance": flux_significance,
            "delta_ra_arcsec": float(east.arcsec), "delta_dec_arcsec": float(north.arcsec),
            "proper_motion_arcsec_per_yr": separation / abs(dt_days / 365.25) if moving else None,
            "east_motion_arcsec_per_yr": float(east.arcsec) / (dt_days / 365.25) if moving else None,
            "north_motion_arcsec_per_yr": float(north.arcsec) / (dt_days / 365.25) if moving else None}


def investigate_epoch_motion(m1, m2, obs1, obs2, registration,
                             parameters=DEFAULT_MATCHING_PARAMETERS):
    """Guard motion analysis independently of the legacy visual comparison path."""
    reasons = []
    dt = obs2.obs_time_mjd - obs1.obs_time_mjd
    if obs1.target != obs2.target:
        reasons.append("Epochs belong to different targets")
    if (obs1.obs_id, obs1.band) == (obs2.obs_id, obs2.band):
        reasons.append("Two distinct observation products are required")
    if obs1.band != obs2.band:
        reasons.append("Motion analysis requires matching spectral bands")
    if not np.isfinite(dt) or dt == 0:
        reasons.append("Two distinct finite observation epochs are required")
    if not registration.get("wcs_aligned"):
        reasons.append("Celestial registration did not succeed")
    overlap = registration.get("overlap_fraction", 0)
    if not np.isfinite(overlap) or overlap < parameters.min_overlap_fraction:
        reasons.append("Insufficient common celestial footprint")
    for index, (model, obs) in enumerate([(m1, obs1), (m2, obs2)], 1):
        if celestial_wcs_error(model) is not None:
            reasons.append(f"Epoch {index} lacks valid celestial WCS")
        if model.get("quality_verified") is not True:
            reasons.append(f"Epoch {index} has unverified quality flags")
        if model.get("science_units_verified") is not True:
            reasons.append(f"Epoch {index} has unverified science/variance units")
        if model.get("variance_provenance") != "MEASURED":
            reasons.append(f"Epoch {index} lacks measured variance")
        if obs.screening_status not in {"PASSED_CLEAN", "FEASIBLE_WITH_CAVEATS"}:
            reasons.append(f"Epoch {index} quality screening is {obs.screening_status}")
    result = {"status": "INSUFFICIENT_EVIDENCE", "failure_reasons": reasons,
              "parameters": asdict(parameters), "epoch_1_sources": [], "epoch_2_sources": [],
              "associations": [], "reference_source_count": 0,
              "reference_frame_verified": False, "registration_error_arcsec": None}
    result["inputs_valid"] = not reasons
    if reasons:
        return result
    first, second = extract_epoch_sources(m1, parameters), extract_epoch_sources(m2, parameters)
    # A counterpart must be measurable in both original frames; reject cutout edges.
    for catalog, other in [(first, m2), (second, m1)]:
        wcs = other["wcs"].celestial
        image, variance = np.asarray(other["image"]), np.asarray(other["variance"])
        scale = float(np.sqrt(np.prod(np.abs(proj_plane_pixel_scales(wcs)) * 3600)))
        radius = parameters.aperture_radius_fwhm * parameters.psf_fwhm_arcsec / scale
        yy, xx = np.indices(image.shape)
        valid = (np.isfinite(image) & np.isfinite(variance) & (variance > 0) &
                 (image < parameters.saturation_threshold_mjy_sr))
        if other.get("valid_mask") is not None:
            valid &= np.asarray(other["valid_mask"], dtype=bool)
        for source in catalog:
            x, y = wcs.world_to_pixel(SkyCoord(source["ra_deg"] * u.deg, source["dec_deg"] * u.deg))
            if not np.isfinite(x) or not np.isfinite(y) or not (radius <= x < image.shape[1]-1-radius and radius <= y < image.shape[0]-1-radius):
                source["reliable"] = False
                source["limitations"].append("Outside common interior footprint")
            else:
                aperture = (xx - x)**2 + (yy - y)**2 <= radius**2
                if not np.all(valid[aperture]):
                    source["reliable"] = False
                    source["limitations"].append("Invalid pixels in counterpart footprint aperture")
    result.update(epoch_1_sources=first, epoch_2_sources=second)
    result.update(associate_epoch_sources(first, second, dt, parameters))
    if result["reference_frame_verified"]:
        result["status"] = "VALID_FOR_SOURCE_ASSOCIATION"
    else:
        result["failure_reasons"].append("Insufficient consistent stationary reference sources")
    return result
