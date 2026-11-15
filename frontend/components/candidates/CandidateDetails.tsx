"use client";

import React from "react";
import { ObservationRecord } from "@/lib/types";
import { QualityFlags } from "./QualityFlags";

interface Props {
  obs: ObservationRecord | null;
}

export function CandidateDetails({ obs }: Props) {
  if (!obs) {
    return <div className="text-xs font-mono text-slate-500">Select an observation to view vetting details.</div>;
  }

  return (
    <div className="space-y-3 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <span className="font-bold text-slate-200">{obs.obs_id}</span>
        <span className="text-cyan-400 font-semibold">{obs.band}</span>
      </div>
      <div>
        <span className="text-slate-500 text-[10px] block mb-1">DECODED DETECTOR BITMASK</span>
        <QualityFlags flagsDecoded={obs.center_flags_decoded} />
      </div>
      <div className="pt-2 border-t border-slate-800">
        <span className="text-slate-500 text-[10px] block mb-1">REJECTION / CAVEAT REASON</span>
        <p className="text-[11px] text-slate-300 font-sans leading-relaxed">{obs.rejection_reason}</p>
      </div>
    </div>
  );
}
