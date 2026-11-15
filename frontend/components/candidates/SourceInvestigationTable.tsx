"use client";

import React, { useState } from "react";
import { DetectedSource } from "@/lib/types";
import { Target, ChevronDown, ChevronUp, ShieldAlert, Sparkles, AlertCircle } from "lucide-react";

interface Props {
  sources: DetectedSource[];
  isSaturatedTarget?: boolean;
}

export function SourceInvestigationTable({ sources, isSaturatedTarget = false }: Props) {
  const [expandedSourceId, setExpandedSourceId] = useState<number | null>(null);

  const getBadge = (category: string) => {
    switch (category) {
      case "POSSIBLE_MOVING_OBJECT_CANDIDATE":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
            MOVING OBJECT CANDIDATE
          </span>
        );
      case "VARIABLE_SOURCE":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-300 border border-sky-500/40">
            VARIABLE SOURCE
          </span>
        );
      case "STATIONARY_ASTRONOMICAL_SOURCE":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
            STATIONARY SOURCE
          </span>
        );
      case "DETECTOR_ARTIFACT":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40">
            DETECTOR ARTIFACT
          </span>
        );
      case "INSUFFICIENT_EVIDENCE":
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
            INSUFFICIENT EVIDENCE
          </span>
        );
    }
  };

  return (
    <div className="glass-panel p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2">
          <Target className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200">
            Astronomical Residual Source Investigation & Candidate Vetting
          </h3>
        </div>
        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="text-slate-400">Detections (≥ 5.0σ):</span>
          <span className="font-bold text-cyan-300 bg-cyan-950/80 px-2.5 py-0.5 rounded border border-cyan-800/60">
            {sources.length} sources
          </span>
        </div>
      </div>

      {isSaturatedTarget && (
        <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-800/60 text-xs text-rose-200 flex items-start space-x-2.5">
          <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <span className="font-bold">Detector Saturation Telemetry Active:</span>
            <p className="text-[11px] text-rose-300/90">
              Bright targets (e.g. Mira, Delta Cephei, Algol) saturate SPHEREx detectors, triggering SUR ramp-fit overflow flags.
              Residual features at masked boundaries are classified as instrumental detector artifacts and strictly barred from moving-object candidate status.
            </p>
          </div>
        </div>
      )}

      {sources.length === 0 ? (
        <div className="py-8 text-center text-xs text-slate-400 font-mono space-y-1">
          <Sparkles className="w-6 h-6 text-slate-500 mx-auto opacity-60 mb-2" />
          <p>No residual components reported above the configured threshold, or extraction was blocked.</p>
          <p className="text-[10px] text-slate-500">This does not establish the absence of sources or motion; consult the independent epoch assessment.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs text-slate-300">
            <thead>
              <tr className="border-b border-slate-800 text-[11px] text-slate-400 bg-slate-950/50">
                <th className="py-2.5 px-3">Source</th>
                <th className="py-2.5 px-3">Celestial (RA, Dec)</th>
                <th className="py-2.5 px-3">Pixel (x, y)</th>
                <th className="py-2.5 px-3">Significance</th>
                <th className="py-2.5 px-3">Residual Flux</th>
                <th className="py-2.5 px-3">Astrometric Error (σ_ast)</th>
                <th className="py-2.5 px-3">Target Sep.</th>
                <th className="py-2.5 px-3">Evidence Classification</th>
                <th className="py-2.5 px-3 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {sources.map((src) => {
                const isExpanded = expandedSourceId === src.source_id;

                return (
                  <React.Fragment key={src.source_id}>
                    <tr className="hover:bg-slate-900/40 transition">
                      <td className="py-2.5 px-3 font-bold text-slate-200">
                        SRC-{src.source_id.toString().padStart(2, "0")}
                        <span className={`ml-2 text-[9px] uppercase px-1 py-0.5 rounded ${
                          src.nature === "positive_excess" ? "text-cyan-400 bg-cyan-950" : "text-amber-400 bg-amber-950"
                        }`}>
                          {src.nature === "positive_excess" ? "+ Excess" : "- Deficit"}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-300">
                        {src.ra_deg !== undefined && src.ra_deg !== null && src.dec_deg !== undefined && src.dec_deg !== null ? (
                          <span>{src.ra_deg.toFixed(5)}°, {src.dec_deg.toFixed(5)}°</span>
                        ) : (
                          <span className="text-slate-500">N/A</span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">
                        [{src.centroid_xy[0].toFixed(1)}, {src.centroid_xy[1].toFixed(1)}]
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="font-bold text-cyan-300">{src.peak_significance.toFixed(2)}σ</span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-300">
                        {src.flux.toFixed(3)} ± {src.flux_err.toFixed(3)}
                      </td>
                      <td className="py-2.5 px-3 text-slate-300">
                        ±{src.astrometric_uncertainty_arcsec.toFixed(3)}&quot;
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">
                        {src.angular_separation_from_target_arcsec !== undefined && src.angular_separation_from_target_arcsec !== null ? (
                          `${src.angular_separation_from_target_arcsec.toFixed(2)}"`
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="py-2.5 px-3">
                        {getBadge(src.classification)}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <button
                          onClick={() => setExpandedSourceId(isExpanded ? null : src.source_id)}
                          className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
                          title="Toggle classification rationale"
                        >
                          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="bg-slate-950/70 border-b border-slate-800 text-[11px]">
                        <td colSpan={9} className="p-3.5 space-y-2">
                          <div className="flex items-start space-x-2 text-slate-300">
                            <AlertCircle className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                            <div>
                              <strong className="text-slate-200 block mb-0.5">Scientific Vetting Rationale:</strong>
                              <p className="text-slate-400 font-sans leading-relaxed">{src.classification_rationale}</p>
                            </div>
                          </div>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-1 font-mono text-[10px] text-slate-400 border-t border-slate-800/60">
                            <div>Pixel Footprint: <span className="text-slate-200">{src.pixel_count} pixels</span></div>
                            <div>Epoch 1 Flux: <span className="text-slate-200">{src.epoch_1_flux !== null && src.epoch_1_flux !== undefined ? src.epoch_1_flux.toFixed(3) : "N/A"}</span></div>
                            <div>Epoch 2 Flux: <span className="text-slate-200">{src.epoch_2_flux !== null && src.epoch_2_flux !== undefined ? src.epoch_2_flux.toFixed(3) : "N/A"}</span></div>
                            <div>Centroid Uncertainty: <span className="text-cyan-300">FWHM / (2 × SNR)</span></div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

