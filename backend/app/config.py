"""
Global Configuration for SPHEREx Explorer Backend.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]  # self-contained backend root
# Hosted environment variables always win in production. Local development keeps
# the existing backend/.env behavior without reading the obsolete root env file.
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
if ENVIRONMENT != "production":
    load_dotenv(BASE_DIR / '.env', override=True)
DATA_DIR = Path(os.getenv("SPHEREX_DATA_DIR", str(BASE_DIR / "data"))).expanduser().resolve()
DEMO_DIR = DATA_DIR / "demo"
CACHE_DIR = Path(os.getenv("SPHEREX_CACHE_DIR", str(DATA_DIR / "cache"))).expanduser().resolve()

# Ensure directories exist
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Server Config
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 8000))
ALLOWED_ORIGINS = [value.strip().rstrip('/') for value in os.getenv('SPHEREX_ALLOWED_ORIGINS',
    '' if ENVIRONMENT == 'production' else 'http://localhost:3000,http://127.0.0.1:3000').split(',') if value.strip()]

# SPHEREx IRSA Endpoints
TAP_URL = os.getenv("SPHEREX_TAP_URL", "https://irsa.ipac.caltech.edu/TAP")
IBE_URL = os.getenv("SPHEREX_IBE_URL", "https://irsa.ipac.caltech.edu/ibe/data/spherex")

# Fraction of the epoch-1 grid with finite science and positive measured variance.
MIN_COMPARISON_OVERLAP = float(os.getenv("SPHEREX_MIN_COMPARISON_OVERLAP", "0.5"))
if not 0 < MIN_COMPARISON_OVERLAP <= 1:
    raise ValueError("SPHEREX_MIN_COMPARISON_OVERLAP must be finite and in (0, 1]")
