import Link from "next/link";
import { ArrowRight, ArrowUpRight, Telescope } from "lucide-react";

const workspaces = [
  ["Sky Explorer", "/sky-explorer"],
  ["Epoch Comparison", "/epoch-comparison"],
  ["Candidate Investigator", "/candidate-investigator"],
  ["Spectral Explorer", "/spectral-explorer"],
];

export function Footer() {
  return <footer className="mt-8 border-t border-cyan-400/10 bg-slate-950">
    <div className="mx-auto max-w-7xl px-4 pb-6 pt-10 lg:px-8 lg:pt-12">
      <div className="grid gap-9 sm:grid-cols-2 lg:grid-cols-[1.5fr_1fr_1fr_1fr] lg:gap-12">
        <div>
          <Link href="/" className="inline-flex items-center gap-2.5 rounded-lg"><Telescope aria-hidden="true" className="h-5 w-5 text-cyan-400" /><span className="text-base font-semibold tracking-tight text-slate-200">SPHEREx <span className="font-normal text-cyan-300">Explorer</span></span></Link>
          <p className="mt-4 max-w-xs text-xs leading-6 text-slate-500">A workspace for exploring genuine infrared observations and the evidence behind them.</p>
          <Link href="/sky-explorer?target=M101" className="mt-5 inline-flex items-center gap-2 text-xs text-cyan-300 transition hover:text-cyan-100">Begin with M101 <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" /></Link>
        </div>
        <nav aria-label="Footer science workspaces"><h2 className="text-[10px] font-semibold uppercase tracking-[.18em] text-slate-400">Explore the data</h2><ul className="mt-4 space-y-3">{workspaces.map(([label, href]) => <li key={href}><Link href={href} className="rounded text-xs text-slate-500 transition hover:text-cyan-200">{label}</Link></li>)}</ul></nav>
        <nav aria-label="Footer project navigation"><h2 className="text-[10px] font-semibold uppercase tracking-[.18em] text-slate-400">Understand the science</h2><ul className="mt-4 space-y-3">{[
          ["Observatory overview", "/"],
          ["Research Assistant", "/research-assistant"],
          ["About the project", "/about"],
        ].map(([label, href]) => <li key={href}><Link href={href} className="rounded text-xs text-slate-500 transition hover:text-cyan-200">{label}</Link></li>)}</ul></nav>
        <nav aria-label="Official mission and archive resources"><h2 className="text-[10px] font-semibold uppercase tracking-[.18em] text-slate-400">Original sources</h2><ul className="mt-4 space-y-3">{[
          ["NASA SPHEREx mission", "https://science.nasa.gov/mission/spherex/"],
          ["NASA/JPL science", "https://www.jpl.nasa.gov/press-kits/spherex/mission-overview/science/"],
          ["IPAC IRSA archive", "https://irsa.ipac.caltech.edu/Missions/spherex.html"],
        ].map(([label, href]) => <li key={href}><a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 rounded text-xs text-slate-500 transition hover:text-cyan-200">{label}<ArrowUpRight aria-hidden="true" className="h-3 w-3" /><span className="sr-only"> (opens in a new tab)</span></a></li>)}</ul></nav>
      </div>
    </div>
  </footer>;
}
