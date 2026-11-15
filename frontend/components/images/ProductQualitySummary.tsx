import type { DetectorQualitySummary, VarianceSummary } from "@/lib/types";

interface Props {
  label?: string;
  quality: DetectorQualitySummary;
  variance: VarianceSummary;
  scienceValidPixelCount?: number;
  observationQuality?: import("@/lib/types").CutoutRenderResponse["observation_quality"];
}

export function ProductQualitySummary({ label = "Product", quality, variance, scienceValidPixelCount, observationQuality }: Props) {
  const source = quality.definitions_source === "FITS_MP_HEADERS" ? "FITS headers" : quality.definitions_source === "DOCUMENTED_RELEASE_SCHEMA" ? "Published release schema" : "Unavailable";
  return (
    <details className="rounded-lg border border-slate-700 bg-slate-950/60 p-3 text-xs text-slate-300 space-y-2">
      <summary className="cursor-pointer font-semibold text-cyan-300">{label}: detector quality and variance</summary>
      <p>Flag metadata: {quality.status} ({source})</p>
      <p>Variance: {variance.provenance}; units {variance.unit || "unavailable"}; unit verification {variance.units_verified ? "passed" : "failed"}</p>
      <p>Science pixels usable after masks: {scienceValidPixelCount ?? "unavailable"}; invalid variance pixels: {variance.invalid_pixel_count}</p>
      {observationQuality && <>
        <p>Observation status: <strong>{observationQuality.observation_status}</strong></p>
        <p>Pixel status: {(observationQuality.valid_pixel_fraction * 100).toFixed(1)}% science-valid; {(observationQuality.finite_pixel_fraction * 100).toFixed(1)}% finite; {observationQuality.saturated_pixel_count} explicitly flagged saturated; {observationQuality.nonfinite_pixel_count} nonfinite.</p>
        <p>Central pixel: {observationQuality.center_pixel.saturated ? "flagged saturated" : observationQuality.center_pixel.nonfinite ? "nonfinite (not assumed saturated)" : observationQuality.center_pixel.valid ? "valid" : "masked"}.</p>
        <div className="flex flex-wrap gap-2">{Object.entries(observationQuality.capabilities).map(([name, allowed]) => <span key={name} className={allowed ? "text-emerald-300" : "text-rose-300"}>{name.replaceAll("_", " ")}: {allowed ? "usable" : "not supported"}</span>)}</div>
      </>}
      {[...quality.issues, ...variance.issues].map((issue, index) => <p key={index} className="text-amber-300">{issue}</p>)}
      <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono">
        {Object.entries(quality.mask_counts).filter(([, count]) => count > 0).map(([name, count]) => <span key={name}>{name}: {count}</span>)}
      </div>
      <p className="text-slate-500">Counts can overlap. SOURCE is informational. Nonfinite pixels and the brightness screen do not identify physical saturation. Mask policy: {quality.policy_version}.</p>
    </details>
  );
}
