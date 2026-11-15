"""
Semantic knowledge base for SPHEREx and Planet X research questions.
"""
RESEARCH_KNOWLEDGE = [
    {
        "keywords": ["saturation", "mira", "delta cephei", "algol", "nan"],
        "answer": (
            "Why do bright stars exhibit NaN central pixels in SPHEREx?\n\n"
            "SPHEREx's HgCdTe detectors are configured with high photometric gain optimized for faint diffuse cosmology "
            "and extragalactic spectrophotometry. Stars brighter than V ~ 10 exceed the pixel full-well depth during the "
            "initial SUR (Slope-Uncorrelated-Ramp) read interval. The pipeline sets bitmask 69206022 (OVERFLOW | SUR_ERROR | BLOOM) "
            "and marks central core pixels as NaN."
        )
    },
    {
        "keywords": ["planet x", "planet 9", "parallax", "motion", "reflex"],
        "answer": (
            "How does SPHEREx discover Planet X through reflex parallax?\n\n"
            "SPHEREx revisits every celestial coordinate every 6 months, establishing a 2 AU Earth orbital baseline. "
            "An outer Solar System body at distance d (AU) experiences apparent reflex parallax shift:\n"
            "    p = 2 AU / d (radians) ≈ 412,530 / d arcseconds.\n\n"
            "At 400 AU, the displacement between 6-month epochs is ~515 arcseconds (~83 pixels), creating an unambiguous "
            "negative/positive dipole signature in differential subtraction images."
        )
    },
    {
        "keywords": ["bands", "lvf", "detectors", "wavelength"],
        "answer": (
            "What are the 6 SPHEREx detector bands?\n\n"
            "- D1: 0.75 - 1.1 μm (R ~ 41, near-IR continuum)\n"
            "- D2: 1.1 - 1.6 μm (R ~ 41, water ice / airglow)\n"
            "- D3: 1.6 - 2.4 μm (R ~ 41, CO/CO2 ice)\n"
            "- D4: 2.4 - 3.8 μm (R ~ 35, 3.05 μm H2O ice feature)\n"
            "- D5: 3.8 - 4.4 μm (R ~ 110, 4.27 μm CO2 ice)\n"
            "- D6: 4.4 - 5.0 μm (R ~ 130, 4.67 μm CO ice and gas lines)"
        )
    }
]

def search_literature(query: str) -> str:
    q_lower = query.lower()
    for item in RESEARCH_KNOWLEDGE:
        if any(kw in q_lower for kw in item["keywords"]):
            return item["answer"]
    return (
        f"Research context for '{query}': SPHEREx is an all-sky spectrophotometric survey measuring 102 spectral channels "
        "(0.75 to 5.0 μm) every 6 months. Clean faint targets like M101 yield high SNR spectrophotometry, while bright stars "
        "saturate early reads. Transients and Solar System moving objects are identified via 6-month reflex parallax dipoles."
    )
