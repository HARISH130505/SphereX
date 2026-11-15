"""
Epoch Comparison API endpoints: Temporal grouping, multi-epoch alignment,
direct subtraction, and significance differential mapping.
"""
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException, Body

from app.models import EpochGroup, EpochComparisonRequest, EpochComparisonResponse
from app.services.data_service import data_service
from app.services.fits_service import fits_service

router = APIRouter(prefix="/epoch", tags=["Epoch Comparison"])

@router.get("/groups/{target}", response_model=List[EpochGroup])
def get_target_epochs(target: str = "M101"):
    """Returns observations grouped into distinct temporal survey epochs."""
    epochs = data_service.get_epochs_for_target(target)
    if not epochs:
        raise HTTPException(status_code=404, detail=f"No epochs found for target '{target}'.")
    return epochs

@router.post("/compare", response_model=EpochComparisonResponse)
def compare_epochs(req: EpochComparisonRequest):
    """
    Executes differential analysis between two observation epochs:
    - Side-by-side aligned arrays
    - Pixel difference (Epoch 2 - Epoch 1)
    - Significance image: (I2 - I1) / sqrt(var1 + var2)
    - Flux ratio and motion detection indicators
    """
    obs1 = data_service.get_observation_by_id(req.epoch_1_obs_id)
    obs2 = data_service.get_observation_by_id(req.epoch_2_obs_id)

    if not obs1:
        raise HTTPException(status_code=404, detail=f"Observation '{req.epoch_1_obs_id}' not found.")
    if not obs2:
        raise HTTPException(status_code=404, detail=f"Observation '{req.epoch_2_obs_id}' not found.")

    result = fits_service.compute_epoch_difference(
        obs1,
        obs2,
        colormap=req.colormap,
        stretch=req.stretch,
    )
    return EpochComparisonResponse(**result)
