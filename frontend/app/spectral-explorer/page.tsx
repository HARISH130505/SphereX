"use client";
import { useState, useEffect } from "react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { WorkspaceHeader, WorkspaceLink, WorkspaceMetric } from "@/components/layout/WorkspaceHeader";
import { SpectralPlot } from "@/components/charts/SpectralPlot";
import { fetchSpectralSummary, fetchTargets } from "@/lib/api";
import { SpectralSummary, TargetInfo } from "@/lib/types";
import { LoaderCircle, Waves, Info, ArrowRight } from "lucide-react";
import { useSelectedTarget, selectTarget } from "@/lib/selected-target";

export default function SpectralExplorerPage() {
  const [summary, setSummary] = useState<SpectralSummary | null>(null);
  const [targets, setTargets] = useState<TargetInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const target = useSelectedTarget();
  useEffect(() => { fetchTargets().then(setTargets).catch(() => setError('Could not load the target catalog.')); }, []);
  useEffect(() => {
    let current = true;
    if (target === 'M101') fetchSpectralSummary().then(data => { if (current) {setSummary(data); setError(null);} }).catch(error => { if (current) setError(error.message); });
    return () => { current = false; };
  }, [target, revision]);
  const available = target === 'M101' && summary;
  const points = available ? summary.points : [];
  const wavelengths=points.map(p=>p.wavelength_um).filter(Number.isFinite);
  const wavelengthRange=wavelengths.length ? `${Math.min(...wavelengths).toFixed(2)}–${Math.max(...wavelengths).toFixed(2)} μm` : '—';
  return <div className="flex min-h-screen flex-col"><Navbar />
    <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 p-4 lg:p-8">
      <WorkspaceHeader section="Spectral workspace" title="Read the light." description="Explore measured flux density across wavelengths. Compare detector bands and inspect the uncertainty behind each cataloged point." action={<WorkspaceLink href="/research-assistant">Ask about spectroscopy</WorkspaceLink>} />
      <section className="glass-panel flex flex-wrap items-center justify-between gap-4 p-5"><div className="flex items-center gap-3"><Waves className="h-5 w-5 text-amber-300" /><div><label htmlFor="spectral-target" className="text-sm font-medium text-slate-200">Spectrophotometry context</label><p className="mt-1 text-xs text-slate-500">Extracted spectral measurements are available for M101 in this catalog.</p></div></div><select id="spectral-target" value={target} onChange={event=>selectTarget(event.target.value)} className="rounded-xl border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-400">{targets.length ? targets.map(t=><option key={t.id} value={t.name}>{t.name}</option>) : <option>{target}</option>}</select></section>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4"><WorkspaceMetric label="Selected source" value={target} detail="Cataloged spectrophotometry" /><WorkspaceMetric label="Measured points" value={available ? points.length : '—'} detail="Samples are not necessarily distinct channels" /><WorkspaceMetric label="Wavelength range" value={wavelengthRange} detail="From available catalog measurements" /><WorkspaceMetric label="Median catalog SNR" value={available ? summary.median_snr.toFixed(1) : '—'} detail="Signal-to-noise across supplied points" /></div>
      {error && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-500/20 bg-rose-500/5 p-4 text-sm text-rose-200">{error}{target==='M101' && <button onClick={()=>{setError(null);setRevision(value=>value+1);}} className="rounded-lg border border-rose-400/30 px-3 py-1.5 text-xs">Retry spectra</button>}</div>}
      {available ? <section className="glass-panel space-y-6 p-5 sm:p-7"><div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-800 pb-5"><div><h2 className="text-lg font-medium text-slate-100">{target} · spectral energy distribution</h2><p className="mt-2 text-xs text-slate-500">Select a detector band. Hover or focus a point to inspect its original measurement.</p></div><span className="rounded-full border border-amber-400/20 bg-amber-400/5 px-3 py-1 text-[10px] text-amber-200">Catalog measurements</span></div><SpectralPlot summary={summary} /></section> : target==='M101' ? <div role="status" className="glass-panel flex items-center justify-center gap-3 p-16 text-sm text-slate-400">{!error && <LoaderCircle className="h-5 w-5 animate-spin text-cyan-400" />}{error ? 'Spectral measurements could not be loaded.' : 'Loading cataloged spectrophotometry…'}</div> : <section className="glass-panel px-6 py-14 text-center"><Waves className="mx-auto mb-5 h-9 w-9 text-slate-600" /><h2 className="text-xl font-medium text-slate-200">No extracted spectrum for {target}</h2><p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-slate-400">The selected field may have genuine FITS images, but this catalog does not include extracted source spectral measurements for it. Detector band labels alone do not form a measured spectrum.</p><button onClick={()=>selectTarget('M101')} className="mt-6 inline-flex items-center gap-2 rounded-xl bg-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 hover:bg-cyan-300">Explore M101 spectra <ArrowRight className="h-4 w-4" /></button></section>}
      <div className="grid gap-4 md:grid-cols-3">{[
        ['Flux density','The vertical axis shows source flux density in microjanskys (μJy). The plotted values come from the supplied photometry catalog.'],
        ['Measurement uncertainty','Vertical error bars show the cataloged flux uncertainty. They are part of the measurement, not a separate variability detection.'],
        ['Interpretation limits','These points may come from different epochs and detector bands. A spectral shape alone does not confirm a line, variability, or a new object.'],
      ].map(([title,text])=><div key={title} className="rounded-xl border border-slate-800 bg-slate-900/20 p-5"><h3 className="flex items-center gap-2 text-xs font-medium text-slate-200"><Info className="h-3.5 w-3.5 text-cyan-400" />{title}</h3><p className="mt-3 text-xs leading-6 text-slate-500">{text}</p></div>)}</div>
    </main><Footer /></div>;
}
