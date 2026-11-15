"use client";
import { useState, useEffect } from "react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { WorkspaceHeader, WorkspaceLink, WorkspaceMetric } from "@/components/layout/WorkspaceHeader";
import { CandidateTable } from "@/components/candidates/CandidateTable";
import { CandidateDetails } from "@/components/candidates/CandidateDetails";
import { fetchObservations, fetchTargets, evaluateCustomThresholds, QualityEvaluationResponse } from "@/lib/api";
import { ObservationRecord, TargetInfo } from "@/lib/types";
import { useSelectedTarget, selectTarget } from "@/lib/selected-target";
import { ShieldCheck, SlidersHorizontal, LoaderCircle } from "lucide-react";

export default function CandidateInvestigatorPage() {
  const [observations, setObservations] = useState<ObservationRecord[]>([]);
  const [selectedObs, setSelectedObs] = useState<ObservationRecord | null>(null);
  const [filter, setFilter] = useState("ALL");
  const [simApertureFatalMax, setSimApertureFatalMax] = useState(0);
  const [simEvaluation, setSimEvaluation] = useState<QualityEvaluationResponse | null>(null);
  const [targets, setTargets] = useState<TargetInfo[]>([]);
  const [loadedTarget, setLoadedTarget] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [evaluationError, setEvaluationError] = useState<string | null>(null);
  const target = useSelectedTarget();
  const loading = loadedTarget !== target;
  useEffect(() => { fetchTargets().then(setTargets).catch(() => setError("Could not load the target catalog.")); }, []);
  useEffect(() => {
    const controller = new AbortController();
    fetchObservations(target, undefined, controller.signal).then(obs => {
      if (controller.signal.aborted) return;
      setObservations(obs); setSelectedObs(obs[0] || null); setSimEvaluation(null); setError(null); setLoadedTarget(target);
    }).catch(error => { if (!controller.signal.aborted) { setError(error.message); setObservations([]); setSelectedObs(null); setLoadedTarget(target); } });
    return () => controller.abort();
  }, [target]);
  useEffect(() => {
    if (!selectedObs || selectedObs.target !== target) return;
    let current = true;
    evaluateCustomThresholds({ center_finite: selectedObs.center_pixel_finite, center_flags_raw: selectedObs.center_flags_raw,
      aperture_fatal_count: selectedObs.aperture_fatal_count, aperture_total_pixels: selectedObs.aperture_total_pixels,
      bg_usable_pixels: selectedObs.bg_usable_pixels, variance_available: selectedObs.variance_available,
      target_inside: selectedObs.target_inside_cutout, aperture_fatal_tolerance: simApertureFatalMax,
    }).then(result => { if (current) { setSimEvaluation(result); setEvaluationError(null); } }).catch(error => { if (current) { setEvaluationError(error.message); setSimEvaluation(null); } });
    return () => { current = false; };
  }, [selectedObs, simApertureFatalMax, target]);

  return <div className="flex min-h-screen flex-col"><Navbar />
    <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 p-4 lg:p-8">
      <WorkspaceHeader section="Quality workspace" title="Look beyond the signal." description="Inspect observation quality, understand detector flags, and test screening tolerances before interpreting a candidate." action={<WorkspaceLink href="/epoch-comparison">Open comparison evidence</WorkspaceLink>} />
      <div className="glass-panel flex flex-wrap items-center justify-between gap-4 p-5"><div className="flex items-center gap-3"><ShieldCheck className="h-5 w-5 text-cyan-400" /><div><label htmlFor="candidate-target" className="text-sm font-medium text-slate-200">Observation screening</label><p className="mt-1 text-xs text-slate-500">Quality records describe the instrument; they do not establish a source detection.</p></div></div><select id="candidate-target" value={target} onChange={event => { selectTarget(event.target.value); setFilter('ALL'); setSimApertureFatalMax(0); }} className="rounded-xl border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-400">{targets.length ? targets.map(t => <option key={t.id} value={t.name}>{t.name}</option>) : <option>{target}</option>}</select></div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4"><WorkspaceMetric label="Target" value={target} detail="Predefined observation field" /><WorkspaceMetric label="Screening records" value={loading ? '—' : observations.length} detail="Individual cataloged products" /><WorkspaceMetric label="Catalog clean status" value={loading ? '—' : observations.filter(o => o.screening_status === 'PASSED_CLEAN').length} detail="Products marked PASSED_CLEAN" /><WorkspaceMetric label="FITS validated" value={loading ? '—' : observations.filter(o => o.fits_valid).length} detail="Validation does not guarantee photometric suitability" /></div>
      {error && <p role="alert" className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4 text-sm text-rose-200">{error}</p>}
      {loading ? <div role="status" className="glass-panel flex items-center justify-center gap-3 p-12 text-sm text-slate-400"><LoaderCircle className="h-5 w-5 animate-spin text-cyan-400" /> Loading {target} screening records…</div> : <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <section className="glass-panel space-y-4 p-5 lg:col-span-8"><div className="border-b border-slate-800 pb-4"><h2 className="text-sm font-medium text-slate-200">Observation screening catalog</h2><p className="mt-1 text-xs text-slate-500">Select a row to inspect its quality record.</p></div><CandidateTable observations={observations} selectedObs={selectedObs} onSelect={obs => { setSelectedObs(obs); setSimEvaluation(null); setSimApertureFatalMax(0); }} filter={filter} setFilter={setFilter} /></section>
        <aside className="glass-panel space-y-5 self-start p-5 lg:col-span-4"><h2 className="border-b border-slate-800 pb-4 text-sm font-medium text-slate-200">Product diagnostics</h2><CandidateDetails obs={selectedObs} /><div className="border-t border-slate-800 pt-5"><h3 className="flex items-center gap-2 text-sm text-slate-200"><SlidersHorizontal className="h-4 w-4 text-cyan-400" /> Screening sandbox</h3><p className="mt-2 text-xs leading-6 text-slate-500">Explore how a tolerance changes screening. This does not modify FITS data, saved quality records, or scientific safeguards.</p></div><label className="block text-xs text-slate-300">Allowed flagged aperture pixels <strong className="float-right rounded bg-cyan-400/10 px-2 text-cyan-200">{simApertureFatalMax}</strong><input className="mt-4 w-full accent-cyan-400" type="range" min={0} max={selectedObs?.aperture_total_pixels ?? 29} value={simApertureFatalMax} disabled={!selectedObs} onChange={event => { setSimApertureFatalMax(Number(event.target.value)); setSimEvaluation(null); }} /></label>{evaluationError && <p role="alert" className="text-xs text-rose-300">{evaluationError}</p>}{simEvaluation && <div className={`rounded-xl border p-4 ${simEvaluation.usable ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-200' : 'border-amber-500/30 bg-amber-500/5 text-amber-200'}`}><p className="text-[9px] uppercase tracking-wider opacity-60">Tolerance preview · not saved</p><p className="mt-2 text-sm font-medium">{simEvaluation.status}</p><p className="mt-2 text-xs leading-6 opacity-80">{simEvaluation.reason}</p></div>}</aside>
      </div>}
    </main><Footer /></div>;
}
