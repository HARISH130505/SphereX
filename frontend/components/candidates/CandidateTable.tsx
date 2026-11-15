"use client";

import React from "react";
import { ObservationRecord } from "@/lib/types";

interface Props {
  observations: ObservationRecord[];
  selectedObs: ObservationRecord | null;
  onSelect: (obs: ObservationRecord) => void;
  filter: string;
  setFilter: (f: string) => void;
}

export function CandidateTable({ observations, selectedObs, onSelect, filter, setFilter }: Props) {
  const filtered = observations.filter((o) => filter === "ALL" || o.screening_status === filter);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {["ALL", ...new Set(observations.map(o=>o.screening_status))].map((f) => (
          <button
            key={f}
            aria-pressed={filter===f}
            onClick={() => setFilter(f)}
            className={`px-2.5 py-1 rounded text-[11px] font-mono font-bold transition ${
              filter === f ? "bg-cyan-500 text-slate-950" : "bg-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            {f.replaceAll("_", " ")} <span className="ml-1 opacity-50">{f==='ALL' ? observations.length : observations.filter(o=>o.screening_status===f).length}</span>
          </button>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <caption className="sr-only">Observation quality screening records. Select a product for diagnostics.</caption>
          <thead className="bg-slate-900/80 text-slate-400 border-b border-slate-800">
            <tr>
              <th className="p-2.5">Target</th>
              <th className="p-2.5">Obs ID</th>
              <th className="p-2.5">Band</th>
              <th className="p-2.5">Center Value</th>
              <th className="p-2.5">Fatal Flags</th>
              <th className="p-2.5">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {filtered.map((o) => {
              const isSel = selectedObs?.obs_id === o.obs_id && selectedObs?.band === o.band;
              const isClean = o.screening_status === "PASSED_CLEAN";
              return (
                <tr
                  key={`${o.obs_id}_${o.band}`}
                  onClick={() => onSelect(o)}
                  tabIndex={0}
                  onKeyDown={event=> {if(event.key==='Enter' || event.key===' ') {event.preventDefault(); onSelect(o);}}}
                  aria-selected={isSel}
                  className={`cursor-pointer transition ${
                    isSel ? "bg-cyan-500/20 text-cyan-200" : "hover:bg-slate-900/60 text-slate-300"
                  }`}
                >
                  <td className="p-2.5 font-bold">{o.target}</td>
                  <td className="p-2.5 text-cyan-400">{o.obs_id}</td>
                  <td className="p-2.5">{o.band}</td>
                  <td className="p-2.5">
                    {o.center_image_val != null ? `${o.center_image_val.toFixed(2)}` : 'Nonfinite / unavailable'}
                  </td>
                  <td className="p-2.5">
                    <span className={o.aperture_fatal_count > 0 ? "text-rose-400 font-bold" : "text-emerald-400"}>
                      {o.aperture_fatal_count} / {o.aperture_total_pixels}
                    </span>
                  </td>
                  <td className="p-2.5">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        isClean
                          ? "bg-emerald-950 text-emerald-400 border border-emerald-800/50"
                          : "bg-rose-950 text-rose-400 border border-rose-800/50"
                      }`}
                    >
                      {o.screening_status}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!filtered.length && <div className="py-12 text-center text-sm text-slate-500">No observation records match this filter.</div>}
      </div>
    </div>
  );
}
