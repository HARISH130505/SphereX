"""
Data Service: Loads and caches SPHEREx screening data, IPAC photometry tables,
and target catalog with scientific precision.
"""
import os
import re
import csv
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone

from app.models import (
    TargetInfo,
    ObservationRecord,
    EpochGroup,
    SpectrumDataPoint,
    SpectralSummary,
)

DATA_DIR = Path(__file__).parent.parent / "data"

def _resolve_file(*candidate_names: str) -> Optional[Path]:
    search_dirs = [
        Path(__file__).parent.parent / "data",
        Path(__file__).parent.parent.parent / "data",
    ]
    for d in search_dirs:
        for name in candidate_names:
            p = d / name
            if p.exists():
                return p
    return None

BAND_INFO = {
    1: {"name": "SPHEREx-D1", "range": "0.75 - 1.1 μm", "res": "R~41"},
    2: {"name": "SPHEREx-D2", "range": "1.1 - 1.6 μm",  "res": "R~41"},
    3: {"name": "SPHEREx-D3", "range": "1.6 - 2.4 μm",  "res": "R~41"},
    4: {"name": "SPHEREx-D4", "range": "2.4 - 3.8 μm",  "res": "R~35"},
    5: {"name": "SPHEREx-D5", "range": "3.8 - 4.4 μm",  "res": "R~110"},
    6: {"name": "SPHEREx-D6", "range": "4.4 - 5.0 μm",  "res": "R~130"},
}

TARGET_COORDINATES = {
    "M101": {"ra": 210.80227, "dec": 54.34895, "cat": "Galaxy (Pinwheel)", "sat": "NONE", "desc": "Grand-design spiral galaxy with active H II star-forming regions and clean SPHEREx diffuse & compact detections."},
    "Mira": {"ra": 34.8366, "dec": -2.9776, "cat": "Pulsating Red Giant", "sat": "PRODUCT_DEPENDENT", "desc": "Prototype Mira variable. Several catalog products have invalid central pixels and verified detector flags; inspect each product capability summary."},
    "Delta Cephei": {"ra": 337.2928, "dec": 58.4152, "cat": "Cepheid Variable", "sat": "PRODUCT_DEPENDENT", "desc": "Classical Cepheid distance anchor. Catalog products contain invalid central pixels; no physical saturation state is inferred without an explicit verified flag."},
    "Algol": {"ra": 47.118, "dec": 40.956, "cat": "Eclipsing Binary", "sat": "PRODUCT_DEPENDENT", "desc": "Bright eclipsing binary. Product-level bloom, overflow, nonfinite, and usable-pixel states are reported separately."},
    "Sedna": {"ra": 55.438, "dec": 7.892, "cat": "Extreme TNO / Planet X Probe", "sat": "NONE", "desc": "Distant detached trans-Neptunian object (~84 AU). Probing extreme solar system orbits and Planet X dynamical footprints."},
    "Planet 9 Candidate Field": {"ra": 65.250, "dec": 15.500, "cat": "Outer Solar System Survey", "sat": "NONE", "desc": "Deep ecliptic survey region monitored across SPHEREx semi-annual epochs to detect high-proper-motion thermal infrared emitters."},
}

def mjd_to_iso(mjd: float) -> str:
    """Convert Modified Julian Date to ISO 8601 UTC string."""
    try:
        jd = mjd + 2400000.5
        z = int(jd + 0.5)
        f = (jd + 0.5) - z
        if z < 2299161:
            a = z
        else:
            alpha = int((z - 1867216.25) / 36524.25)
            a = z + 1 + alpha - int(alpha / 4)
        b = a + 1524
        c = int((b - 122.1) / 365.25)
        d = int(365.25 * c)
        e = int((b - d) / 30.6001)
        day = b - d - int(30.6001 * e) + f
        if e < 14:
            month = e - 1
        else:
            month = e - 13
        if month > 2:
            year = c - 4716
        else:
            year = c - 4715
        
        hours = (day - int(day)) * 24.0
        minutes = (hours - int(hours)) * 60.0
        seconds = (minutes - int(minutes)) * 60.0
        return f"{year:04d}-{month:02d}-{int(day):02d}T{int(hours):02d}:{int(minutes):02d}:{seconds:04.1f}Z"
    except Exception:
        return f"MJD {mjd:.2f}"

class DataService:
    def __init__(self):
        self._observations: List[ObservationRecord] = []
        self._spectra: List[SpectrumDataPoint] = []
        self._loaded = False
        self._load_all_data()

    def _load_all_data(self):
        if self._loaded:
            return
        self._load_screening_results()
        self._load_photometry_table()
        self._loaded = True

    def _load_screening_results(self):
        csv_path = _resolve_file("screening_results.csv", "spherex_screening_results.csv")
        if not csv_path:
            print("Warning: screening results CSV not found")
            return

        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    mjd = float(row.get("obs_time_mjd", 0.0))
                    rec = ObservationRecord(
                        obs_id=row.get("obs_id", "").strip(),
                        target=row.get("target", "").strip(),
                        band=row.get("band", "").strip(),
                        obs_time_mjd=mjd,
                        obs_time_iso=mjd_to_iso(mjd),
                        ra=TARGET_COORDINATES.get(row.get("target", ""), {}).get("ra", 0.0),
                        dec=TARGET_COORDINATES.get(row.get("target", ""), {}).get("dec", 0.0),
                        cutout_url=row.get("cutout_url", "").strip(),
                        download_status=row.get("download_status", "").strip(),
                        fits_valid=str(row.get("fits_valid", "")).strip().lower() == "true",
                        extensions_found=row.get("extensions_found", "").strip(),
                        image_shape=row.get("image_shape", "").strip(),
                        target_x=float(row["target_x"]) if row.get("target_x") else None,
                        target_y=float(row["target_y"]) if row.get("target_y") else None,
                        target_inside_cutout=str(row.get("target_inside_cutout", "")).strip().lower() == "true",
                        center_pixel_finite=str(row.get("center_pixel_finite", "")).strip().lower() == "true",
                        center_image_val=float(row["center_image_val"]) if row.get("center_image_val") else None,
                        center_var_val=float(row["center_var_val"]) if row.get("center_var_val") else None,
                        center_flags_raw=float(row["center_flags_raw"]) if row.get("center_flags_raw") else None,
                        center_flags_decoded=row.get("center_flags_decoded", "").strip(),
                        aperture_total_pixels=int(row.get("aperture_total_pixels", 29) or 29),
                        aperture_finite_pixels=int(row.get("aperture_finite_pixels", 0) or 0),
                        aperture_overflow_count=int(row.get("aperture_overflow_count", 0) or 0),
                        aperture_sur_error_count=int(row.get("aperture_sur_error_count", 0) or 0),
                        aperture_bloom_count=int(row.get("aperture_bloom_count", 0) or 0),
                        aperture_source_count=int(row.get("aperture_source_count", 0) or 0),
                        aperture_fatal_count=int(row.get("aperture_fatal_count", 0) or 0),
                        bg_usable_pixels=int(row.get("bg_usable_pixels", 0) or 0),
                        bg_median_mjy_sr=float(row["bg_median_mjy_sr"]) if row.get("bg_median_mjy_sr") else None,
                        zodi_median_mjy_sr=float(row["zodi_median_mjy_sr"]) if row.get("zodi_median_mjy_sr") else None,
                        variance_available=str(row.get("variance_available", "")).strip().lower() == "true",
                        screening_status=row.get("screening_status", "").strip(),
                        rejection_reason=row.get("rejection_reason", "").strip(),
                    )
                    self._observations.append(rec)
                except Exception as exc:
                    print(f"Skipping row parse error: {exc}")

    def _load_photometry_table(self):
        tbl_path = _resolve_file("m101_photometry.tbl", "table_photometry-this.tbl")
        if not tbl_path:
            print("Warning: photometry table not found")
            return

        with open(tbl_path, mode="r", encoding="utf-8") as f:
            lines = f.readlines()

        header_line = None
        data_start_idx = 0
        for i, line in enumerate(lines):
            line_str = line.strip()
            if line_str.startswith("|mjd") or line_str.startswith("| mjd"):
                header_line = [c.strip() for c in line_str.split("|")[1:-1]]
                data_start_idx = i + 4  # skip types, units, blank delimiter
                break

        if not header_line:
            return

        for line in lines[data_start_idx:]:
            parts = line.strip().split()
            if len(parts) < len(header_line):
                continue
            try:
                row_dict = dict(zip(header_line, parts))
                mjd = float(row_dict["mjd"])
                det_id = int(row_dict["det_id"])
                wl = float(row_dict["lambda"])
                wl_w = float(row_dict["lambda_width"])
                flux = float(row_dict["flux"])
                flux_err = float(row_dict["flux_err"])
                flux_err_tr = float(row_dict["flux_err_tractor"]) if "flux_err_tractor" in row_dict else None
                bkg = float(row_dict["flux_bkg"]) if "flux_bkg" in row_dict else None
                fit_ql = float(row_dict["fit_ql"]) if "fit_ql" in row_dict else 0.0
                flags = int(row_dict["flags"]) if "flags" in row_dict else 0
                ra = float(row_dict["ra"]) if "ra" in row_dict else 210.80227
                dec = float(row_dict["dec"]) if "dec" in row_dict else 54.34895
                pub_did = row_dict.get("obs_publisher_did", "")

                band_name = BAND_INFO.get(det_id, {}).get("name", f"SPHEREx-D{det_id}")
                snr = flux / flux_err if flux_err > 0 else 0.0

                from app.services.screening_service import decode_spherex_flags
                flags_dec = decode_spherex_flags(flags)

                sp = SpectrumDataPoint(
                    mjd=mjd,
                    det_id=det_id,
                    band_name=band_name,
                    wavelength_um=round(wl, 4),
                    wavelength_width_um=round(wl_w, 4),
                    flux_ujy=round(flux, 2),
                    flux_err_ujy=round(flux_err, 2),
                    flux_err_tractor_ujy=round(flux_err_tr, 2) if flux_err_tr is not None else None,
                    flux_bkg_mjy_sr=round(bkg, 4) if bkg is not None else None,
                    snr=round(snr, 2),
                    flags_raw=flags,
                    flags_decoded=flags_dec,
                    fit_ql=round(fit_ql, 2),
                    ra=ra,
                    dec=dec,
                    obs_publisher_did=pub_did,
                )
                self._spectra.append(sp)
            except Exception as e:
                continue

    def get_targets(self) -> List[TargetInfo]:
        results = []
        for name, meta in TARGET_COORDINATES.items():
            obs_for_target = [o for o in self._observations if o.target.lower() == name.lower()]
            clean_count = sum(1 for o in obs_for_target if o.screening_status == "PASSED_CLEAN")
            results.append(TargetInfo(
                id=name.lower().replace(" ", "-"),
                name=name,
                ra=meta["ra"],
                dec=meta["dec"],
                description=meta["desc"],
                category=meta["cat"],
                saturation_risk=meta["sat"],
                recommended_band="SPHEREx-D1 / D2" if meta["sat"] == "NONE" else "Off-center faint wings only",
                observation_count=len(obs_for_target),
                clean_count=clean_count,
            ))
        return results

    def get_observations(self, target: Optional[str] = None, status: Optional[str] = None) -> List[ObservationRecord]:
        filtered = self._observations
        if target:
            target_norm = target.strip().lower()
            filtered = [o for o in filtered if o.target.lower() == target_norm]
        if status:
            filtered = [o for o in filtered if o.screening_status == status]
        return filtered

    def get_observation_by_id(self, obs_id: str) -> Optional[ObservationRecord]:
        for o in self._observations:
            if o.obs_id == obs_id:
                return o
        return None

    def get_epochs_for_target(self, target: str = "M101") -> List[EpochGroup]:
        target_obs = [o for o in self._observations if o.target.lower() == target.lower()]
        if not target_obs:
            return []

        # Sort by MJD
        target_obs.sort(key=lambda x: x.obs_time_mjd)
        
        # Group into epochs if separated by > 30 days
        groups: List[List[ObservationRecord]] = []
        current_group: List[ObservationRecord] = []
        last_mjd = None

        for obs in target_obs:
            if last_mjd is None or (obs.obs_time_mjd - last_mjd) > 30.0:
                if current_group:
                    groups.append(current_group)
                current_group = [obs]
            else:
                current_group.append(obs)
            last_mjd = obs.obs_time_mjd
        if current_group:
            groups.append(current_group)

        result: List[EpochGroup] = []
        for idx, grp in enumerate(groups, 1):
            mjds = [o.obs_time_mjd for o in grp]
            bands = list(dict.fromkeys(o.band for o in grp))
            iso_start = grp[0].obs_time_iso.split("T")[0] if grp[0].obs_time_iso else f"MJD {min(mjds):.0f}"
            result.append(EpochGroup(
                epoch_id=idx,
                name=f"Survey Epoch {idx} ({iso_start})",
                mjd_min=min(mjds),
                mjd_max=max(mjds),
                date_label=iso_start,
                observation_count=len(grp),
                bands=bands,
                observations=grp,
            ))
        return result

    def get_m101_spectral_summary(self) -> SpectralSummary:
        pts = sorted(self._spectra, key=lambda x: x.wavelength_um)
        if not pts:
            return SpectralSummary(
                target="M101",
                ra=210.80227,
                dec=54.34895,
                total_points=0,
                wavelength_range_um=[0.74, 5.0],
                bands=[],
                points=[],
                median_snr=0.0,
            )

        wl_min = min(p.wavelength_um for p in pts)
        wl_max = max(p.wavelength_um for p in pts)
        snrs = [p.snr for p in pts]
        median_snr = sorted(snrs)[len(snrs) // 2] if snrs else 0.0
        highest = max(pts, key=lambda p: p.flux_ujy) if pts else None
        bands = list(dict.fromkeys(p.band_name for p in pts))

        return SpectralSummary(
            target="M101",
            ra=210.80227,
            dec=54.34895,
            total_points=len(pts),
            wavelength_range_um=[wl_min, wl_max],
            bands=bands,
            points=pts,
            median_snr=round(median_snr, 1),
            highest_flux_point=highest,
        )

# Global singleton
data_service = DataService()
