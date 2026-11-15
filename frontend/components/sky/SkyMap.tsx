"use client";

import React from "react";
import { TargetInfo } from "@/lib/types";

interface Props {
  targets: TargetInfo[];
  selectedTarget: string;
  onSelectTarget: (name: string) => void;
}

export function SkyMap({ targets, selectedTarget, onSelectTarget }: Props) {
  return (
    <div className="relative w-full aspect-[2/1] rounded-xl bg-slate-950 border border-slate-800 overflow-hidden p-4">
      <div className="absolute top-2 left-2 text-[10px] font-mono text-slate-500 uppercase">
        All-Sky Celestial Coordinate Projection (ICRS)
      </div>
      <svg className="w-full h-full" viewBox="0 0 720 360">
        {/* Coordinate Grid Lines */}
        {[60, 120, 180, 240, 300].map((ra) => {
          const x = (ra / 360) * 720;
          return <line key={ra} x1={x} y1="0" x2={x} y2="360" stroke="#1e293b" strokeDasharray="3 3" />;
        })}
        {[90, 180, 270].map((dec) => {
          return <line key={dec} x1="0" y1={dec} x2="720" y2={dec} stroke="#1e293b" strokeDasharray="3 3" />;
        })}

        {/* Targets */}
        {targets.map((t) => {
          const x = (t.ra / 360) * 720;
          const y = ((90 - t.dec) / 180) * 360;
          const isSel = t.name === selectedTarget;
          const isSat = t.saturation_risk === "CRITICAL_SATURATED";

          return (
            <g key={t.id} onClick={() => onSelectTarget(t.name)} className="cursor-pointer">
              <circle
                cx={x}
                cy={y}
                r={isSel ? 7 : 4}
                fill={isSat ? "#f43f5e" : "#38bdf8"}
                stroke="#030712"
                strokeWidth={1.5}
                className={isSel ? "animate-pulse" : ""}
              />
              <text
                x={x + 10}
                y={y + 4}
                fill={isSel ? "#38bdf8" : "#94a3b8"}
                fontSize="11"
                fontFamily="monospace"
                fontWeight={isSel ? "bold" : "normal"}
              >
                {t.name}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
