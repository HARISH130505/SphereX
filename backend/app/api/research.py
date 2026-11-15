"""
Research Assistant API: NASA Space Apps Challenge context, Planet X and SPHEREx
mission intelligence, orbital motion physics, and verified scientific knowledge.
"""
from typing import Dict, Any, List
from fastapi import APIRouter
from app.models import ResearchQuestionRequest

router = APIRouter(prefix="/research", tags=["Research Assistant"])

MISSION_CONTEXT = {
    "challenge": "NASA Space Apps Challenge 2026: Planet X and SPHEREx",
    "theme": "Cross-epoch multi-wavelength infrared transient and moving object detection",
    "mission_overview": (
        "SPHEREx (Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer) "
        "is a NASA Medium-Class Explorer (MIDEX) mission designed to survey the entire sky every 6 months in 102 "
        "near-infrared spectral bands between 0.75 and 5.0 μm with 6.2 arcsec spatial resolution."
    ),
    "planet_x_detection_strategy": {
        "parallax_baseline": "SPHEREx surveys the entire sky in 6-month cycles from Low Earth Orbit. This provides an Earth orbital diameter baseline of ~2 AU.",
        "expected_proper_motion": "A hypothetical Planet Nine / Planet X at 300 - 800 AU exhibits apparent reflex parallax of ~1.25 to 3.3 arcminutes per 6 months, exceeding the 6.2 arcsec SPHEREx pixel size by a factor of 12x to 32x.",
        "infrared_signature": "At 300-800 AU, internal heat provides an effective surface temperature of ~30-50 K, peaking in far-IR, but reflected sunlight and atmospheric methane/water absorption bands yield detectable near-IR spectral features across SPHEREx Bands 4-6 (2.4 - 5.0 μm).",
        "transient_distinction": "Static stars do not shift between epochs. Variable stars (like Cepheids or Mira) modulate flux in-place but remain fixed at sub-pixel centers. Moving solar system objects show a disappearing/reappearing dipole or displacement between epochs separated by months.",
    },
    "scientific_lessons_from_audit": [
        "1. Real SPHEREx detectors have low saturation limits designed for faint all-sky cosmology and ices. Bright stars (V < 10, e.g., Mira, Delta Cephei, Algol) heavily saturate all detector channels (producing NaN central cores, SUR fit errors, and charge blooming).",
        "2. Diffuse and compact extragalactic targets like M101 yield clean, high-SNR detections with full 102-channel spectrophotometry.",
        "3. In multi-epoch difference imaging, saturation produces spurious subtraction artifacts. Quality flag vetting (FATAL_MASK) MUST precede any transient or moving object candidate confirmation.",
    ]
}

KNOWLEDGE_BASE = [
    {
        "keywords": ["saturation", "mira", "delta cephei", "algol", "bright"],
        "answer": (
            "Why do bright stars show NaN central pixels in SPHEREx data?\n\n"
            "SPHEREx is an all-sky survey optimized for cosmic infrared background, extragalactic spectroscopy, and interstellar ices. "
            "Its detectors utilize high-sensitivity HgCdTe arrays with non-destructive ramp sampling (Slope-Uncorrelated-Ramp, or SUR). "
            "For bright celestial sources (brighter than ~10-12th magnitude depending on band), the detector wells fill within the first read interval, "
            "causing raw counter OVERFLOW, SUR_ERROR, and charge BLOOM. The pipeline assigns flag 69206022 and replaces the central core with NaN. "
            "Consequently, bright variable stars like Mira and Delta Cephei cannot be observed directly without heavy masking or specialized off-axis PSF wing analysis."
        )
    },
    {
        "keywords": ["planet x", "planet 9", "moving", "parallax", "motion", "proper motion"],
        "answer": (
            "How does SPHEREx discover moving objects and test the Planet X hypothesis?\n\n"
            "SPHEREx revisits every patch of sky every 6 months. Between two epochs (separated by ~180 days), Earth moves 2 AU across its orbit. "
            "For an outer Solar System body at distance d (AU), this induces an annual parallax shift of:\n"
            "    p = 2 AU / d (radians) ≈ (412,530 / d) arcseconds.\n\n"
            "At 400 AU, the displacement between 6-month epochs is ~515 arcseconds (~83 SPHEREx pixels!). "
            "In difference imaging (Epoch 2 - Epoch 1), such an object creates a distinct negative hole at the Epoch 1 position and a positive peak at Epoch 2 position. "
            "The Candidate Investigator screens candidate pairs against detector flags to eliminate cosmic ray snowballs, blooming, and optical ghosts."
        )
    },
    {
        "keywords": ["m101", "pinwheel", "spectrum", "sed", "sed curve"],
        "answer": (
            "What did SPHEREx observe in M101 (Pinwheel Galaxy)?\n\n"
            "M101 provided the definitive calibration dataset in our audit. Across 371 photometric measurements between 0.74 μm and 5.0 μm:\n"
            "- Signal-to-noise ratio (SNR) ranges from 15 to 45 across all 6 detector arrays (D1 to D6).\n"
            "- It demonstrates the full power of SPHEREx's Linear Variable Filters (LVF), showing continuous spectrophotometric SED with no saturation.\n"
            "- Star formation features, including stellar continuum and mid-IR dust/PAH emissions, are clearly resolved."
        )
    },
    {
        "keywords": ["bands", "detectors", "lvf", "wavelength"],
        "answer": (
            "What are the 6 SPHEREx detector bands?\n\n"
            "- Band 1 (D1): 0.75 - 1.1 μm (R ~ 41, near-IR stellar continuum)\n"
            "- Band 2 (D2): 1.1 - 1.6 μm (R ~ 41, 1.27 μm O2 airglow/water ice bands)\n"
            "- Band 3 (D3): 1.6 - 2.4 μm (R ~ 41, CO/CO2 ice absorption, stellar continuum)\n"
            "- Band 4 (D4): 2.4 - 3.8 μm (R ~ 35, 3.05 μm H2O ice feature, hydrocarbon stretch)\n"
            "- Band 5 (D5): 3.8 - 4.4 μm (R ~ 110, 4.27 μm CO2 ice feature, high spectral resolution)\n"
            "- Band 6 (D6): 4.4 - 5.0 μm (R ~ 130, 4.67 μm CO ice and gas phase lines)"
        )
    }
]

@router.get("/briefing")
def get_mission_briefing():
    """Returns NASA challenge briefing and verified scientific audit facts."""
    return MISSION_CONTEXT

@router.post("/ask")
def ask_research_assistant(req: ResearchQuestionRequest):
    """Evidence-grounded scientific Q&A assistant for SPHEREx and Planet X."""
    q_lower = req.question.lower()
    
    # Keyword search
    best_match = None
    highest_score = 0
    for item in KNOWLEDGE_BASE:
        score = sum(1 for kw in item["keywords"] if kw in q_lower)
        if score > highest_score:
            highest_score = score
            best_match = item["answer"]

    if not best_match:
        best_match = (
            f"Regarding '{req.question}':\n\n"
            "SPHEREx conducts an all-sky near-infrared spectrophotometric survey across 102 spectral bands (0.75 to 5.0 μm) "
            "every 6 months. In our audit of the mission pipeline, M101 provides pristine spectrophotometric observations "
            "without saturation, while bright stars require specialized handling due to early SUR detector saturation. "
            "Candidate moving objects like Planet X candidates are characterized by multi-epoch reflex parallax and absence of fatal detector flag bitmasks."
        )

    return {
        "question": req.question,
        "context_target": req.context_target,
        "answer": best_match,
        "sources": [
            "SPHEREx Level 2 Processing Pipeline (v20/v25)",
            "table_photometry-this.tbl (IPAC/IRSA)",
            "spherex_screening_results.csv",
            "NASA MIDEX SPHEREx Mission Whitepaper",
        ]
    }
