"use client";

import React from "react";

interface Props {
  flagsDecoded?: string;
}

export function QualityFlags({ flagsDecoded }: Props) {
  const flags = flagsDecoded ? flagsDecoded.split("|").filter(Boolean) : [];
  return (
    <div className="flex flex-wrap gap-1.5">
      {flags.length > 0 ? (
        flags.map((f) => (
          <span
            key={f}
            className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
              ["OVERFLOW", "SUR_ERROR", "BLOOM", "SATURATED"].includes(f)
                ? "bg-rose-950 text-rose-300 border border-rose-800/60"
                : "bg-slate-800 text-cyan-300 border border-slate-700"
            }`}
          >
            {f}
          </span>
        ))
      ) : (
        <span className="text-[10px] text-slate-500 font-mono">NO ACTIVE FLAGS</span>
      )}
    </div>
  );
}
