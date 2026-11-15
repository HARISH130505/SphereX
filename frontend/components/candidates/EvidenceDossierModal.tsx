"use client";

import React, { useState } from "react";
import { Download, Copy, Check, X, ShieldCheck } from "lucide-react";
import type { EvidenceDossier } from "@/lib/types";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  targetName: string;
  markdownReport?: string;
  dossierJson?: EvidenceDossier;
}

export function EvidenceDossierModal({
  isOpen,
  onClose,
  targetName,
  markdownReport = "",
  dossierJson,
}: Props) {
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(markdownReport);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadMarkdown = () => {
    const blob = new Blob([markdownReport], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `SPHEREx_Evidence_${targetName.replace(/\s+/g, "_")}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const downloadJson = () => {
    const blob = new Blob([JSON.stringify(dossierJson ?? {}, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `SPHEREx_Dossier_${targetName.replace(/\s+/g, "_")}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="glass-panel w-full max-w-4xl max-h-[88vh] flex flex-col bg-slate-900 border border-slate-700 shadow-2xl rounded-xl overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/70">
          <div className="flex items-center space-x-2.5">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <div>
              <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wide">
                Scientific Evidence Dossier: {targetName}
              </h2>
              <p className="text-[11px] text-slate-400 font-mono">
                Reproducible astronomical report with FITS provenance & variance propagation
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleCopy}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-mono bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              title="Copy Markdown Report"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? "Copied" : "Copy"}</span>
            </button>
            <button
              onClick={downloadMarkdown}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-mono bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold transition shadow-sm"
              title="Export Markdown Document"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Report (.md)</span>
            </button>
            <button
              onClick={downloadJson}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-mono bg-purple-600 hover:bg-purple-500 text-white font-bold transition shadow-sm"
              title="Export Machine-Readable JSON"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Dossier (.json)</span>
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Body: Rendered Markdown Preview */}
        <div className="p-6 overflow-y-auto space-y-4 font-mono text-xs text-slate-300 bg-slate-950/40 flex-1 leading-relaxed selection:bg-cyan-500/30">
          <pre className="whitespace-pre-wrap font-mono text-[11px] text-slate-300 bg-slate-900/90 p-4 rounded-lg border border-slate-800 overflow-x-auto">
            {markdownReport || "Generating evidence dossier report..."}
          </pre>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950/70 flex items-center justify-between text-[11px] font-mono text-slate-500">
          <span>
            {dossierJson?.reproducibility?.pipeline ?? "SPHEREx Explorer Evidence Engine"} v{dossierJson?.reproducibility?.pipeline_version ?? "Unavailable"}
            {" | "}{dossierJson?.reproducibility?.provenance_status ?? "Unavailable"} provenance
            {" | "}{dossierJson?.assessment?.scientific_validity_status ?? "Validity unavailable"}
          </span>
          <span
            className="max-w-[48%] truncate"
            title={dossierJson?.reproducibility?.reproducibility_hash ?? "Hash unavailable"}
          >
            SHA-256: {dossierJson?.reproducibility?.reproducibility_hash ?? "Unavailable"}
          </span>
        </div>
      </div>
    </div>
  );
}

