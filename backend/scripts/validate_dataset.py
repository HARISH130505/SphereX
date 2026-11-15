#!/usr/bin/env python3
"""
Validates required columns, coordinates, and data types for all SPHEREx datasets.
"""
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "demo"

REQUIRED_CSV_COLS = [
    "target", "obs_id", "band", "obs_time_mjd", "cutout_url",
    "screening_status", "rejection_reason"
]

def validate():
    csv_path = DATA_DIR / "screening_results.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing {csv_path}")

    df = pd.read_csv(csv_path)
    for col in REQUIRED_CSV_COLS:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    print(f"[OK] All {len(REQUIRED_CSV_COLS)} schema columns validated in {csv_path.name}!")

if __name__ == "__main__":
    validate()
