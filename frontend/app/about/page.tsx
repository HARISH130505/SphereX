import Link from "next/link";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { ArrowRight, ArrowUpRight, BookOpen, Compass, Database, FileCheck2, Layers, ShieldCheck, Sparkles, Telescope } from "lucide-react";

const tools = [
  { icon: Telescope, title: "See the observation", text: "Open genuine FITS images, inspect their celestial coordinates, and explore contrast, detector flags, and usable pixels.", href: "/sky-explorer", label: "Sky Explorer" },
  { icon: Layers, title: "Compare with care", text: "Register compatible observations on a shared sky grid. Inspect difference and variance-aware significance maps where the data support them.", href: "/epoch-comparison", label: "Epoch Comparison" },
  { icon: FileCheck2, title: "Follow the evidence", text: "Review quality screening and candidate diagnostics. Export a comparison dossier with product identities, processing details, and scientific limitations.", href: "/candidate-investigator", label: "Candidate Investigator" },
  { icon: Sparkles, title: "Ask a scientific question", text: "Use the Gemini assistant to understand mission concepts and available target metadata. Consult the measured evidence before drawing conclusions.", href: "/research-assistant", label: "Research Assistant" },
];

export default function AboutPage() {
  return <div className="flex min-h-screen flex-col">
    <Navbar />
    <main className="mx-auto w-full max-w-7xl flex-1 space-y-10 p-4 lg:space-y-14 lg:p-8">
      <section className="relative overflow-hidden rounded-2xl border border-cyan-400/20 bg-gradient-to-br from-cyan-950/40 via-slate-950 to-indigo-950/30 p-6 sm:p-10 lg:p-12">
        <div aria-hidden="true" className="pointer-events-none absolute -right-24 -top-28 h-96 w-96 rounded-full border border-cyan-400/10"><div className="absolute inset-12 rounded-full border border-cyan-400/10" /><div className="absolute inset-24 rounded-full border border-cyan-400/10" /></div>
        <div className="relative max-w-3xl">
          <p className="text-[10px] font-semibold uppercase tracking-[.25em] text-cyan-400">About the project</p>
          <h1 className="mt-5 text-4xl font-semibold leading-tight tracking-tight text-slate-100 sm:text-5xl">A closer look at an<br /><span className="text-cyan-300">infrared universe.</span></h1>
          <p className="mt-6 max-w-2xl text-base leading-8 text-slate-300">SPHEREx Explorer connects public NASA observations with approachable tools for seeing, comparing, and questioning the data.</p>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-400">Built for a NASA Space Apps Challenge submission, this independent project helps students, curious explorers, and aspiring researchers move from an astronomical image to a traceable scientific investigation.</p>
          <div className="mt-8 flex flex-wrap gap-3"><Link href="/sky-explorer?target=M101" className="inline-flex items-center gap-3 rounded-xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300">Explore M101 <ArrowRight className="h-4 w-4" /></Link><a href="https://science.nasa.gov/mission/spherex/" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-3 rounded-xl border border-slate-700 px-5 py-3 text-sm text-slate-300 hover:border-cyan-400/50 hover:text-cyan-200">Meet the NASA mission <ArrowUpRight className="h-4 w-4" /></a></div>
        </div>
      </section>

      <section className="grid gap-8 lg:grid-cols-[1fr_1.35fr] lg:gap-14">
        <div><p className="text-[10px] font-semibold uppercase tracking-[.2em] text-cyan-400">The mission behind the data</p><h2 className="mt-3 text-2xl font-medium tracking-tight text-slate-100">One sky. Many infrared colors.</h2><p className="mt-4 text-sm leading-7 text-slate-400">SPHEREx stands for Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer. NASA&apos;s mission studies the early universe, the history of galaxies, and the ingredients for life in our galaxy.</p><a href="https://www.jpl.nasa.gov/press-kits/spherex/mission-overview/science/" target="_blank" rel="noopener noreferrer" className="mt-4 inline-flex items-center gap-2 text-xs text-cyan-300 hover:text-cyan-100">Read NASA/JPL&apos;s science overview <ArrowUpRight className="h-3.5 w-3.5" /></a></div>
        <div className="grid gap-4 sm:grid-cols-3">{[
          { value: "102", label: "Spectral channels", detail: "Infrared colors reveal different properties of celestial sources." },
          { value: "0.75–5", label: "Micrometers", detail: "Near-infrared wavelengths extend beyond human vision." },
          { value: "All sky", label: "Mission survey", detail: "The mission surveys the sky; this app presents a curated set of public products." },
        ].map(item => <div key={item.label} className="glass-panel flex flex-col justify-between p-5"><div><p className="text-3xl font-light tracking-tight text-cyan-200">{item.value}</p><p className="mt-2 text-xs font-medium text-slate-300">{item.label}</p></div><p className="mt-6 text-xs leading-6 text-slate-400">{item.detail}</p></div>)}</div>
      </section>

      <section>
        <div className="mb-6 flex items-end justify-between gap-4"><div><p className="text-[10px] font-semibold uppercase tracking-[.2em] text-cyan-400">From pixels to understanding</p><h2 className="mt-3 text-2xl font-medium tracking-tight text-slate-100">Your investigation, step by step.</h2></div><Compass className="hidden h-7 w-7 text-slate-600 sm:block" /></div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">{tools.map(({ icon: Icon, title, text, href, label }, index) => <article key={title} className="glass-panel flex flex-col p-5"><div className="mb-6 flex items-center justify-between"><Icon className="h-5 w-5 text-cyan-400" /><span className="font-mono text-[11px] text-slate-600">0{index + 1}</span></div><h3 className="text-sm font-semibold text-slate-100">{title}</h3><p className="mb-6 mt-3 flex-1 text-xs leading-6 text-slate-400">{text}</p><Link href={href} className="inline-flex items-center gap-2 text-xs text-cyan-300 hover:text-cyan-100">{label} <ArrowRight className="h-3.5 w-3.5" /></Link></article>)}</div>
        <p className="mt-4 text-xs leading-6 text-slate-500">Interested in wavelength measurements? <Link href="/spectral-explorer" className="text-cyan-300 hover:text-cyan-100">Spectral Explorer</Link> presents available cataloged spectrophotometry and identifies when a selected target lacks extracted spectral measurements.</p>
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <div className="glass-panel p-6 sm:p-8"><ShieldCheck className="mb-4 h-6 w-6 text-emerald-400" /><h2 className="text-xl font-medium text-slate-100">Scientific integrity comes first.</h2><p className="mt-3 text-sm leading-7 text-slate-400">A compelling image is a starting point. Every interpretation depends on the quality, geometry, and provenance of its observations.</p><ul className="mt-5 space-y-4">{[
          ["Real observations", "FITS products come from NASA/IPAC IRSA. Missing observations are never replaced by synthetic science images."],
          ["Visible limitations", "Nonfinite pixels and verified saturation flags are distinct. Invalid stellar cores are not reconstructed or used as reliable photometry."],
          ["Evidence before conclusions", "Comparison validity depends on compatible bands, celestial overlap, quality masks, and measured variance. A residual is not a confirmed discovery."],
        ].map(([title, text]) => <li key={title} className="border-t border-slate-800 pt-4"><h3 className="text-xs font-semibold text-slate-200">{title}</h3><p className="mt-1.5 text-xs leading-6 text-slate-400">{text}</p></li>)}</ul></div>
        <div className="space-y-5">
          <div className="glass-panel p-6 sm:p-8"><Database className="mb-4 h-6 w-6 text-cyan-400" /><h2 className="text-xl font-medium text-slate-100">A focused collection, openly sourced.</h2><p className="mt-3 text-sm leading-7 text-slate-400">Explore M101, M51, M33, NGC 253, Mira, Delta Cephei, and Algol. Each target retains its own observation records and quality limitations; a target&apos;s presence in the catalog does not guarantee every analysis is suitable.</p><p className="mt-3 text-xs leading-6 text-slate-500">The application is not a complete archive search or an all-sky coverage assessment. It does not establish a Planet Nine discovery or a moving-object detection.</p></div>
          <div className="rounded-2xl border border-violet-400/15 bg-violet-400/5 p-6 sm:p-8"><Sparkles className="mb-4 h-6 w-6 text-violet-300" /><h2 className="text-xl font-medium text-slate-100">AI to help you ask, evidence to help you decide.</h2><p className="mt-3 text-sm leading-7 text-slate-400">The Research Assistant uses Gemini with available target and observation context. Its explanations can clarify concepts and limitations, but they are not scientific measurements or a substitute for source verification. Live literature retrieval is not part of this assistant.</p></div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/30 p-6 sm:p-8">
        <div className="flex items-center gap-3"><BookOpen className="h-5 w-5 text-cyan-400" /><h2 className="text-lg font-medium text-slate-100">Explore the original sources</h2></div>
        <div className="mt-5 grid gap-3 sm:grid-cols-3">{[
          ["NASA SPHEREx", "Mission purpose and official updates", "https://science.nasa.gov/mission/spherex/"],
          ["NASA/JPL science", "The mission’s three science themes", "https://www.jpl.nasa.gov/press-kits/spherex/mission-overview/science/"],
          ["IPAC IRSA archive", "Public SPHEREx data and documentation", "https://irsa.ipac.caltech.edu/Missions/spherex.html"],
        ].map(([title, detail, href]) => <a key={title} href={href} target="_blank" rel="noopener noreferrer" className="flex items-center justify-between gap-3 rounded-xl border border-slate-800 p-4 transition hover:border-cyan-400/40"><span><span className="block text-sm text-slate-200">{title}</span><span className="mt-1 block text-[11px] text-slate-500">{detail}</span></span><ArrowUpRight className="h-4 w-4 shrink-0 text-slate-500" /></a>)}</div>
        <p className="mt-6 border-t border-slate-800 pt-5 text-[11px] leading-6 text-slate-500">SPHEREx Explorer is an independent educational project prepared for NASA Space Apps. Use of public NASA data does not imply NASA, JPL, or Caltech endorsement. Mission science and data products are credited to their original providers.</p>
      </section>
    </main>
    <Footer />
  </div>;
}
