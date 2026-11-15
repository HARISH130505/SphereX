"use client";

import { ProductQualitySummary } from "@/components/images/ProductQualitySummary";
import React, { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { WorkspaceHeader, WorkspaceLink, WorkspaceMetric } from '@/components/layout/WorkspaceHeader';
import { FitsImageViewer } from "@/components/images/FitsImageViewer";
import { ImageControls } from "@/components/images/ImageControls";
import { ObservationPanel } from "@/components/sky/ObservationPanel";
import { fetchObservations, fetchObservationCutout, fetchTargets, fetchCoverageReport } from "@/lib/api";
import { ObservationRecord, TargetInfo, CutoutRenderResponse, CoverageReport } from "@/lib/types";
import { observationKey } from "@/lib/observations";
import { selectTarget, predefinedTarget } from '@/lib/selected-target';
import { Compass, AlertTriangle, CheckCircle2, Info, RefreshCw } from "lucide-react";

const TARGET_NAMES = ["M101", "M51", "M33", "NGC 253", "Mira", "Delta Cephei", "Algol"];

function SkyExplorerContent() {
  const searchParams = useSearchParams();
  const requestedTarget = searchParams.get("target");
  const linkedTarget = predefinedTarget(requestedTarget);
  const [targets, setTargets] = useState<TargetInfo[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<string>(linkedTarget);
  const [observations, setObservations] = useState<ObservationRecord[]>([]);
  const [selectedObs, setSelectedObs] = useState<ObservationRecord | null>(null);
  const [cutoutData, setCutoutData] = useState<CutoutRenderResponse | null>(null);
  const [cutoutError, setCutoutError] = useState<string | null>(null);
  const [stretch, setStretch] = useState<string>("asinh");
  const [colormap, setColormap] = useState<string>("plasma");
  const [loading, setLoading] = useState<boolean>(false);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [catalogRevision, setCatalogRevision] = useState(0);
  const [coverage, setCoverage] = useState<CoverageReport | null>(null);
  const currentTargetMeta = targets.find((t) => t.name === selectedTarget);

  useEffect(() => {
    fetchTargets().then((res) => {
      setTargets(res);
      if(!requestedTarget) {
        const saved=sessionStorage.getItem('spherex-selected-target');
        if(saved) setSelectedTarget(predefinedTarget(saved));
      }
    }).catch(console.error);
  }, [requestedTarget]);

  useEffect(() => {
    const controller = new AbortController();
    fetchObservations(selectedTarget, undefined, controller.signal)
      .then((obs) => {
        if(controller.signal.aborted) return;
        setObservations(obs);
        setSelectedObs(null); setCutoutData(null); setCutoutError(null);
        setLoading(obs.length > 0); setRefreshing(false);
        if (obs.length > 0) {
          // Select first observation with valid FITS product
          const firstPlayable = obs.find((o) => o.screening_status !== "FAILED_DOWNLOAD") || obs[0];
          setSelectedObs(firstPlayable);
        }
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        console.error(err);
        setObservations([]);
        setLoading(false); setRefreshing(false);
      });
    return () => controller.abort();
  }, [selectedTarget, catalogRevision]);

  useEffect(() => {
    if (selectedTarget !== "Sedna" && selectedTarget !== "Planet 9 Candidate Field") {
      return;
    }
    fetchCoverageReport(selectedTarget).then(setCoverage).catch(() => setCoverage(null));
  }, [selectedTarget]);

  useEffect(() => {
    if (!selectedObs) return;
    const controller = new AbortController();

    fetchObservationCutout(observationKey(selectedObs), stretch, colormap, controller.signal)
      .then((data) => {
        if(controller.signal.aborted) return;
        setCutoutData(data);
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        console.error("Cutout fetch error:", err);
        setCutoutError(err instanceof Error ? err.message : "Failed to load genuine FITS product from archive.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [selectedObs, stretch, colormap]);

  const isUnsurveyedTarget = selectedTarget === "Sedna" || selectedTarget === "Planet 9 Candidate Field";

  const handleManualRefresh = () => {
    setRefreshing(true);
    setCatalogRevision(value=>value+1);
  };

  const chooseTarget = (name: string) => {
    setCutoutData(null);
    setCutoutError(null);
    setSelectedObs(null);
    setObservations([]);
    setCoverage(null);
    setSelectedTarget(name);
    selectTarget(name);
    window.history.replaceState(null, "", `/sky-explorer?target=${encodeURIComponent(name)}`);
  };

  return (
    <div className="flex flex-col min-h-screen">
      <Navbar />
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 lg:p-8 space-y-6">
        <WorkspaceHeader section="Observation workspace" title="A closer look at the sky." description="Select a target, open a genuine observation, and inspect the pixels behind the picture." action={<WorkspaceLink href="/epoch-comparison">Compare observations</WorkspaceLink>} />
        {/* Target Selector Bar */}
        <section className="glass-panel p-5 space-y-4">
          <div className="flex items-center space-x-2">
            <Compass className="w-4 h-4 text-cyan-400" />
            <span className="text-xs font-medium text-slate-300">Choose an observation field</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {(targets.length ? targets.map((target) => target.name) : TARGET_NAMES).map((name) => (
              <button
                key={name}
                aria-pressed={selectedTarget===name}
                onClick={() => chooseTarget(name)}
                className={`px-4 py-3 rounded-xl text-sm font-medium border text-left transition ${
                  selectedTarget === name
                    ? "bg-cyan-500/20 border-cyan-400 text-cyan-200 shadow-sm shadow-cyan-500/20"
                    : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200"
                }`}
              >
                {name}
                <span className="mt-1 block text-[8px] font-normal tracking-wide opacity-70">{targets.find(t => t.name === name)?.exploration_status}</span>
              </button>
            ))}
          </div>
        </section>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <WorkspaceMetric label="Selected target" value={selectedTarget} detail={currentTargetMeta?.category} />
          <WorkspaceMetric label="Cataloged observations" value={observations.length} detail="Select a product to view its quality" />
          <WorkspaceMetric label="Celestial center" value={currentTargetMeta ? `${currentTargetMeta.ra.toFixed(3)}°, ${currentTargetMeta.dec.toFixed(3)}°` : '—'} detail="Right ascension / declination · ICRS" />
          <WorkspaceMetric label="Selected detector" value={selectedObs?.band || '—'} detail={selectedObs ? `Observed MJD ${selectedObs.obs_time_mjd.toFixed(5)}` : 'No observation selected'} />
        </div>
        {observations.length === 0 && !isUnsurveyedTarget && <p className="text-amber-300">No products are currently cataloged for this target.</p>}

        {/* Dynamic Status Banner based on Target Science State */}
        {isUnsurveyedTarget ? (
          <div className="glass-panel border-cyan-500/30 bg-cyan-950/20 p-4 rounded-xl flex items-start justify-between gap-4">
            <div className="flex items-start space-x-3.5">
              <Info className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
              <div>
                <h4 className="text-sm font-bold text-cyan-200">Target Field Survey Status — {selectedTarget}</h4>
                <p className="text-xs text-cyan-100/80 mt-1 max-w-3xl leading-relaxed">
                  {currentTargetMeta?.description || "High-priority solar system science target."} {coverage?.detail || "Coverage search status is unavailable."}
                </p>
                <div className="flex items-center space-x-4 mt-2 text-[11px] font-mono text-cyan-300">
                  <span>Coordinates: RA {currentTargetMeta?.ra.toFixed(3)}°, Dec {currentTargetMeta?.dec.toFixed(3)}°</span>
                  <span>Coverage: {observations.length} catalog records</span>
                  <span className="text-emerald-400">Integrity: No Synthetic Fabrication</span>
                </div>
                {coverage && <div className="mt-2 text-[10px] font-mono text-cyan-200">Status: {coverage.status}; mode: {coverage.search_mode || "not specified"}; releases: {coverage.searched_releases.join(", ")}; complete: {coverage.search_complete ? "yes" : "no"}.</div>}
                {selectedTarget === "Sedna" && <button onClick={() => fetchCoverageReport("Sedna", true).then(setCoverage)} className="mt-2 px-2 py-1 rounded border border-cyan-500 text-[10px]">Run JPL Horizons epoch query</button>}
              </div>
            </div>
            <button
              onClick={handleManualRefresh}
              disabled={refreshing}
              className="shrink-0 flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400 text-xs font-medium text-cyan-200 transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
              <span>Refresh Status</span>
            </button>
          </div>
        ) : currentTargetMeta?.saturation_risk === "CRITICAL_SATURATED" ? (
          <div className="glass-panel border-rose-500/30 bg-rose-950/20 p-4 rounded-xl flex items-start space-x-3.5">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-bold text-rose-300">
                Detector Saturation Alert — {currentTargetMeta.name} (Authentic FITS Pixel Data)
              </h4>
              <p className="text-xs text-rose-200/80 mt-1">
                Catalog screening identifies this target as affected by detector saturation. Inspect this product&apos;s actual flag states and variance below; nonfinite pixels alone do not identify the detector failure.
              </p>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-4 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
            <div className="flex items-center space-x-2.5">
              <CheckCircle2 className="w-4 h-4 text-cyan-400" />
              <span>{selectedTarget}: Inspect each product&apos;s detector flags and variance before interpreting its photometry.</span>
            </div>
            <span className="text-[10px] text-cyan-200 bg-cyan-400/5 px-2 py-1 rounded border border-cyan-400/20">
              {cutoutData?.fits_valid ? cutoutData.screening_status === 'PASSED_CLEAN' ? 'PASSED_CLEAN' : 'Validated — inspect quality' : 'Observation not yet validated'}
            </span>
          </div>
        )}

        {/* Main Grid: FITS Viewer + Observations */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7 glass-panel p-5 space-y-4">
            <div className="flex items-center justify-between gap-3 border-b border-slate-800 pb-4"><div><h2 className="text-sm font-medium text-slate-200">Observation canvas</h2><p className="mt-1 text-[11px] text-slate-500">{loading ? 'Loading genuine FITS data…' : 'Adjust the display without changing the science pixels.'}</p></div><span className="text-[10px] text-cyan-300">FITS / WCS</span></div>
            <FitsImageViewer
              pngBase64={cutoutData?.png_base64}
              loading={loading}
              showOverlays={true}
              centerVal={cutoutData ? cutoutData.center_val : selectedObs?.center_image_val}
              imageShape={cutoutData?.image_shape}
              nanCount={cutoutData?.nan_count}
              validPct={cutoutData?.valid_pct}
              minVal={cutoutData?.min_val}
              maxVal={cutoutData?.max_val}
              medianVal={cutoutData?.median_val}
              wcsInfo={cutoutData?.wcs_info}
              sourceFile={cutoutData?.source_file}
              errorMessage={cutoutError}
              isUnsurveyed={isUnsurveyedTarget}
              targetName={selectedTarget}
              onRefresh={handleManualRefresh}
            />

            {cutoutData?.quality_summary && cutoutData?.variance_summary && <ProductQualitySummary quality={cutoutData.quality_summary} variance={cutoutData.variance_summary} scienceValidPixelCount={cutoutData.science_valid_pixel_count} observationQuality={cutoutData.observation_quality} />}

            {!isUnsurveyedTarget && (
              <ImageControls
                stretch={stretch}
                setStretch={value=> {setCutoutData(null); setCutoutError(null); setLoading(!!selectedObs); setStretch(value);}}
                colormap={colormap}
                setColormap={value=> {setCutoutData(null); setCutoutError(null); setLoading(!!selectedObs); setColormap(value);}}
              />
            )}
          </div>

          <div className="lg:col-span-5 glass-panel p-5 space-y-4 self-start lg:sticky lg:top-24">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold tracking-wide uppercase text-slate-300">
                Observations for {selectedTarget} ({observations.length})
              </h3>
              {currentTargetMeta && (
                <span className="text-[11px] font-mono text-slate-400">
                  {currentTargetMeta.category}
                </span>
              )}
            </div>

            <ObservationPanel
              observations={observations}
              selectedObs={selectedObs}
              onSelectObs={obs=> {setCutoutData(null); setCutoutError(null); setLoading(true); setSelectedObs(obs);}}
            />
            {selectedObs && <div className="space-y-3 rounded-xl border border-slate-800 bg-slate-950/50 p-4"><p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">Selected product provenance</p><p className="break-all font-mono text-[10px] leading-5 text-slate-400">{selectedObs.obs_publisher_did || selectedObs.archive_product_id || selectedObs.product_id}</p><p className="text-xs leading-6 text-slate-400">{selectedObs.rejection_reason}</p><WorkspaceLink href="/candidate-investigator">Review quality screening</WorkspaceLink></div>}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}

export default function SkyExplorerPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-950" />}>
      <SkyExplorerContent />
    </Suspense>
  );
}
