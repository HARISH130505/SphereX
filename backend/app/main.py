"""
Main FastAPI Application for SPHEREx Explorer Backend.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.services.product_identity import AmbiguousObservationError
from fastapi.middleware.cors import CORSMiddleware
from app.config import ALLOWED_ORIGINS

from app.api.routes.health import router as health_router
from app.api.routes.observations import router as obs_router
from app.api.routes.images import router as images_router
from app.api.routes.comparisons import router as comparisons_router
from app.api.routes.candidates import router as candidates_router
from app.api.routes.research import router as research_router
from app.api.routes.spectral import router as spectral_router
from app.api.routes.coverage import router as coverage_router

app = FastAPI(
    title="SPHEREx Explorer Scientific API",
    description="Backend engine powering the NASA Space Apps Challenge 2026: Planet X and SPHEREx Explorer web application.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(AmbiguousObservationError)
async def ambiguous_observation_handler(request: Request, exc: AmbiguousObservationError):
    return JSONResponse(status_code=409, content={"detail": {
        "code": "AMBIGUOUS_OBSERVATION_ID", "message": str(exc),
        "identifier": exc.identifier, "product_ids": exc.product_ids,
    }})

# Include All API Route Modules under /api
app.include_router(health_router, prefix="/api")
app.include_router(obs_router, prefix="/api")
app.include_router(images_router, prefix="/api")
app.include_router(comparisons_router, prefix="/api")
app.include_router(candidates_router, prefix="/api")
app.include_router(research_router, prefix="/api")
app.include_router(spectral_router, prefix="/api")
app.include_router(coverage_router, prefix="/api")

@app.get("/")
def root():
    return {
        "service": "SPHEREx Explorer Scientific API",
        "docs": "/docs",
        "health": "/api/health",
    }
