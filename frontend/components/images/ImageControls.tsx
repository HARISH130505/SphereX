"use client";

import React from "react";

interface Props {
  stretch: string;
  setStretch: (s: string) => void;
  colormap: string;
  setColormap: (c: string) => void;
}

export function ImageControls({ stretch, setStretch, colormap, setColormap }: Props) {
  return (
    <div className="grid grid-cols-2 gap-4 p-3 rounded-xl bg-slate-900/60 border border-slate-800">
      <div>
        <label className="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1.5">
          Contrast Stretch
        </label>
        <div className="grid grid-cols-4 gap-1">
          {["asinh", "log", "linear", "sqrt"].map((s) => (
            <button
              key={s}
              onClick={() => setStretch(s)}
              className={`py-1 text-xs font-mono font-semibold rounded uppercase transition ${
                stretch === s
                  ? "bg-cyan-500 text-slate-950 font-bold"
                  : "bg-slate-800/80 text-slate-400 hover:text-slate-200"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1.5">
          Colormap
        </label>
        <div className="grid grid-cols-4 gap-1">
          {["plasma", "viridis", "inferno", "coolwarm"].map((c) => (
            <button
              key={c}
              onClick={() => setColormap(c)}
              className={`py-1 text-xs font-mono font-semibold rounded capitalize transition ${
                colormap === c
                  ? "bg-cyan-500 text-slate-950 font-bold"
                  : "bg-slate-800/80 text-slate-400 hover:text-slate-200"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
