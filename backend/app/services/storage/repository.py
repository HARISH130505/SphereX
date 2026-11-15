"""
Data Repository: Manages persistence and in-memory caches for SPHEREx observations.
"""
import csv
import json
from pathlib import Path
from typing import List, Optional, Dict
from app.config import DEMO_DIR
from app.services.product_identity import AmbiguousObservationError
from app.schemas.observation import ObservationSchema, TargetSchema

# Target Registry
TARGETS_METADATA = {
    "M101": {"ra": 210.80227, "dec": 54.34895, "cat": "Galaxy (Pinwheel)", "sat": "NONE", "desc": "Clean SPHEREx diffuse & compact detection across all 6 LVF arrays."},
    "Mira": {"ra": 34.8366, "dec": -2.9776, "cat": "Pulsating Red Giant", "sat": "PRODUCT_DEPENDENT", "desc": "Prototype Mira variable. Several catalog products have invalid central pixels and verified detector flags; inspect each product capability summary."},
    "Delta Cephei": {"ra": 337.2928, "dec": 58.4152, "cat": "Cepheid Variable", "sat": "PRODUCT_DEPENDENT", "desc": "Classical Cepheid distance anchor. Catalog products contain invalid central pixels; no physical saturation state is inferred without an explicit verified flag."},
    "Algol": {"ra": 47.118, "dec": 40.956, "cat": "Eclipsing Binary", "sat": "PRODUCT_DEPENDENT", "desc": "Demon Star eclipsing binary. Product-level bloom, overflow, nonfinite, and usable-pixel states are reported separately."},
}

class ObservationRepository:
    def __init__(self):
        self._observations: List[ObservationSchema] = []
        self._load()
        verified_path = DEMO_DIR / 'verified_targets.json'
        if verified_path.exists():
            for name, entry in json.loads(verified_path.read_text(encoding='utf-8')).items():
                if not entry.get('comparison_validity', {}).get('scientific_analysis_allowed'):
                    continue
                TARGETS_METADATA[name] = {'ra': entry['ra'], 'dec': entry['dec'],
                    'cat': 'Galaxy', 'sat': 'PRODUCT_DEPENDENT',
                    'desc': 'Public SPHEREx products with a validated registered comparison pair.'}
                self._observations.extend(ObservationSchema.model_validate(row) for row in entry['observations'])

    def _load(self):
        csv_path = DEMO_DIR / "screening_results.csv"
        if not csv_path.exists():
            return
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    mjd = float(row.get("obs_time_mjd", 0.0))
                    target = row.get("target", "").strip()
                    meta = TARGETS_METADATA.get(target, {})
                    rec = ObservationSchema(
                        obs_id=row.get("obs_id", "").strip(),
                        obs_publisher_did=row.get("obs_publisher_did") or None,
                        target=target,
                        band=row.get("band", "").strip(),
                        obs_time_mjd=mjd,
                        ra=meta.get("ra", 0.0),
                        dec=meta.get("dec", 0.0),
                        cutout_url=row.get("cutout_url", "").strip(),
                        download_status=row.get("download_status", "").strip(),
                        fits_valid=str(row.get("fits_valid", "")).strip().lower() == "true",
                        extensions_found=row.get("extensions_found", "").strip(),
                        image_shape=row.get("image_shape", "(59, 58)").strip(),
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
                except Exception:
                    continue

    def get_all(self, target: Optional[str] = None, status: Optional[str] = None) -> List[ObservationSchema]:
        res = self._observations
        if target:
            res = [o for o in res if o.target.lower() == target.lower()]
        if status and status != "ALL":
            res = [o for o in res if o.screening_status == status]
        return res

    def get_by_id(self, obs_id: str) -> Optional[ObservationSchema]:
        # Exact canonical identity first; legacy IDs are accepted only if unique.
        matches = [o for o in self._observations if o.product_id == obs_id]
        if not matches:
            matches = [o for o in self._observations if o.obs_id == obs_id]
        if len(matches) > 1:
            raise AmbiguousObservationError(obs_id, matches)
        return matches[0] if matches else None

    def get_targets(self) -> List[TargetSchema]:
        res = []
        for name, meta in TARGETS_METADATA.items():
            obs = self.get_all(name)
            clean = sum(1 for o in obs if o.screening_status == "PASSED_CLEAN")
            res.append(TargetSchema(
                id=name.lower().replace(" ", "-"),
                name=name,
                ra=meta["ra"],
                dec=meta["dec"],
                description=meta["desc"],
                category=meta["cat"],
                saturation_risk=meta["sat"],
                recommended_band="D1 / D2" if meta["sat"] == "NONE" else "Off-center wings only",
                observation_count=len(obs),
                clean_count=clean,
                exploration_status=('READY FOR EXPLORATION' if name == 'M101' or meta.get('cat') == 'Galaxy' else
                    'LIMITED SCIENTIFIC USABILITY' if any(o.fits_valid for o in obs) else
                    'NO VERIFIED PUBLIC OBSERVATIONS'),
            ))
        return res

    def get_m101_photometry(self) -> List[dict]:
        tbl_path = DEMO_DIR / "m101_photometry.tbl"
        if not tbl_path.exists():
            return []
        with open(tbl_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        header_line = None
        data_start = 0
        for i, line in enumerate(lines):
            line_str = line.strip()
            if line_str.startswith("|mjd") or line_str.startswith("| mjd"):
                header_line = [c.strip() for c in line_str.split("|")[1:-1]]
                data_start = i + 4
                break
        if not header_line:
            return []
        points = []
        for line in lines[data_start:]:
            parts = line.strip().split()
            if len(parts) < len(header_line):
                continue
            try:
                row = dict(zip(header_line, parts))
                flux = float(row["flux"])
                err = float(row["flux_err"])
                det_id = int(row["det_id"])
                points.append({
                    "mjd": float(row["mjd"]),
                    "det_id": det_id,
                    "band_name": f"SPHEREx-D{det_id}",
                    "wavelength_um": round(float(row["lambda"]), 4),
                    "wavelength_width_um": round(float(row["lambda_width"]), 4),
                    "flux_ujy": round(flux, 2),
                    "flux_err_ujy": round(err, 2),
                    "snr": round(flux / err, 2) if err > 0 else 0.0,
                    "flags_raw": int(row.get("flags", 0)),
                    "fit_ql": round(float(row.get("fit_ql", 0.0)), 2),
                    "ra": float(row.get("ra", 210.80227)),
                    "dec": float(row.get("dec", 54.34895)),
                    "obs_publisher_did": row.get("obs_publisher_did", ""),
                })
            except Exception:
                continue
        return points

repository = ObservationRepository()
