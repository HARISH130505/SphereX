"use client";

import React, { useState, useEffect } from "react";
import { fetchTargetTimeline, fetchTargets } from "@/lib/api";
import { observationKey } from "@/lib/observations";
import { TargetTimelineResponse, TimelineItem } from "@/lib/types";
import { Clock, CheckCircle2, AlertTriangle, ShieldAlert } from "lucide-react";
import { selectTarget } from '@/lib/selected-target';

interface Props {
  currentTarget: string;
  onSelectTarget: (target: string) => void;
  onSelectEpochPair: (obs1Id: string, obs2Id: string) => void;
  selectedEpoch1Id?: string;
  selectedEpoch2Id?: string;
}

const TARGET_LIST = [
  "M101",
  "Mira",
  "Delta Cephei",
  "Algol",
];

export function ObservationTimeline({
  currentTarget,
  onSelectTarget,
  onSelectEpochPair,
  selectedEpoch1Id,
  selectedEpoch2Id,
}: Props) {
  const [timelineData, setTimelineData] = useState<TargetTimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [targetNames, setTargetNames] = useState(TARGET_LIST.map(name=>({id:name,name})));
  useEffect(() => { fetchTargets().then(rows => setTargetNames(rows.map(row => ({id:row.name,name:row.name})))).catch(console.error); }, []);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    fetchTargetTimeline(currentTarget)
      .then((data) => {
        if (isMounted) {
          setTimelineData(data);
        }
      })
      .catch((err) => {
        if (isMounted) setError(err.message || "Failed to load timeline");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [currentTarget]);

  return (
    <div className="glass-panel p-5 space-y-4">
      {/* Target Selector Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2">
          <Clock className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200">
            Observation timeline & provenance
          </h3>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {targetNames.map((tgt) => (
            <button
              key={tgt.id}
              onClick={() => {
                setTimelineData(null);
                setLoading(true);
                setError(null);
                selectTarget(tgt.id);
                onSelectTarget(tgt.id);
              }}
              className={`px-3 py-1 rounded text-xs font-semibold transition ${
                currentTarget.toLowerCase() === tgt.id.toLowerCase()
                  ? "bg-cyan-500 text-slate-950 font-bold shadow-md shadow-cyan-500/20"
                  : "bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-700/60"
              }`}
            >
              {tgt.name}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="py-8 text-center text-xs text-slate-400 animate-pulse font-mono">
          Querying archive timeline and observation provenance for {currentTarget}...
        </div>
      )}

      {error && (
        <div className="p-4 rounded-lg bg-rose-950/40 border border-rose-800/60 text-xs text-rose-300 flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {timelineData && !loading && (
        <div className="space-y-4">
          {/* Header Stats */}
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-slate-400 bg-slate-950/60 p-4 rounded-xl border border-slate-800">
            <div className="flex flex-wrap items-center gap-3">
              <span>Target: <strong className="text-slate-200">{timelineData.target}</strong></span>
              <span>Coordinates: <strong className="text-slate-200">{timelineData.ra.toFixed(4)}°, {timelineData.dec.toFixed(4)}°</strong></span>
              <span>Category: <strong className="text-slate-200">{timelineData.category}</strong></span>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <span>Total Obs: <strong className="text-cyan-400">{timelineData.observation_count}</strong></span>
              <span>Eligible for Compare: <strong className="text-emerald-400">{timelineData.eligible_count}</strong></span>
              {timelineData.coverage_status === "NO_LOCAL_RECORDS_SEARCH_INCOMPLETE" ? (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-300 border border-amber-800">
                  NO LOCAL RECORDS / SEARCH INCOMPLETE
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">
                  {timelineData.coverage_status.replaceAll('_',' ')}
                </span>
              )}
            </div>
          </div>

          {timelineData.timeline.length === 0 ? (
            <div className="p-6 text-center rounded-lg bg-slate-900/60 border border-slate-800 text-xs text-slate-400 space-y-2">
              <ShieldAlert className="w-8 h-8 text-amber-400 mx-auto opacity-80" />
              <p className="font-semibold text-slate-300">No observation products are currently cataloged for this target.</p>
              <p className="text-[11px] text-slate-500 max-w-md mx-auto">
                No verified products are available in the current application catalog.
              </p>
            </div>
          ) : (
            <div className="grid max-h-[440px] grid-cols-1 gap-3 overflow-y-auto pr-1 md:grid-cols-2 lg:grid-cols-3">
              {timelineData.timeline.map((item: TimelineItem) => {
                const productKey = observationKey(item);
                const isSelectedEp1 = selectedEpoch1Id === productKey;
                const isSelectedEp2 = selectedEpoch2Id === productKey;

                return (
                  <div
                    key={productKey}
                    className={`p-3.5 rounded-lg border transition space-y-2.5 font-mono text-xs ${
                      isSelectedEp1
                        ? "bg-cyan-950/40 border-cyan-500/80 shadow-sm shadow-cyan-500/20"
                        : isSelectedEp2
                        ? "bg-purple-950/40 border-purple-500/80 shadow-sm shadow-purple-500/20"
                        : "bg-slate-900/70 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="break-all font-medium text-slate-200">{item.obs_id}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-cyan-300 border border-slate-700">
                        {item.band}
                      </span>
                    </div>

                    <div className="text-[11px] text-slate-400 space-y-0.5">
                      <div>Date: <span className="text-slate-300">{item.obs_time_iso || `MJD ${item.obs_time_mjd.toFixed(2)}`}</span></div>
                      <div>Archive product: <span className="text-slate-300 truncate block text-[10px]" title={item.archive_product_id || item.product_identifier}>{item.product_identifier}</span></div>
                      <div>Dimensions: <span className="text-slate-300">{item.image_shape}</span></div>
                    </div>

                    <div className="flex items-center justify-between pt-1 border-t border-slate-800/80 text-[10px]">
                      {item.comparison_eligible ? (
                        <span className="flex items-center space-x-1 text-emerald-400">
                          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                          <span>Comparison Ready</span>
                        </span>
                      ) : (
                        <span className="flex items-center space-x-1 text-amber-400" title={item.eligibility_reason}>
                          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate max-w-[140px]">{item.eligibility_reason}</span>
                        </span>
                      )}

                      <div className="flex items-center space-x-1">
                        <button
                          onClick={() => onSelectEpochPair(productKey, selectedEpoch2Id || "")}
                          disabled={!item.comparison_eligible}
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase transition ${
                            isSelectedEp1
                              ? "bg-cyan-500 text-slate-950"
                              : "bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-30"
                          }`}
                        >
                          Ep 1
                        </button>
                        <button
                          onClick={() => onSelectEpochPair(selectedEpoch1Id || "", productKey)}
                          disabled={!item.comparison_eligible}
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase transition ${
                            isSelectedEp2
                              ? "bg-purple-500 text-white"
                              : "bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-30"
                          }`}
                        >
                          Ep 2
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

