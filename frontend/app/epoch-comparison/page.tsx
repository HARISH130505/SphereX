"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Image from "next/image";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { WorkspaceHeader, WorkspaceLink, WorkspaceMetric } from '@/components/layout/WorkspaceHeader';
import { ProductQualitySummary } from "@/components/images/ProductQualitySummary";
import { DifferenceViewer } from "@/components/images/DifferenceViewer";
import { ImageComparisonSlider } from "@/components/images/ImageComparisonSlider";
import { ObservationTimeline } from "@/components/sky/ObservationTimeline";
import { SourceAssociationTable } from "@/components/candidates/SourceAssociationTable";
import { SourceInvestigationTable } from "@/components/candidates/SourceInvestigationTable";
import { EvidenceDossierModal } from "@/components/candidates/EvidenceDossierModal";
import { fetchObservations, compareEpochs } from "@/lib/api";
import { observationKey } from "@/lib/observations";
import { ObservationRecord, EpochComparisonResponse } from "@/lib/types";
import { RefreshCw, FileText, AlertCircle } from "lucide-react";
import { useSelectedTarget, selectTarget } from '@/lib/selected-target';

export default function EpochComparisonPage() {
  const currentTarget = useSelectedTarget();
  const setCurrentTarget = selectTarget;
  const [observations, setObservations] = useState<ObservationRecord[]>([]);
  const [epoch1Id, setEpoch1Id] = useState<string>("");
  const [epoch2Id, setEpoch2Id] = useState<string>("");
  const [result, setResult] = useState<EpochComparisonResponse | null>(null);
  const [viewMode, setViewMode] = useState<"side" | "swipe" | "blink">("side");
  const [loading, setLoading] = useState<boolean>(false);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [blinkState, setBlinkState] = useState<boolean>(false);
  const [isDossierOpen, setIsDossierOpen] = useState<boolean>(false);
  const compareRequest = useRef(0);
  const comparisonObservations = useRef<ObservationRecord[]>([]);

  const runCompare = useCallback((firstId: string, secondId: string) => {
    if (!firstId || !secondId) return;
    const first = comparisonObservations.current.find(o => observationKey(o) === firstId);
    const second = comparisonObservations.current.find(o => observationKey(o) === secondId);
    if (first && second && (first.band !== second.band || firstId === secondId || first.obs_time_mjd === second.obs_time_mjd)) {
      compareRequest.current += 1;
      setLoading(false);
      setResult(null);
      setCompareError("Choose two distinct observations at different times in the same spectral band.");
      return;
    }
    const requestId = ++compareRequest.current;
    setLoading(true);
    setCompareError(null);
    setResult(null);
    compareEpochs(firstId, secondId)
      .then((res) => {
        if (requestId === compareRequest.current) setResult(res);
      })
      .catch((err: unknown) => {
        if (requestId !== compareRequest.current) return;
        console.error("Comparison error:", err);
        setCompareError(err instanceof Error ? err.message : "Failed to execute multi-epoch comparison.");
        setResult(null);
      })
      .finally(() => {
        if (requestId === compareRequest.current) setLoading(false);
      });
  }, []);

  // Reload observations whenever target changes
  useEffect(() => {
    const controller = new AbortController();
    compareRequest.current += 1;
    fetchObservations(currentTarget, undefined, controller.signal).then((obs) => {
      if(controller.signal.aborted) return;
      setObservations(obs);
      comparisonObservations.current = obs;
      const eligible = obs.filter((o) => o.fits_valid);
      const pair = eligible.flatMap((a, i) => eligible.slice(i + 1)
        .filter(b => a.band === b.band && a.obs_time_mjd !== b.obs_time_mjd)
        .map(b => [a, b] as const))[0];
      if (pair) {
        const first = observationKey(pair[0]);
        const second = observationKey(pair[1]);
        setEpoch1Id(first);
        setEpoch2Id(second);
        runCompare(first, second);
      } else if (eligible.length === 1) {
        setEpoch1Id(observationKey(eligible[0]));
        setEpoch2Id("");
        setResult(null);
      } else {
        setEpoch1Id("");
        setEpoch2Id("");
        setResult(null);
      }
    }).catch((error: unknown) => {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setObservations([]);
      setEpoch1Id("");
      setEpoch2Id("");
      setResult(null);
      setCompareError(error instanceof Error ? error.message : "Failed to load observations.");
    });
    return () => controller.abort();
  }, [currentTarget, runCompare]);

  useEffect(() => {
    if (viewMode !== "blink") return;
    const interval = setInterval(() => setBlinkState((p) => !p), 500);
    return () => clearInterval(interval);
  }, [viewMode]);

  const isSaturated =
    result?.epoch_1_meta?.screening_status === "REJECTED_SATURATED" ||
    result?.epoch_2_meta?.screening_status === "REJECTED_SATURATED";

  return (
    <div className="flex flex-col min-h-screen">
      <Navbar />
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 lg:p-8 space-y-6">
        <WorkspaceHeader section="Comparison workspace" title="The sky, across time." description="Choose two observations in the same detector band. Compare their registered images, then follow the residuals back to the evidence." action={<WorkspaceLink href="/sky-explorer">Inspect original observations</WorkspaceLink>} />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <WorkspaceMetric label="Target field" value={currentTarget} detail={`${observations.length} cataloged observation products`} />
          <WorkspaceMetric label="Epoch baseline" value={result ? `${result.time_delta_days.toFixed(3)} days` : '—'} detail="Actual elapsed time between selected observations" />
          <WorkspaceMetric label="Usable overlap" value={result?.comparison_validity.overlap_fraction != null ? `${(result.comparison_validity.overlap_fraction*100).toFixed(1)}%` : '—'} detail="Quality-valid pixels on the reference grid" />
          <WorkspaceMetric label="Comparison status" value={loading ? 'Processing' : result ? result.comparison_validity.scientific_analysis_allowed ? 'Valid comparison' : 'Visual only' : 'Awaiting pair'} detail="WCS, quality and variance safeguards apply" />
        </div>
        {/* Section 1: Target Timeline & Provenance */}
        <ObservationTimeline
          currentTarget={currentTarget}
          onSelectTarget={(t) => {setResult(null);setCompareError(null);setCurrentTarget(t);}}
          onSelectEpochPair={(id1, id2) => {
            if (id1) setEpoch1Id(id1);
            if (id2) setEpoch2Id(id2);
            runCompare(id1 || epoch1Id, id2 || epoch2Id);
          }}
          selectedEpoch1Id={epoch1Id}
          selectedEpoch2Id={epoch2Id}
        />

        {/* Section 2: Observation Pair Controls Bar */}
        <div className="glass-panel p-5 flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs font-mono font-bold text-slate-400 uppercase">Compare:</span>
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <select
                value={epoch1Id}
                aria-label="First epoch observation"
                onChange={(e) => {
                  setEpoch1Id(e.target.value);
                  runCompare(e.target.value, epoch2Id);
                }}
                className="max-w-full sm:max-w-[280px] bg-slate-900 border border-slate-700 text-xs font-mono rounded-lg px-3 py-2.5 text-cyan-300 focus:outline-none focus:border-cyan-500"
              >
                <option value="">Select Epoch 1</option>
                {observations.map((o) => (
                  <option key={o.product_id} value={observationKey(o)}>
                    {o.obs_id} ({o.band}) {o.screening_status === "REJECTED_SATURATED" ? "[SAT]" : ""}
                  </option>
                ))}
              </select>
              <span className="text-slate-500 font-bold font-mono">vs</span>
              <select
                value={epoch2Id}
                aria-label="Second epoch observation"
                onChange={(e) => {
                  setEpoch2Id(e.target.value);
                  runCompare(epoch1Id, e.target.value);
                }}
                className="max-w-full sm:max-w-[280px] bg-slate-900 border border-slate-700 text-xs font-mono rounded-lg px-3 py-2.5 text-purple-300 focus:outline-none focus:border-purple-500"
              >
                <option value="">Select Epoch 2</option>
                {observations.map((o) => (
                  <option key={o.product_id} value={observationKey(o)} disabled={observationKey(o) === epoch1Id || o.band !== observations.find(item => observationKey(item) === epoch1Id)?.band}>
                    {o.obs_id} ({o.band}) {o.screening_status === "REJECTED_SATURATED" ? "[SAT]" : ""}
                  </option>
                ))}
              </select>
            </div>
            {loading && (
              <span className="text-xs font-mono text-cyan-400 flex items-center space-x-1.5 animate-pulse">
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Reprojecting WCS & Computing Residuals...</span>
              </span>
            )}
          </div>

          <div className="flex items-center space-x-2">
            <div className="flex items-center space-x-1 bg-slate-900 p-1 rounded-lg border border-slate-800">
              {(["side", "swipe", "blink"] as const).map((m) => (
                <button
                  key={m}
                  aria-pressed={viewMode===m}
                  onClick={() => setViewMode(m)}
                  className={`px-3 py-1 rounded text-xs font-bold uppercase transition ${
                    viewMode === m ? "bg-cyan-500 text-slate-950 font-black shadow-sm" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {m === 'side' ? 'Side by side' : m === 'swipe' ? 'Swipe' : 'Blink'}
                </button>
              ))}
            </div>

            {result && (
              <button
                onClick={() => setIsDossierOpen(true)}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-mono bg-cyan-600/30 hover:bg-cyan-600/50 border border-cyan-500/60 text-cyan-200 font-bold transition shadow-sm"
              >
                <FileText className="w-3.5 h-3.5 text-cyan-400" />
                <span>Scientific Dossier</span>
              </button>
            )}
          </div>
        </div>

        {!loading && !result && !compareError && <div className="rounded-xl border border-slate-800 bg-slate-900/30 px-6 py-10 text-center"><h2 className="text-lg font-medium text-slate-200">Choose a compatible observation pair</h2><p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-slate-400">A scientific comparison needs two distinct epochs in the same band with usable celestial overlap. If the current target has insufficient data, select another predefined target above.</p></div>}

        {compareError && (
          <div className="p-4 rounded-lg bg-rose-950/40 border border-rose-800 text-xs text-rose-300 font-mono flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{compareError}</span>
          </div>
        )}

        {result && (
          <div className={`glass-panel p-4 text-xs space-y-2 ${result.comparison_validity.scientific_analysis_allowed ? "text-emerald-300" : "text-amber-300"}`}>
            <p className="font-bold">{result.comparison_validity.status}</p>
            <p>Minimum usable overlap: {(result.comparison_validity.min_overlap_fraction * 100).toFixed(1)}% of the reference grid.</p>
            {result.comparison_validity.failure_reasons.map((reason, index) => <p key={`${reason.code}-${index}`}>{reason.message}</p>)}
          </div>
        )}

        {result && <div className="grid gap-3 md:grid-cols-2">
          {Object.entries(result.data_quality).map(([epoch, metadata]) => <ProductQualitySummary key={epoch} label={epoch.replace("_", " ")} quality={metadata.quality} variance={metadata.variance} scienceValidPixelCount={metadata.science_valid_pixel_count} />)}
        </div>}

        {/* Section 3: Visual Comparator & Verdict Quadrant */}
        {result && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-8 glass-panel p-5 space-y-4">
              {viewMode === "side" && (
                <DifferenceViewer
                  scientificAnalysisAllowed={result.comparison_validity.scientific_analysis_allowed}
                  img1={result.epoch_1_image_base64}
                  img2={result.epoch_2_image_base64}
                  diffImg={result.difference_image_base64 || ""}
                  sigImg={result.significance_image_base64 || ""}
                  origImg1={result.epoch_1_original_image_base64}
                  origImg2={result.epoch_2_original_image_base64}
                  maskImg={result.overlap_mask_image_base64}
                />
              )}
              {viewMode === "swipe" && (
                <ImageComparisonSlider
                  img1={result.epoch_1_image_base64}
                  img2={result.epoch_2_image_base64}
                />
              )}
              {viewMode === "blink" && (
                <div className="relative aspect-video max-h-[420px] rounded-xl overflow-hidden bg-slate-950 border border-slate-800 flex items-center justify-center">
                  <Image unoptimized width={1000} height={1000}
                    src={blinkState ? result.epoch_2_image_base64 : result.epoch_1_image_base64}
                    alt="Blink Comparator"
                    className="w-full h-full object-contain pixelated"
                  />
                  <div className="absolute top-3 left-3 px-2.5 py-1 rounded bg-slate-950/90 text-xs font-mono font-bold border border-slate-700 flex items-center space-x-2">
                    <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                    <span>{result.comparison_validity.scientific_analysis_allowed ? (blinkState ? "FRAME: EPOCH 2 (WCS Reprojected)" : "FRAME: EPOCH 1 (Reference)") : `VISUAL ONLY: EPOCH ${blinkState ? 2 : 1} ORIGINAL`}</span>
                  </div>
                </div>
              )}
            </div>

            <div className="lg:col-span-4 glass-panel p-5 space-y-3 font-mono text-xs">
              <h4 className="text-xs font-bold uppercase text-slate-300 border-b border-slate-800 pb-2 flex items-center justify-between">
                <span>Comparison Assessment</span>
                {result.comparison_validity.scientific_analysis_allowed ? (
                  <span className="text-[10px] text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800/60 font-bold">
                    WCS REPROJECTED
                  </span>
                ) : (
                  <span className="text-[10px] text-amber-400 bg-amber-950/80 px-2 py-0.5 rounded border border-amber-800/60 font-bold">
                    VISUAL ONLY
                  </span>
                )}
              </h4>

              <div className="grid grid-cols-2 gap-2">
                <div className="p-3 rounded bg-slate-900 border border-slate-800">
                  <span className="text-slate-500 text-[10px] block font-bold">PEAK RESIDUAL</span>
                  <span className="text-xl font-black text-cyan-300">
                    {result.candidate_assessment?.peak_sig != null ? `${result.candidate_assessment.peak_sig.toFixed(2)} sigma` : "Unavailable"}
                  </span>
                </div>
                <div className="p-3 rounded bg-slate-900 border border-slate-800">
                  <span className="text-slate-500 text-[10px] block font-bold">TIME BASELINE</span>
                  <span className="text-xl font-black text-purple-300">{result.time_delta_days.toFixed(1)} d</span>
                </div>
              </div>

              {result.candidate_assessment && (
                <div className="p-3 rounded bg-slate-950 border border-slate-800 space-y-1.5 text-[11px]">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-500">Classification:</span>
                    <span className="font-bold text-cyan-300">
                      {result.candidate_assessment.category}
                    </span>
                  </div>
                  {result.registration_diagnostics?.overlap_fraction !== undefined && (
                    <div className="flex justify-between items-center text-[10px]">
                      <span className="text-slate-500">Celestial Overlap:</span>
                      <span className="text-slate-300 font-bold">
                        {(result.registration_diagnostics.overlap_fraction * 100).toFixed(1)}% ({result.difference_statistics?.valid_pixel_count} px)
                      </span>
                    </div>
                  )}
                  {result.registration_diagnostics?.angular_separation_arcsec != null && (
                    <div className="flex justify-between items-center text-[10px]">
                      <span className="text-slate-500">Pointing Offset:</span>
                      <span className="text-slate-300">
                        {result.registration_diagnostics.angular_separation_arcsec.toFixed(3)}&quot;
                      </span>
                    </div>
                  )}
                  {result.difference_statistics?.saturated_pixel_count ? (
                    <div className="flex justify-between items-center text-[10px] text-rose-300 font-bold">
                      <span>Masked Saturated:</span>
                      <span>{result.difference_statistics.saturated_pixel_count} px</span>
                    </div>
                  ) : null}
                  <div className="flex justify-between items-center text-[10px]">
                    <span className="text-slate-500">Detected Sources:</span>
                    <span className="text-slate-300">
                      {result.detected_sources?.length || result.difference_statistics?.detected_residual_sources_count || 0}
                    </span>
                  </div>
                </div>
              )}

              <p className="text-[11px] text-slate-300 font-sans leading-relaxed pt-1">
                {result.scientific_summary}
              </p>

              <button
                onClick={() => setIsDossierOpen(true)}
                className="w-full py-2 px-3 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold flex items-center justify-center space-x-2 transition mt-2"
              >
                <FileText className="w-4 h-4 text-cyan-400" />
                <span>Export Scientific Dossier & Dossier Report</span>
              </button>
            </div>
          </div>
        )}

        {/* Section 4: Residual Source Investigation Table */}
        {result?.motion_analysis && <SourceAssociationTable analysis={result.motion_analysis} />}

        {result?.comparison_validity.scientific_analysis_allowed && (
          <SourceInvestigationTable
            sources={result.detected_sources || []}
            isSaturatedTarget={isSaturated}
          />
        )}

        {/* Section 5: Scientific Evidence Dossier Modal */}
        <EvidenceDossierModal
          isOpen={isDossierOpen}
          onClose={() => setIsDossierOpen(false)}
          targetName={currentTarget}
          markdownReport={result?.evidence_report_markdown}
          dossierJson={result?.evidence_dossier}
        />
      </main>
      <Footer />
    </div>
  );
}
