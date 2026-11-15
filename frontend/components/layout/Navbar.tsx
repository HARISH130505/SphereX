"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, ArrowUpRight, Compass, Info, Layers, Menu, Sparkles, Telescope, Waves, X } from "lucide-react";

const links = [
  { href: "/", label: "Overview", icon: Compass, detail: "Your observatory home" },
  { href: "/sky-explorer", label: "Sky Explorer", icon: Telescope, detail: "Genuine images and pixel quality" },
  { href: "/epoch-comparison", label: "Compare", icon: Layers, detail: "Observations across time" },
  { href: "/candidate-investigator", label: "Candidates", icon: Activity, detail: "Screening and diagnostics" },
  { href: "/spectral-explorer", label: "Spectral", icon: Waves, detail: "Cataloged wavelength measurements" },
  { href: "/research-assistant", label: "Research AI", icon: Sparkles, detail: "Target-aware scientific questions" },
  { href: "/about", label: "About", icon: Info, detail: "Our project and the mission" },
];

export function Navbar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const active = links.find(link => link.href === pathname);

  return <header onKeyDown={event => { if (event.key === 'Escape') { setOpen(false); document.getElementById('navigation-toggle')?.focus(); } }} className="sticky top-0 z-50 border-b border-cyan-400/10 bg-slate-950/90 backdrop-blur-xl">
    <div className="mx-auto flex h-[76px] max-w-7xl items-center justify-between gap-4 px-4 lg:px-8">
      <Link href="/" aria-label="SPHEREx Explorer home" onClick={() => setOpen(false)} className="group flex shrink-0 items-center gap-3 rounded-lg">
        <span className="relative flex h-10 w-10 items-center justify-center overflow-hidden rounded-xl border border-cyan-400/30 bg-gradient-to-br from-cyan-400/15 to-indigo-400/10 transition group-hover:border-cyan-300/60"><span aria-hidden="true" className="absolute -right-2 -top-2 h-8 w-8 rounded-full border border-cyan-400/15" /><Telescope aria-hidden="true" className="relative h-5 w-5 text-cyan-300" /></span>
        <span><span className="block text-[15px] font-semibold tracking-tight text-slate-100">SPHEREx <span className="font-normal text-cyan-300">Explorer</span></span><span className="mt-0.5 block text-[8px] font-medium uppercase tracking-[.22em] text-slate-500">The infrared workspace</span></span>
      </Link>

      <nav aria-label="Main navigation" className="hidden items-center gap-1 rounded-xl border border-slate-800/80 bg-slate-900/40 p-1 xl:flex">
        {links.map(({ href, label, icon: Icon }) => {
          const selected = pathname === href;
          return <Link key={href} href={href} aria-current={selected ? 'page' : undefined} className={`relative flex items-center gap-1.5 rounded-lg px-3 py-2.5 text-[11px] font-medium transition ${selected ? 'bg-cyan-400/10 text-cyan-200 ring-1 ring-inset ring-cyan-400/20' : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-100'}`}><Icon aria-hidden="true" className="h-3.5 w-3.5" />{label}</Link>;
        })}
      </nav>

      <div className="flex items-center gap-3 xl:hidden">
        <span className="hidden text-xs text-slate-500 sm:block">{active?.label}</span>
        <button id="navigation-toggle" type="button" aria-label={open ? 'Close navigation' : 'Open navigation'} aria-expanded={open} aria-controls="mobile-navigation" onClick={() => setOpen(value => !value)} className={`flex h-10 w-10 items-center justify-center rounded-xl border transition ${open ? 'border-cyan-400/30 bg-cyan-400/10 text-cyan-200' : 'border-slate-700 bg-slate-900/60 text-slate-300 hover:border-slate-500'}`}>{open ? <X aria-hidden="true" className="h-5 w-5" /> : <Menu aria-hidden="true" className="h-5 w-5" />}</button>
      </div>
    </div>

    <nav id="mobile-navigation" aria-label="Mobile navigation" hidden={!open} className="max-h-[calc(100dvh-76px)] overflow-y-auto border-t border-slate-800 bg-slate-950 px-4 pb-5 pt-3 xl:hidden">
      <div className="mx-auto grid max-w-7xl gap-1 sm:grid-cols-2">{links.map(({ href, label, icon: Icon, detail }) => {
        const selected = pathname === href;
        return <Link key={href} href={href} onClick={() => setOpen(false)} aria-current={selected ? 'page' : undefined} className={`flex items-center gap-3 rounded-xl border p-3 transition ${selected ? 'border-cyan-400/20 bg-cyan-400/5 text-cyan-200' : 'border-transparent text-slate-300 hover:border-slate-800 hover:bg-slate-900'}`}><Icon aria-hidden="true" className={`h-4 w-4 shrink-0 ${selected ? 'text-cyan-300' : 'text-slate-500'}`} /><span className="flex-1"><span className="block text-sm font-medium">{label}</span><span className="mt-1 block text-[10px] text-slate-500">{detail}</span></span>{selected && <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" aria-hidden="true" />}</Link>;
      })}</div>
      <div className="mx-auto mt-3 flex max-w-7xl items-center justify-between border-t border-slate-800 px-3 pt-4"><span className="text-[10px] text-slate-500">Independent NASA Space Apps project</span><a href="https://irsa.ipac.caltech.edu/Missions/spherex.html" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-[10px] text-cyan-300">Original data archive <ArrowUpRight aria-hidden="true" className="h-3 w-3" /></a></div>
    </nav>
  </header>;
}
