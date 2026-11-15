"use client";

import React, { useState } from "react";
import Image from "next/image";
import { Layers } from "lucide-react";

interface Props {
  scientificAnalysisAllowed?: boolean;
  img1: string;
  img2: string;
  diffImg: string;
  sigImg: string;
  origImg1?: string;
  origImg2?: string;
  maskImg?: string;
}

export function DifferenceViewer({
  scientificAnalysisAllowed = true,
  img1,
  img2,
  diffImg,
  sigImg,
  origImg1,
  origImg2,
  maskImg,
}: Props) {
  const [mode, setMode] = useState<"standard" | "expanded">("standard");

  if (!scientificAnalysisAllowed) {
    return (
      <div className="space-y-3 text-xs text-amber-300">
        <p>Original epoch images for visual inspection. Scientific comparison is blocked; consult the failure reasons above.</p>
        <div className="grid grid-cols-2 gap-3">
          {[origImg1 || img1, origImg2 || img2].map((src, index) => (
            <figure key={index} className="space-y-2">
              <figcaption>Epoch {index + 1} original frame</figcaption>
              <Image unoptimized width={1000} height={1000} src={src} alt={`Epoch ${index + 1} original, visual inspection only`} className="w-full aspect-square object-contain bg-slate-950 rounded-lg" />
            </figure>
          ))}
        </div>
        <p>Difference, significance and overlap-mask products are unavailable.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* View sub-mode toggler */}
      <div className="flex items-center justify-between text-xs font-mono">
        <span className="text-slate-400 font-bold uppercase tracking-wider">
          {mode === "standard" ? "Primary Comparison Quadrant" : "Full Diagnostic Products (6-Up)"}
        </span>
        <button
          onClick={() => setMode((m) => (m === "standard" ? "expanded" : "standard"))}
          className="flex items-center space-x-1 px-2.5 py-1 rounded bg-slate-900 border border-slate-700 text-slate-300 hover:text-cyan-300 transition text-[11px]"
        >
          <Layers className="w-3.5 h-3.5" />
          <span>{mode === "standard" ? "Show Original & Overlap Mask" : "Show Primary 4-Up"}</span>
        </button>
      </div>

      {mode === "standard" ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="space-y-1 text-center">
            <span className="text-[11px] font-mono text-slate-400">Epoch 1 (Ref)</span>
            <div className="rounded-lg overflow-hidden bg-slate-950 border border-slate-800 aspect-square group relative">
              <Image unoptimized width={1000} height={1000} src={img1} alt="Epoch 1" className="w-full h-full object-contain pixelated" />
            </div>
          </div>
          <div className="space-y-1 text-center">
            <span className="text-[11px] font-mono text-slate-400">Epoch 2 (WCS Reprojected)</span>
            <div className="rounded-lg overflow-hidden bg-slate-950 border border-slate-800 aspect-square group relative">
              <Image unoptimized width={1000} height={1000} src={img2} alt="Epoch 2" className="w-full h-full object-contain pixelated" />
            </div>
          </div>
          <div className="space-y-1 text-center">
            <span className="text-[11px] font-mono text-cyan-400">Difference (I₂ - I₁)</span>
            <div className="rounded-lg overflow-hidden bg-slate-950 border border-cyan-800/40 aspect-square group relative">
              <Image unoptimized width={1000} height={1000} src={diffImg} alt="Difference" className="w-full h-full object-contain pixelated" />
            </div>
          </div>
          <div className="space-y-1 text-center">
            <span className="text-[11px] font-mono text-amber-400">Significance (S = D/√Var)</span>
            <div className="rounded-lg overflow-hidden bg-slate-950 border border-amber-800/40 aspect-square group relative">
              <Image unoptimized width={1000} height={1000} src={sigImg} alt="Significance" className="w-full h-full object-contain pixelated" />
            </div>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {/* Row 1: Raw inputs */}
          <div className="space-y-1 text-center">
            <span className="text-[11px] font-mono text-slate-400">Epoch 1 Original Frame</span>
            <div className="rounded-lg overflow-hidden bg-slate-950 border border-slate-800 aspect-square">
              <Image unoptimized width={1000} height={1000} src={origImg1 || img1} alt="Epoch 1 Original" className="w-full h-full object-contain pixelated" />
            </div>
          </div>
          <div className="space-y-1 text-center">
            <span className="text-[11px] font-mono text-slate-400">Epoch 2 Original Frame</span>
            <div className="rounded-lg overflow-hidden bg-slate-950 border border-slate-800 aspect-square">
              <Image unoptimized width={1000} height={1000} src={origImg2 || img2} alt="Epoch 2 Original" className="w-full h-full object-contain pixelated" />
            </div>
          </div>
          <div className="space-y-1 text-center">
            <span className="text-[11px] font-mono text-cyan-400">Epoch 2 (WCS Aligned Grid)</span>
            <div className="rounded-lg overflow-hidden bg-slate-950 border border-cyan-900/40 aspect-square">
              <Image unoptimized width={1000} height={1000} src={img2} alt="Epoch 2 Registered" className="w-full h-full object-contain pixelated" />
            </div>
          </div>

          {/* Row 2: Derived scientific products */}
          <div className="space-y-1 text-center">
            <span className="text-[11px] font-mono text-cyan-300">Differential Map (MJy/sr)</span>
            <div className="rounded-lg overflow-hidden bg-slate-950 border border-cyan-800/40 aspect-square">
              <Image unoptimized width={1000} height={1000} src={diffImg} alt="Difference" className="w-full h-full object-contain pixelated" />
            </div>
          </div>
          <div className="space-y-1 text-center">
            <span className="text-[11px] font-mono text-amber-300">Variance Significance (σ)</span>
            <div className="rounded-lg overflow-hidden bg-slate-950 border border-amber-800/40 aspect-square">
              <Image unoptimized width={1000} height={1000} src={sigImg} alt="Significance" className="w-full h-full object-contain pixelated" />
            </div>
          </div>
          <div className="space-y-1 text-center">
            <span className="text-[11px] font-mono text-emerald-400">Valid Overlap & Saturation Mask</span>
            <div className="rounded-lg overflow-hidden bg-slate-950 border border-emerald-800/40 aspect-square">
              {maskImg ? (
                <Image unoptimized width={1000} height={1000} src={maskImg} alt="Overlap Footprint Mask" className="w-full h-full object-contain pixelated" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-xs text-slate-500 font-mono">
                  Footprint mask ready
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
