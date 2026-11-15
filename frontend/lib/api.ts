import type { EvidenceDossier } from "./types";

/** API requests use the Next.js proxy so the browser stays on the site origin. */
const API_BASE = "/api";

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${cleanPath}`, init);
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new Error("Cannot reach the application API. Check that the frontend and FastAPI backend are running.");
  }
  // Keep structured FastAPI errors (including archive failures) available to callers.
  if ([500, 502, 503, 504].includes(response.status) &&
      !response.headers.get("content-type")?.includes("application/json")) {
    throw new Error("Scientific backend unavailable. Start FastAPI on port 8000, or configure SPHEREX_BACKEND_URL and restart Next.js.");
  }
  return response;
}

export interface TargetInfo {
  exploration_status?: string;
  id: string;
  name: string;
  ra: number;
  dec: number;
  description: string;
  category: string;
  saturation_risk: "NONE" | "LOW" | "MEDIUM" | "CRITICAL_SATURATED" | "PRODUCT_DEPENDENT";
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
  screening_status: "PASSED_CLEAN" | "FEASIBLE_WITH_CAVEATS" | "REJECTED_SATURATED" | "FAILED_DOWNLOAD" | string;
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
  comparison_validity: import("./types").ComparisonValidity;
  data_quality: Record<string, import("./types").EpochDataQuality>;
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
  motion_analysis?: import("./types").MotionAnalysis;
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
  detected_sources?: import("./types").DetectedSource[];
  evidence_dossier?: EvidenceDossier;
  evidence_report_markdown?: string;
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
  bands: string[];
  points: SpectrumDataPoint[];
  median_snr: number;
  highest_flux_point?: SpectrumDataPoint;
}

export async function fetchHealth() {
  const res = await apiFetch("/health");
  if (!res.ok) throw new Error("Backend offline");
  return res.json();
}

export async function fetchTargets(): Promise<TargetInfo[]> {
  const res = await apiFetch("/sky/targets");
  if (!res.ok) throw new Error("Failed to fetch targets");
  return res.json();
}

export async function fetchObservations(target?: string, status?: string, signal?: AbortSignal): Promise<ObservationRecord[]> {
  const params = new URLSearchParams();
  if (target) params.set("target", target);
  if (status) params.set("status", status);
  const res = await apiFetch(`/sky/observations?${params.toString()}`, { signal });
  if (!res.ok) throw new Error("Failed to fetch observations");
  return res.json();
}

export async function fetchObservationCutout(obsId: string, stretch = "asinh", colormap = "plasma", signal?: AbortSignal) {
  const res = await apiFetch(`/sky/cutout/${encodeURIComponent(obsId)}?stretch=${stretch}&colormap=${colormap}`, { signal });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    const detail = errorData.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.message || `Failed to render cutout (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchEpochs(target: string): Promise<EpochGroup[]> {
  const res = await apiFetch(`/epoch/groups/${target}`);
  if (!res.ok) throw new Error("Failed to fetch epochs");
  return res.json();
}

export async function compareEpochs(
  epoch1Id: string,
  epoch2Id: string,
  stretch = "asinh",
  colormap = "coolwarm"
): Promise<EpochComparisonResponse> {
  const res = await apiFetch(`/epoch/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      epoch_1_product_id: epoch1Id,
      epoch_2_product_id: epoch2Id,
      stretch,
      colormap,
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.message || "Comparison failed");
  }
  return res.json();
}

export async function fetchSpectralSummary(): Promise<SpectralSummary> {
  const res = await apiFetch("/spectral/m101");
  if (!res.ok) throw new Error("Failed to load spectral SED");
  return res.json();
}

export async function askResearchAssistant(question: string, contextTarget = "M101") {
  const res = await apiFetch("/research/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, context_target: contextTarget }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "Research query failed");
  }
  return res.json();
}

export async function fetchMissionBriefing() {
  const res = await apiFetch("/research/briefing");
  if (!res.ok) throw new Error("Failed to load briefing");
  return res.json();
}

export interface QualityEvaluationRequest {
  center_finite: boolean;
  center_flags_raw?: number;
  aperture_fatal_count: number;
  aperture_total_pixels: number;
  bg_usable_pixels: number;
  variance_available: boolean;
  target_inside: boolean;
  aperture_fatal_tolerance?: number;
}

export interface QualityEvaluationResponse {
  status: string;
  reason: string;
  usable: boolean;
  decoded_flags: string[];
}

export async function evaluateCustomThresholds(params: QualityEvaluationRequest): Promise<QualityEvaluationResponse> {
  const res = await apiFetch("/candidates/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error("Evaluation failed");
  return res.json();
}

export async function fetchTargetTimeline(target: string): Promise<import("./types").TargetTimelineResponse> {
  const res = await apiFetch(`/sky/timeline/${encodeURIComponent(target)}`);
  if (!res.ok) throw new Error(`Failed to fetch timeline for ${target}`);
  return res.json();
}

export async function fetchCoverageReport(target: string, live = false): Promise<import("./types").CoverageReport> {
  const res = await apiFetch(`/coverage/${encodeURIComponent(target)}?live=${live}`);
  if (!res.ok) throw new Error(`Coverage search failed for ${target}`);
  return res.json();
}
