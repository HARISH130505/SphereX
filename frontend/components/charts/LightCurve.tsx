"use client";

import React from "react";
import { ObservationRecord } from "@/lib/types";

interface Props {
  observations: ObservationRecord[];
}

export function LightCurve({ observations }: Props) {
  const sorted = [...observations].filter((o) => o.center_image_val != null).sort((a, b) => a.obs_time_mjd - b.obs_time_mjd);

  if (sorted.length === 0) {
    return <div className="text-xs font-mono text-slate-500">No finite photometric points available.</div>;
  }

  const minMjd = Math.min(...sorted.map((o) => o.obs_time_mjd));
  const maxMjd = Math.max(...sorted.map((o) => o.obs_time_mjd)) || minMjd + 1;
  const minVal = Math.min(...sorted.map((o) => o.center_image_val!));
  const maxVal = Math.max(...sorted.map((o) => o.center_image_val!)) || minVal + 1;

  return (
    <div className="relative w-full h-[200px] bg-slate-950 rounded-xl border border-slate-800 p-4">
      <div className="text-[10px] font-mono text-slate-500 mb-2">FLUX vs TIME (MJD)</div>
      <svg className="w-full h-[140px]" viewBox="0 0 600 140">
        {sorted.map((o, i) => {
          const x = ((o.obs_time_mjd - minMjd) / (maxMjd - minMjd || 1)) * 540 + 30;
          const y = 120 - ((o.center_image_val! - minVal) / (maxVal - minVal || 1)) * 100;
          return (
            <g key={`${o.obs_id}_${o.band}_${i}`}>
              <circle cx={x} cy={y} r={4} fill="#38bdf8" stroke="#030712" />
            </g>
          );
        })}
      </svg>
    </div>
  );
}
