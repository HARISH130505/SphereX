"use client";
import { useState } from "react";
import { SpectralSummary, SpectrumDataPoint } from "@/lib/types";

const colors: Record<number,string> = {1:'#38bdf8',2:'#818cf8',3:'#c084fc',4:'#f472b6',5:'#fb923c',6:'#facc15'};

export function SpectralPlot({ summary }: { summary: SpectralSummary }) {
  const [selectedBand,setSelectedBand]=useState('ALL');
  const [hovered,setHovered]=useState<SpectrumDataPoint|null>(null);
  const valid=summary.points.filter(p=>Number.isFinite(p.wavelength_um) && Number.isFinite(p.flux_ujy) && Number.isFinite(p.flux_err_ujy) && p.flux_err_ujy>=0);
  const filtered=valid.filter(p=>selectedBand==='ALL' || p.band_name===selectedBand);
  const range=(values:number[])=> {
    if(!values.length) return [0,1];
    const low=Math.min(...values), high=Math.max(...values), pad=(high-low || Math.abs(high)*.1 || 1)*.08;
    return [low-pad,high+pad];
  };
  const [xmin,xmax]=range(valid.map(p=>p.wavelength_um));
  const [ymin,ymax]=range(filtered.flatMap(p=>[p.flux_ujy-p.flux_err_ujy,p.flux_ujy+p.flux_err_ujy]));
  const x=(v:number)=>70+(v-xmin)/(xmax-xmin)*710;
  const y=(v:number)=>290-(v-ymin)/(ymax-ymin)*260;
  const display=(v:number)=>Math.abs(v)>=1000 ? `${(v/1000).toFixed(1)}k` : v.toFixed(1);
  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-4"><p className="text-xs text-slate-500">{filtered.length} measurements · uncertainty bars shown</p><div className="flex flex-wrap gap-1.5">{['ALL','SPHEREx-D1','SPHEREx-D2','SPHEREx-D3','SPHEREx-D4','SPHEREx-D5','SPHEREx-D6'].map(b=><button key={b} onClick={()=> {setSelectedBand(b);setHovered(null);}} aria-pressed={selectedBand===b} className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-[11px] transition ${selectedBand===b?'border-cyan-400/40 bg-cyan-400/10 text-slate-100':'border-slate-800 bg-slate-900/50 text-slate-400 hover:border-slate-600'}`}>{b!=='ALL' && <span className="h-1.5 w-1.5 rounded-full" style={{backgroundColor:colors[Number(b.slice(-1))]}} />}{b==='ALL'?'All bands':b.replace('SPHEREx-','')}</button>)}</div></div>
    <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-3 sm:p-5"><div className="mb-3 text-[10px] uppercase tracking-wider text-slate-500">Flux density · μJy</div>{filtered.length ? <div className="overflow-x-auto"><svg viewBox="0 0 820 340" className="w-full min-w-[520px]" aria-label="Spectral scatter plot with cataloged flux uncertainty bars" role="group"><title>{summary.target} flux density by wavelength</title><desc>Each point is a cataloged measurement. Focus a point to show wavelength, flux, uncertainty and observation identity below.</desc>{Array.from({length:6},(_,i)=> {
      const value=ymin+(ymax-ymin)*i/5;
      return <g key={`y${i}`}><line x1={70} x2={780} y1={y(value)} y2={y(value)} stroke="#1e293b" strokeDasharray="3 5" /><text x={58} y={y(value)+4} fill="#64748b" fontSize={10} textAnchor="end">{display(value)}</text></g>;
    })}{Array.from({length:7},(_,i)=> {
      const value=xmin+(xmax-xmin)*i/6;
      return <g key={`x${i}`}><line x1={x(value)} x2={x(value)} y1={30} y2={290} stroke="#1e293b" strokeDasharray="3 5" /><text x={x(value)} y={313} fill="#64748b" fontSize={10} textAnchor="middle">{value.toFixed(2)}</text></g>;
    })}{filtered.map((pt,i)=><g key={`${pt.obs_publisher_did}-${i}`}><line x1={x(pt.wavelength_um)} x2={x(pt.wavelength_um)} y1={y(pt.flux_ujy+pt.flux_err_ujy)} y2={y(pt.flux_ujy-pt.flux_err_ujy)} stroke={colors[pt.det_id]||'#38bdf8'} opacity={hovered===pt?1:.35} /><circle cx={x(pt.wavelength_um)} cy={y(pt.flux_ujy)} r={hovered===pt?5:3} fill={colors[pt.det_id]||'#38bdf8'} stroke={hovered===pt?'#fff':'#030712'} strokeWidth={1} tabIndex={0} role="button" aria-label={`${pt.band_name}, ${pt.wavelength_um} micrometers, ${pt.flux_ujy} plus or minus ${pt.flux_err_ujy} microjanskys. Show measurement details.`} onMouseEnter={()=>setHovered(pt)} onFocus={()=>setHovered(pt)} onClick={()=>setHovered(pt)} onKeyDown={event=> {if(event.key==='Enter'||event.key===' ') {event.preventDefault();setHovered(pt);}}} className="cursor-crosshair outline-none" /></g>)}<text x={425} y={337} fill="#94a3b8" fontSize={11} textAnchor="middle">Wavelength · μm</text></svg></div> : <p className="py-24 text-center text-sm text-slate-500">No valid spectral measurements in this band.</p>}</div>
    <div className="min-h-28 rounded-xl border border-slate-800 bg-slate-900/40 p-4" aria-live="polite">{hovered ? <><div className="grid grid-cols-2 gap-4 sm:grid-cols-4">{[['Detector',hovered.band_name],['Wavelength',`${hovered.wavelength_um.toFixed(4)} μm`],['Flux density',`${hovered.flux_ujy.toFixed(2)} ± ${hovered.flux_err_ujy.toFixed(2)} μJy`],['Catalog SNR',hovered.snr.toFixed(1)]].map(([label,value])=><div key={label}><p className="text-[9px] uppercase tracking-wide text-slate-500">{label}</p><p className="mt-2 text-xs text-cyan-100">{value}</p></div>)}</div><p className="mt-4 break-all border-t border-slate-800 pt-3 font-mono text-[10px] leading-5 text-slate-500">MJD {hovered.mjd.toFixed(5)} · {hovered.obs_publisher_did || 'Publisher identifier not supplied'}</p></> : <div className="py-4 text-center"><p className="text-xs text-slate-400">Every point has a story.</p><p className="mt-2 text-[11px] text-slate-500">Hover, tap, or keyboard-focus a measurement to inspect its catalog values.</p></div>}</div>
    {valid.length!==summary.points.length && <p className="text-xs text-amber-300">{summary.points.length-valid.length} nonfinite or invalid-uncertainty catalog points cannot be plotted.</p>}
  </div>;
}
