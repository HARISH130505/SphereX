"""
Image cutout rendering and contrast stretch routes.
Extracts and renders genuine SPHEREx FITS products.
"""
from fastapi import APIRouter, Query, HTTPException
from app.schemas.image import CutoutRenderResponse
from app.services.storage.repository import repository
from app.services.astronomy.fits_io import load_fits_image, render_png_base64
from app.services.storage.cache import cache

router = APIRouter(prefix="/sky", tags=["Images"])

@router.get("/cutout/{product_id}", response_model=CutoutRenderResponse)
def get_cutout(
    product_id: str,
    stretch: str = Query("asinh"),
    colormap: str = Query("plasma"),
    overlays: bool = Query(True),
):
    obs = repository.get_by_id(product_id)
    if not obs:
        raise HTTPException(status_code=404, detail=f"Observation {product_id} not found.")

    cache_key = f"cutout_v4_{obs.product_id}_{stretch}_{colormap}_{overlays}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Attempt genuine FITS loading
    try:
        model = load_fits_image(obs)
    except FileNotFoundError as fnf_err:
        raise HTTPException(
            status_code=404,
            detail=f"FITS file unavailable for {product_id}: {str(fnf_err)}"
        )
    except Exception as err:
        raise HTTPException(
            status_code=502,
            detail=f"Error reading genuine FITS product for {product_id}: {str(err)}"
        )

    # Render PNG base64 directly from real FITS array
    png_b64 = render_png_base64(
        model["image"],
        stretch=stretch,
        colormap=colormap,
        aperture_center=tuple(model["target_xy"]) if overlays else None,
        draw_overlays=overlays,
    )

    res = CutoutRenderResponse(
        product_id=obs.product_id,
        archive_product_id=obs.archive_product_id,
        obs_id=obs.obs_id,
        target=obs.target,
        band=obs.band,
        screening_status=obs.screening_status,
        image_shape=model["shape"],
        target_xy=model["target_xy"],
        png_base64=png_b64,
        center_val=model["center_val"],
        bg_median=obs.bg_median_mjy_sr,
        min_val=model.get("min_val"),
        max_val=model.get("max_val"),
        median_val=model.get("median_val"),
        nan_count=model.get("nan_count"),
        valid_pct=model.get("valid_pct"),
        wcs_info=model.get("wcs_info"),
        source_file=model.get("source_file"),
        quality_summary=model["quality_summary"], variance_summary=model["variance_summary"],
        science_valid_pixel_count=int(model["valid_mask"].sum()),
        observation_quality=model["observation_quality"],
        fits_valid=True,
    )

    cache.set(cache_key, res)
    return res
