"""
Sky Explorer API endpoints: Target discovery, TAP observations archive,
and FITS cutout rendering.
"""
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException

from app.models import TargetInfo, ObservationRecord
from app.services.data_service import data_service
from app.services.fits_service import fits_service

router = APIRouter(prefix="/sky", tags=["Sky Explorer"])

@router.get("/targets", response_model=List[TargetInfo])
def get_targets():
    """List curated astronomical targets with saturation indicators."""
    return data_service.get_targets()

@router.get("/observations", response_model=List[ObservationRecord])
def get_observations(
    target: Optional[str] = Query(None, description="Filter by target name (e.g. M101, Mira)"),
    status: Optional[str] = Query(None, description="Filter by screening status (e.g. PASSED_CLEAN)"),
    band: Optional[str] = Query(None, description="Filter by SPHEREx detector band"),
):
    """Query SPHEREx observations matching target or criteria."""
    obs = data_service.get_observations(target=target, status=status)
    if band:
        obs = [o for o in obs if o.band.lower() == band.lower()]
    return obs

@router.get("/cutout/{obs_id}")
def get_observation_cutout(
    obs_id: str,
    stretch: str = Query("asinh", description="Astronomical stretch (asinh, linear, log, sqrt)"),
    colormap: str = Query("plasma", description="Matplotlib colormap (plasma, viridis, inferno, coolwarm)"),
    overlays: bool = Query(True, description="Draw aperture and annulus overlays"),
):
    """Renders FITS 2D pixel array into high-contrast PNG tile."""
    rec = data_service.get_observation_by_id(obs_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Observation {obs_id} not found.")

    arrays = fits_service.get_or_generate_cutout_arrays(rec)
    tx, ty = arrays["target_xy"]
    png_b64 = fits_service.render_array_to_png_base64(
        arrays["image"],
        stretch=stretch,
        colormap=colormap,
        aperture_center=(tx, ty) if overlays else None,
        draw_overlays=overlays,
    )
    return {
        "obs_id": rec.obs_id,
        "target": rec.target,
        "band": rec.band,
        "screening_status": rec.screening_status,
        "image_shape": arrays["shape"],
        "target_xy": [round(tx, 2), round(ty, 2)],
        "png_base64": png_b64,
        "center_val": rec.center_image_val,
        "bg_median": rec.bg_median_mjy_sr,
    }
