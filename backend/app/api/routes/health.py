"""
Health check route.
"""
from fastapi import APIRouter
from app.services.storage.repository import repository

router = APIRouter(tags=["Health"])

@router.get("/health")
def get_health():
    obs = repository.get_all()
    clean = sum(1 for o in obs if o.screening_status == "PASSED_CLEAN")
    return {
        "status": "HEALTHY",
        "service": "SPHEREx Explorer Backend",
        "version": "1.0.0",
        "records_loaded": len(obs),
        "clean_records": clean,
    }
