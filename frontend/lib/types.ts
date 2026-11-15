export type EvidenceClassification =
  | "STATIONARY_ASTRONOMICAL_SOURCE"
  | "VARIABLE_SOURCE"
  | "DETECTOR_ARTIFACT"
  | "POSSIBLE_MOVING_OBJECT_CANDIDATE"
  | "INSUFFICIENT_EVIDENCE";

export interface EvidenceDossier {
  schema_version: string;
  dossier_id: string;
  target: string;
  assessment: {
    classification: EvidenceClassification;
    detected: boolean;
    motion_detected: boolean;
    scientific_validity_status: string;
    scientific_assessment: string;
    confidence_probability: null;
    confidence_score_calibrated: false;
  };
  reproducibility: {
    algorithm: "SHA-256";
    canonicalization: string;
    pipeline: string;
    pipeline_version: string;
    provenance_status: "COMPLETE" | "PARTIAL";
    manifest_sha256: string;
    reproducibility_hash: string;
    evidence_sha256: string;
    generated_at_utc: string;
    manifest: Record<string, unknown>;
  };
  markdown_report?: string;
  [key: string]: unknown;
}

export interface TargetInfo {
  exploration_status?: string;
  id: string;
  name: string;
  ra: number;
  dec: number;
  description: string;
  category: string;
  saturation_risk: "NONE" | "LOW" | "MEDIUM" | "CRITICAL_SATURATED" | string;
  recommended_band?: string;
  observation_count: number;
  clean_count: number;
}

export interface ObservationRecord {
  collection?: string;
  access_url?: string;
  product_id: string;
  archive_product_id: string | null;
  obs_publisher_did?: string | null;
  obs_id: string;
  target: string;
  band: string;
  obs_time_mjd: number;
  obs_time_iso?: string;
  ra: number;
  dec: number;
  cutout_url: string;
  download_status: string;
  fits_valid: boolean;
  extensions_found: string;
  image_shape: string;
  target_x?: number;
  target_y?: number;
  target_inside_cutout: boolean;
  center_pixel_finite: boolean;
  center_image_val?: number;
  center_var_val?: number;
  center_flags_raw?: number;
  center_flags_decoded?: string;
  aperture_total_pixels: number;
  aperture_finite_pixels: number;
  aperture_overflow_count: number;
  aperture_sur_error_count: number;
  aperture_bloom_count: number;
  aperture_source_count: number;
  aperture_fatal_count: number;
  bg_usable_pixels: number;
  bg_median_mjy_sr?: number;
  zodi_median_mjy_sr?: number;
  variance_available: boolean;
  screening_status: string;
  rejection_reason: string;
}

export interface EpochGroup {
  epoch_id: number;
  name: string;
  mjd_min: number;
  mjd_max: number;
  date_label: string;
  observation_count: number;
  bands: string[];
  observations: ObservationRecord[];
}

export interface EpochComparisonResponse {
  comparison_validity: ComparisonValidity;
  data_quality: Record<string, EpochDataQuality>;
  epoch_1_meta: ObservationRecord;
  epoch_2_meta: ObservationRecord;
  time_delta_days: number;
  epoch_1_image_base64: string;
  epoch_2_image_base64: string;
  difference_image_base64: string | null;
  significance_image_base64: string | null;
  flux_ratio: number | null;
  transient_score: number | null;
  motion_detected: boolean;
  motion_analysis?: MotionAnalysis;
  motion_vector_arcsec?: {
    delta_ra_arcsec: number;
    delta_dec_arcsec: number;
    proper_motion_arcsec_per_yr: number;
  };
  scientific_summary: string;
  registration_diagnostics?: {
    method?: string;
    wcs_aligned?: boolean;
    overlap_fraction?: number;
    angular_separation_arcsec?: number | null;
    subpixel_offset_xy?: number[] | null;
  };
  difference_statistics?: {
    mean_diff?: number;
    median_diff?: number;
    rms_diff?: number;
    valid_pixel_count?: number;
    saturated_pixel_count?: number;
    detected_residual_sources_count?: number;
  };
  candidate_assessment?: {
    category?: string;
    detected?: boolean;
    confidence_score?: number;
    peak_sig?: number | null;
    scientific_assessment?: string;
  };
  epoch_1_original_image_base64?: string;
  epoch_2_original_image_base64?: string;
  overlap_mask_image_base64?: string;
  detected_sources?: DetectedSource[];
  evidence_dossier?: EvidenceDossier;
  evidence_report_markdown?: string;
}

export interface DetectedSource {
  source_id: number;
  centroid_xy: [number, number];
  pixel_count: number;
  peak_significance: number;
  flux: number;
  flux_err: number;
  epoch_1_flux?: number | null;
  epoch_2_flux?: number | null;
  astrometric_uncertainty_arcsec: number;
  nature: string;
  ra_deg?: number | null;
  dec_deg?: number | null;
  angular_separation_from_target_arcsec?: number | null;
  classification: "STATIONARY_ASTRONOMICAL_SOURCE" | "VARIABLE_SOURCE" | "DETECTOR_ARTIFACT" | "POSSIBLE_MOVING_OBJECT_CANDIDATE" | "INSUFFICIENT_EVIDENCE" | string;
  classification_rationale: string;
  epoch_1_detected?: boolean;
  epoch_2_detected?: boolean;
}

export interface TimelineItem {
  product_id: string;
  archive_product_id: string | null;
  obs_id: string;
  band: string;
  obs_time_mjd: number;
  obs_time_iso?: string | null;
  product_identifier: string;
  image_shape: string;
  screening_status: string;
  rejection_reason: string;
  data_quality: string;
  provenance: string;
  comparison_eligible: boolean;
  eligibility_reason: string;
}

export interface TargetTimelineResponse {
  target: string;
  category: string;
  ra: number;
  dec: number;
  coverage_status: string;
  observation_count: number;
  eligible_count: number;
  timeline: TimelineItem[];
}

export interface SpectrumDataPoint {
  mjd: number;
  det_id: number;
  band_name: string;
  wavelength_um: number;
  wavelength_width_um: number;
  flux_ujy: number;
  flux_err_ujy: number;
  flux_err_tractor_ujy?: number;
  flux_bkg_mjy_sr?: number;
  snr: number;
  flags_raw: number;
  flags_decoded: string[];
  fit_ql: number;
  ra: number;
  dec: number;
  obs_publisher_did: string;
}

export interface SpectralSummary {
  target: string;
  ra: number;
  dec: number;
  total_points: number;
  wavelength_range_um: number[];
  points: SpectrumDataPoint[];
  median_snr: number;
  highest_flux_point?: SpectrumDataPoint;
}

export interface CutoutRenderResponse {
  product_id: string;
  archive_product_id: string | null;
  obs_id: string;
  target: string;
  band: string;
  screening_status: string;
  image_shape: number[];
  target_xy: number[];
  png_base64: string;
  center_val?: number | null;
  bg_median?: number | null;
  min_val?: number | null;
  max_val?: number | null;
  median_val?: number | null;
  nan_count?: number | null;
  valid_pct?: number | null;
  wcs_info?: {
    ra_center?: number;
    dec_center?: number;
    ctype?: string[];
    pixel_scale_arcsec?: number;
  };
  source_file?: string;
  quality_summary?: DetectorQualitySummary | null;
  variance_summary?: VarianceSummary | null;
  science_valid_pixel_count?: number;
  observation_quality?: {
    observation_status: string;
    total_pixel_count: number;
    finite_pixel_count: number;
    valid_pixel_count: number;
    finite_pixel_fraction: number;
    valid_pixel_fraction: number;
    saturated_pixel_count: number;
    nonfinite_pixel_count: number;
    center_pixel: { inside: boolean; saturated: boolean; nonfinite: boolean; valid: boolean };
    capabilities: Record<string, boolean>;
    core_values_recovered_or_fabricated: false;
  };
  fits_valid: boolean;
}

export interface CoverageReport {
  target: string;
  status: string;
  search_mode?: string;
  searched_releases: string[];
  archive_tables: string[];
  footprint_rule: string;
  search_complete: boolean;
  detail?: string;
  coordinates_deg?: number[];
  fixed_coordinate_reference_deg?: number[];
  ephemerides?: { mjd: number; ra_deg: number; dec_deg: number; observer: string; source: string }[];
  local_footprint_tests?: { product_id: string; mjd: number; predicted_ra_deg: number; predicted_dec_deg: number; footprint_intersection: boolean | null; product_status: string }[];
  local_footprint_matches?: { product_id: string; mjd: number; predicted_ra_deg: number; predicted_dec_deg: number; footprint_intersection: boolean | null; product_status: string }[];
}

export interface EpochSourceMeasurement {
  source_id: number;
  ra_deg: number;
  dec_deg: number;
  flux_jy: number | null;
  flux_err_jy: number | null;
  reliable: boolean;
  limitations: string[];
}

export interface SourceAssociation {
  epoch_1_source: EpochSourceMeasurement | null;
  epoch_2_source: EpochSourceMeasurement | null;
  association_status: string;
  classification: string;
  rationale: string;
  angular_displacement_arcsec: number | null;
  displacement_uncertainty_arcsec?: number;
  displacement_significance: number | null;
  proper_motion_arcsec_per_yr: number | null;
}

export interface MotionAnalysis {
  status: string;
  failure_reasons: string[];
  reference_source_count: number;
  registration_error_arcsec: number | null;
  associations: SourceAssociation[];
  parameters: Record<string, number>;
}

export interface ComparisonValidity {
  status: "VALID_FOR_REGISTERED_COMPARISON" | "NON_SCIENTIFIC_VISUAL_COMPARISON";
  scientific_analysis_allowed: boolean;
  failure_reasons: { code: string; message: string }[];
  min_overlap_fraction: number;
  overlap_fraction: number | null;
  overlap_definition: string;
}

export interface DetectorQualitySummary {
  status: string;
  definitions_source: string;
  policy_version: string;
  issues: string[];
  mask_counts: Record<string, number>;
  definitions: { bit: number; name: string; description: string }[];
}

export interface VarianceSummary {
  provenance: string;
  unit: string | null;
  image_unit: string | null;
  units_verified: boolean;
  valid_pixel_count: number;
  invalid_pixel_count: number;
  issues: string[];
}

export interface EpochDataQuality {
  quality: DetectorQualitySummary;
  variance: VarianceSummary;
  science_valid_pixel_count: number;
}
