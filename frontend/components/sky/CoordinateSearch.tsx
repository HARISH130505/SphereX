"use client";

import React, { useState } from "react";
import { Compass } from "lucide-react";

interface Props {
  onSearch: (ra: number, dec: number, name: string) => void;
}

export function CoordinateSearch({ onSearch }: Props) {
  const [ra, setRa] = useState("");
  const [dec, setDec] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const r = parseFloat(ra);
    const d = parseFloat(dec);
    if (!isNaN(r) && !isNaN(d)) {
      onSearch(r, d, `Custom (${r.toFixed(2)}, ${d.toFixed(2)})`);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-2 text-xs font-mono">
      <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800">
        <Compass className="w-3.5 h-3.5 text-cyan-400" />
        <input
          type="text"
          placeholder="RA (deg)"
          value={ra}
          onChange={(e) => setRa(e.target.value)}
          className="w-16 bg-transparent text-slate-200 focus:outline-none placeholder-slate-600"
        />
        <input
          type="text"
          placeholder="Dec (deg)"
          value={dec}
          onChange={(e) => setDec(e.target.value)}
          className="w-16 bg-transparent text-slate-200 focus:outline-none placeholder-slate-600"
        />
      </div>
      <button
        type="submit"
        className="px-3 py-1.5 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold hover:bg-cyan-500/30 transition"
      >
        Go
      </button>
    </form>
  );
}
