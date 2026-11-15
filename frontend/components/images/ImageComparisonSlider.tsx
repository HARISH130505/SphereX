"use client";

import React, { useState } from "react";
import Image from "next/image";

interface Props {
  img1: string;
  img2: string;
}

export function ImageComparisonSlider({ img1, img2 }: Props) {
  const [swipePos, setSwipePos] = useState<number>(50);

  return (
    <div className="space-y-3">
      <div className="relative aspect-video max-h-[400px] w-full rounded-xl overflow-hidden bg-slate-950 border border-slate-800 select-none">
        <Image unoptimized width={1000} height={1000} src={img1} alt="Epoch 1" className="absolute inset-0 w-full h-full object-contain pixelated" />
        <Image unoptimized width={1000} height={1000}
          src={img2}
          alt="Epoch 2"
          className="absolute inset-0 w-full h-full object-contain pixelated"
          style={{ clipPath: `inset(0 ${100 - swipePos}% 0 0)` }}
        />
        <div className="absolute inset-y-0 w-0.5 bg-cyan-400" style={{ left: `${swipePos}%` }} />
        <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-slate-950/80 text-[10px] font-mono text-cyan-400 border border-cyan-800">
          Epoch 2 ({swipePos}%)
        </div>
        <div className="absolute top-2 right-2 px-2 py-0.5 rounded bg-slate-950/80 text-[10px] font-mono text-slate-300 border border-slate-800">
          Epoch 1
        </div>
      </div>

      <div className="flex items-center space-x-3 px-2">
        <span className="text-xs text-slate-400 font-mono">Swipe Split</span>
        <input
          type="range"
          min="0"
          max="100"
          value={swipePos}
          onChange={(e) => setSwipePos(Number(e.target.value))}
          className="flex-1 accent-cyan-400 cursor-pointer"
        />
        <span className="text-xs font-mono text-cyan-400">{swipePos}%</span>
      </div>
    </div>
  );
}
