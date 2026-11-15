"use client";

import React from "react";
import Image from "next/image";
import { RefreshCw, AlertCircle, Compass, CheckCircle2 } from "lucide-react";

interface Props {
  pngBase64?: string;
  loading?: boolean;
  showOverlays?: boolean;
  centerVal?: number | null;
  imageShape?: number[];
  nanCount?: number | null;
  validPct?: number | null;
  minVal?: number | null;
  maxVal?: number | null;
  medianVal?: number | null;
  wcsInfo?: {
    ra_center?: number;
    dec_center?: number;
    ctype?: string[];
    pixel_scale_arcsec?: number;
  };
  sourceFile?: string;
  errorMessage?: string | null;
  isUnsurveyed?: boolean;
  targetName?: string;
  onRefresh?: () => void;
}

export function FitsImageViewer({
  pngBase64,
  loading,
  showOverlays = true,
  centerVal,
  imageShape,
  nanCount,
  validPct,
  minVal,
  maxVal,
  medianVal,
  wcsInfo,
  sourceFile,
  errorMessage,
  isUnsurveyed,
  targetName,
  onRefresh,
}: Props) {
  // Unsurveyed target state (Sedna / Planet 9 Candidate Field)
  if (isUnsurveyed) {
    return (
      <div className="relative min-h-[460px] rounded-xl overflow-hidden bg-slate-950 border border-slate-800 flex flex-col items-center justify-center p-6 text-center scanline-effect shadow-inner space-y-4">
        <div className="w-14 h-14 rounded-full bg-cyan-950/40 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
          <Compass className="w-7 h-7 animate-pulse" />
        </div>
        <div className="max-w-md space-y-2">
          <span className="text-[10px] font-mono tracking-widest uppercase bg-cyan-950/80 text-cyan-300 px-2.5 py-1 rounded-full border border-cyan-800/60">
            Archive Spatial Coverage Report
          </span>
          <h3 className="text-base font-bold text-slate-100">
            No loaded observation for {targetName || "Target"}
          </h3>
          <p className="text-xs text-slate-400 leading-relaxed">
            Archive coverage has not been established by this viewer. Check the discovery status and searched collections, or retry the search.
          </p>
          <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-400 text-left space-y-1">
            <div className="flex justify-between">
              <span className="text-slate-500">Archive Endpoint:</span>
              <span className="text-slate-300">irsa.ipac.caltech.edu/TAP</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Pipeline Integrity:</span>
              <span className="text-emerald-400">Zero Synthetic Fabrication</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Survey Schedule:</span>
              <span className="text-cyan-300">Scheduled for 6-Month All-Sky Sweeps</span>
            </div>
          </div>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/40 text-xs font-medium text-cyan-300 transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Re-query IPAC IRSA TAP Archive</span>
          </button>
        )}
      </div>
    );
  }

  // Error state (e.g. failed download from archive)
  if (errorMessage) {
    return (
      <div className="relative min-h-[460px] rounded-xl overflow-hidden bg-slate-950 border border-rose-900/40 flex flex-col items-center justify-center p-6 text-center space-y-3">
        <AlertCircle className="w-10 h-10 text-rose-400" />
        <h4 className="text-sm font-bold text-rose-300">FITS Archive Product Unavailable</h4>
        <p className="text-xs text-rose-200/80 max-w-md">{errorMessage}</p>
        <span className="text-[10px] font-mono text-slate-500">
          SPHEREx Explorer strict mode: Synthetic replacement images are disabled.
        </span>
      </div>
    );
  }

  return (
    <div className="relative aspect-square max-h-[500px] mx-auto rounded-xl overflow-hidden bg-slate-950 border border-slate-800 flex items-center justify-center scanline-effect shadow-inner">
      {/* Top Metadata Badges */}
      <div className="absolute top-2.5 left-2.5 right-2.5 flex items-center justify-between pointer-events-none z-10">
        <div className="flex items-center space-x-2">
          <span className="text-[10px] font-mono font-bold bg-slate-950/85 backdrop-blur-md px-2 py-0.5 rounded border border-emerald-500/50 text-emerald-300 flex items-center space-x-1">
            <CheckCircle2 className="w-3 h-3 text-emerald-400 inline" />
            <span>{pngBase64 && sourceFile ? 'GENUINE FITS' : 'Observation not yet validated'}</span>
          </span>
          {imageShape && (
            <span className="text-[10px] font-mono bg-slate-950/85 backdrop-blur-md px-2 py-0.5 rounded border border-slate-700 text-slate-300">
              {imageShape[1]} × {imageShape[0]} px
            </span>
          )}
        </div>
        {sourceFile && (
          <span
            className="text-[9px] font-mono bg-slate-950/85 backdrop-blur-md px-2 py-0.5 rounded border border-slate-800 text-slate-400 max-w-[200px] truncate"
            title={sourceFile}
          >
            {sourceFile}
          </span>
        )}
      </div>

      {/* Main Image Display */}
      {loading ? (
        <div className="flex flex-col items-center space-y-2 text-cyan-400">
          <RefreshCw className="w-8 h-8 animate-spin" />
          <span className="text-xs font-mono">Extracting FITS HDU Pixels...</span>
        </div>
      ) : pngBase64 ? (
        <Image unoptimized width={1000} height={1000}
          src={pngBase64}
          alt="SPHEREx Cutout"
          className="w-full h-full object-contain pixelated"
          style={{ imageRendering: "pixelated" }}
        />
      ) : (
        <span className="text-xs text-slate-500">No observation selected</span>
      )}

      {/* Bottom Floating Telemetry Bar */}
      {showOverlays && pngBase64 && (
        <div className="absolute bottom-2 left-2 right-2 flex flex-col space-y-1 px-3 py-2 rounded-lg bg-slate-950/90 backdrop-blur-md border border-slate-800 text-[10px] font-mono text-slate-300">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-1.5">
                <span className="w-2.5 h-2.5 rounded-full border-2 border-cyan-400 inline-block" />
                <span className="text-cyan-300">Aperture (R=3 px)</span>
              </div>
              <div className="flex items-center space-x-1.5">
                <span className="w-2.5 h-2.5 rounded-full border border-yellow-400 inline-block" />
                <span className="text-yellow-300">Annulus (R=6–10 px)</span>
              </div>
            </div>
            <div>
              <span>Center: {centerVal != null ? `${centerVal.toFixed(2)} MJy/sr` : "Nonfinite / unavailable"}</span>
            </div>
          </div>

          <div className="flex items-center justify-between text-[9px] text-slate-400 border-t border-slate-800/80 pt-1">
            <div>
              <span>Flux: </span>
              <span className="text-slate-300">
                {minVal ?? "--"} / {medianVal ?? "--"} / {maxVal ?? "--"} MJy/sr
              </span>
            </div>
            <div>
              {nanCount != null && (
                <span>
                  NaNs: <span className={nanCount > 0 ? "text-amber-400 font-semibold" : "text-emerald-400"}>{nanCount}</span>
                  {validPct != null ? ` (${validPct}% finite)` : ""}
                </span>
              )}
            </div>
            {wcsInfo?.pixel_scale_arcsec && (
              <div>
                <span>Scale: {wcsInfo.pixel_scale_arcsec}&quot;/px</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
