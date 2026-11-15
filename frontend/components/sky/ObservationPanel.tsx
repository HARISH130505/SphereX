"use client";

import React from "react";
import { ObservationRecord } from "@/lib/types";
import { AlertCircle, FileX } from "lucide-react";

interface Props {
  observations: ObservationRecord[];
  selectedObs: ObservationRecord | null;
  onSelectObs: (obs: ObservationRecord) => void;
}

export function ObservationPanel({ observations, selectedObs, onSelectObs }: Props) {
  if (observations.length === 0) {
    return (
      <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 text-center space-y-2">
        <FileX className="w-8 h-8 text-slate-500 mx-auto" />
        <p className="text-xs text-slate-400">
          No observation records cataloged for this target in current archive screening.
        </p>
        <span className="text-[10px] font-mono text-slate-500">
          No verified observations are available in the predefined catalog for this target.
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
      {observations.map((obs) => {
        const isSelected = selectedObs?.product_id === obs.product_id;
        const isPassed = obs.screening_status === "PASSED_CLEAN";
        const isCaveat = obs.screening_status === "FEASIBLE_WITH_CAVEATS";
        const isFailed = obs.download_status === "FAILED_DOWNLOAD";

        return (
          <div
            key={obs.product_id}
            onClick={() => onSelectObs(obs)}
            role="button"
            tabIndex={0}
            aria-pressed={isSelected}
            onKeyDown={event=> {if(event.key==='Enter'||event.key===' ') {event.preventDefault();onSelectObs(obs);}}}
            className={`p-2.5 rounded-lg border cursor-pointer transition ${
              isSelected
                ? "bg-cyan-500/15 border-cyan-400"
                : isFailed
                ? "bg-slate-900/40 border-rose-900/30 hover:border-rose-700/50"
                : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-mono">
              <span className="font-bold text-slate-200 break-all">{obs.obs_publisher_did || obs.obs_id}</span>
              <span className="text-cyan-400 font-semibold">{obs.band}</span>
            </div>

            <div className="flex items-center justify-between text-[11px] text-slate-400 mt-1">
              <div className="flex items-center space-x-2">
                <span>MJD {obs.obs_time_mjd.toFixed(2)}</span>
                {obs.image_shape && (
                  <span className="text-[10px] text-slate-500 font-mono">
                    {obs.image_shape}
                  </span>
                )}
              </div>

              <span
                className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                  isPassed
                    ? "bg-emerald-950 text-emerald-400 border border-emerald-800/50"
                    : isCaveat
                    ? "bg-amber-950 text-amber-400 border border-amber-800/50"
                    : isFailed
                    ? "bg-rose-950/80 text-rose-300 border border-rose-700/60 flex items-center space-x-1"
                    : "bg-rose-950 text-rose-400 border border-rose-800/50"
                }`}
              >
                {isFailed && <AlertCircle className="w-2.5 h-2.5 inline mr-1 text-rose-400" />}
                {obs.screening_status}
              </span>
            </div>

            {isFailed && (
              <div className="mt-1.5 text-[10px] text-rose-300/80 bg-rose-950/30 px-2 py-0.5 rounded border border-rose-900/40 font-mono truncate">
                Archive Error: {obs.rejection_reason || "Corrupted download"}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
