"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { askResearchAssistant, fetchTargets } from "@/lib/api";
import { TargetInfo } from "@/lib/types";
import { useSelectedTarget, selectTarget } from "@/lib/selected-target";
import { ArrowRight, ArrowUp, BookOpen, Check, Copy, LoaderCircle, MessageSquare, RotateCcw, ShieldCheck, Sparkles, Telescope, Trash2 } from "lucide-react";

type Exchange = { id: number; question: string; target: string; answer?: string; provider?: string; error?: string };

function AnswerText({ text }: { text: string }) {
  const inline = (line: string) => line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, index) =>
    part.startsWith('**') ? <strong key={index} className="font-semibold text-slate-100">{part.slice(2, -2)}</strong> :
    part.startsWith('`') ? <code key={index} className="rounded bg-slate-800 px-1 py-0.5 text-xs text-cyan-200">{part.slice(1, -1)}</code> : part);
  return <div className="space-y-3 break-words text-sm leading-7 text-slate-300">{text.split(/\n\s*\n/).map((block, index) => {
    const lines = block.split('\n');
    if (lines.every(line => /^\s*[-*]\s+/.test(line))) return <ul key={index} className="list-disc space-y-1 pl-5 marker:text-cyan-500">{lines.map((line, i) => <li key={i}>{inline(line.replace(/^\s*[-*]\s+/, ''))}</li>)}</ul>;
    if (lines.every(line => /^\s*\d+\.\s+/.test(line))) return <ol key={index} className="list-decimal space-y-1 pl-5 marker:text-cyan-500">{lines.map((line, i) => <li key={i}>{inline(line.replace(/^\s*\d+\.\s+/, ''))}</li>)}</ol>;
    return <div key={index} className="whitespace-pre-wrap">{lines.map((line, i) => /^#{1,6}\s/.test(line) ? <p key={i} className="font-semibold text-slate-100">{inline(line.replace(/^#{1,6}\s+/, ''))}</p> : <span key={i}>{i > 0 && '\n'}{inline(line)}</span>)}</div>;
  })}</div>;
}

export default function ResearchAssistantPage() {
  const [query, setQuery] = useState("");
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [loading, setLoading] = useState(false);
  const [targets, setTargets] = useState<TargetInfo[]>([]);
  const [catalogError, setCatalogError] = useState(false);
  const [copied, setCopied] = useState<number | null>(null);
  const pending = useRef(false);
  const input = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const target = useSelectedTarget();
  const currentTarget = targets.find(t => t.name === target);

  useEffect(() => { fetchTargets().then(setTargets).catch(() => setCatalogError(true)); }, []);
  useEffect(() => { if (exchanges.length) end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [exchanges, loading]);

  async function handleAsk(question = query, selectedTarget = target) {
    const text = question.trim();
    if (!text || text.length > 4000 || pending.current) return;
    pending.current = true;
    setLoading(true);
    setQuery("");
    const id = Date.now();
    setExchanges(previous => [...previous.slice(-19), { id, question: text, target: selectedTarget }]);
    try {
      const response = await askResearchAssistant(text, selectedTarget);
      setExchanges(previous => previous.map(item => item.id === id ? { ...item, answer: response.answer, provider: response.provider } : item));
    } catch (error) {
      setExchanges(previous => previous.map(item => item.id === id ? { ...item, error: error instanceof Error ? error.message : "The assistant could not answer. Please retry." } : item));
    } finally {
      pending.current = false;
      setLoading(false);
    }
  }

  async function copyAnswer(item: Exchange) {
    try {
      await navigator.clipboard.writeText(item.answer || "");
      setCopied(item.id);
      setTimeout(() => setCopied(null), 2000);
    } catch { setCopied(null); }
  }

  const suggestions = [
    { label: "Explore this target", text: `What genuine observations are available for ${target}?`, icon: Telescope },
    { label: "Understand the data", text: `How should I interpret invalid pixels and quality flags for ${target}?`, icon: ShieldCheck },
    { label: "Plan an investigation", text: `What evidence would I need for a reliable epoch comparison of ${target}?`, icon: BookOpen },
  ];

  return <div className="flex min-h-screen flex-col">
    <Navbar />
    <main className="mx-auto w-full max-w-7xl flex-1 space-y-7 p-4 lg:p-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[.25em] text-cyan-400">SPHEREx / Research workspace</p>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-100 sm:text-4xl">Ask the universe a better question.</h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-400">Explore the mission, understand your observations, and turn scientific questions into a clearer investigation.</p>
        </div>
      </header>

      <div className="grid items-start gap-5 lg:grid-cols-[270px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <section className="glass-panel space-y-4 p-5">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-300"><Telescope className="h-4 w-4 text-cyan-400" /> Observation context</div>
            <div>
              <label htmlFor="research-target" className="mb-2 block text-xs text-slate-400">Selected astronomical target</label>
              <select id="research-target" value={target} onChange={event => selectTarget(event.target.value)} className="w-full rounded-xl border border-slate-700 bg-slate-900 p-3 text-sm text-slate-100 outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
                {targets.length ? targets.map(item => <option key={item.id} value={item.name}>{item.name}</option>) : <option>{target}</option>}
              </select>
            </div>
            {currentTarget && <>
              <p className="text-xs leading-relaxed text-slate-400">{currentTarget.category}</p>
              <div className="grid grid-cols-2 gap-3 border-y border-slate-800 py-3">
                <div><p className="text-xl font-semibold text-slate-100">{currentTarget.observation_count}</p><p className="mt-1 text-[10px] text-slate-500">Cataloged products</p></div>
                <div><p className="text-xs font-mono text-cyan-200">{currentTarget.ra.toFixed(4)}°<br />{currentTarget.dec.toFixed(4)}°</p><p className="mt-1 text-[10px] text-slate-500">RA / Dec</p></div>
              </div>
              <p className="text-[10px] leading-relaxed tracking-wide text-amber-200/80">{currentTarget.exploration_status}</p>
            </>}
            {catalogError && <p role="status" className="text-xs text-amber-300">Target details could not be loaded. Questions will still use {target} as context.</p>}
            <Link href={`/sky-explorer?target=${encodeURIComponent(target)}`} className="flex items-center justify-between text-xs text-cyan-300 hover:text-cyan-100">Open observations <ArrowRight className="h-3.5 w-3.5" /></Link>
          </section>
          <section className="rounded-2xl border border-slate-800 bg-slate-900/30 p-5">
            <ShieldCheck className="mb-3 h-5 w-5 text-cyan-400" />
            <h2 className="text-sm font-medium text-slate-200">Explanation meets evidence</h2>
            <p className="mt-2 text-xs leading-6 text-slate-400">Answers use available target metadata and model knowledge. AI explanations are not measurements. Verify scientific claims against the FITS data and evidence dossier.</p>
            <p className="mt-3 text-[11px] leading-5 text-slate-500">No live literature search. Earlier answers stay visible here; each question is sent independently.</p>
            <Link href="/about" className="mt-4 inline-flex items-center gap-2 text-xs text-slate-300 hover:text-cyan-300">About our approach <ArrowRight className="h-3 w-3" /></Link>
          </section>
        </aside>

        <section aria-label="Research conversation" className="glass-panel flex min-h-[630px] min-w-0 flex-col overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b border-slate-800/80 px-5 py-4">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-200"><MessageSquare className="h-4 w-4 text-cyan-400" /> Research notebook <span className="hidden text-xs font-normal text-slate-500 sm:inline">/ this visit</span></div>
            <button onClick={() => { setExchanges([]); input.current?.focus(); }} disabled={loading || !exchanges.length} className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-slate-400 transition hover:bg-slate-800 hover:text-slate-200 disabled:opacity-30"><Trash2 className="h-3.5 w-3.5" /> Clear</button>
          </div>

          <div className="max-h-[650px] flex-1 overflow-y-auto p-5 sm:p-7">
            {!exchanges.length ? <div className="mx-auto flex h-full max-w-xl flex-col justify-center py-6 sm:py-10">
              <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl border border-cyan-400/20 bg-gradient-to-br from-cyan-500/15 to-violet-500/10"><Sparkles className="h-6 w-6 text-cyan-300" /></div>
              <h2 className="text-2xl font-medium tracking-tight text-slate-100">Where would you like to begin?</h2>
              <p className="mt-3 text-sm leading-6 text-slate-400">Ask about {target}, the data behind an image, or what a scientific result can tell you.</p>
              <div className="mt-7 space-y-3">{suggestions.map(({ label, text, icon: Icon }) => <button key={label} onClick={() => handleAsk(text)} className="group flex w-full items-start gap-3 rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-left transition hover:border-cyan-500/40 hover:bg-cyan-500/5 focus-visible:outline-2 focus-visible:outline-cyan-400"><Icon className="mt-0.5 h-4 w-4 shrink-0 text-cyan-400/80" /><span className="flex-1"><span className="block text-xs font-medium text-slate-200">{label}</span><span className="mt-1 block text-xs leading-5 text-slate-400">{text}</span></span><ArrowRight className="mt-0.5 h-4 w-4 text-slate-600 group-hover:text-cyan-400" /></button>)}</div>
            </div> : <div className="space-y-7">{exchanges.map(item => <article key={item.id} className="space-y-4">
              <div className="ml-auto max-w-[90%] rounded-2xl rounded-tr-sm border border-cyan-500/15 bg-cyan-500/10 px-4 py-3"><p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-cyan-400">You · {item.target}</p><p className="whitespace-pre-wrap break-words text-sm leading-6 text-slate-200">{item.question}</p></div>
              <div className="flex gap-3"><div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-violet-400/20 bg-violet-400/10"><Sparkles className="h-4 w-4 text-violet-300" /></div><div className="min-w-0 flex-1">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2"><span className="text-xs font-medium text-slate-300">Research Assistant</span>{item.provider === 'gemini' && <span className="text-[10px] text-violet-300">Powered by Gemini</span>}</div>
                {item.answer ? <><AnswerText text={item.answer} /><button onClick={() => copyAnswer(item)} className="mt-3 inline-flex items-center gap-1.5 text-[11px] text-slate-500 hover:text-cyan-300">{copied === item.id ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}{copied === item.id ? 'Copied' : 'Copy answer'}</button></> : item.error ? <div role="alert" className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4"><p className="text-sm leading-6 text-rose-200">{item.error}</p><button disabled={loading} onClick={() => handleAsk(item.question, item.target)} className="mt-3 inline-flex items-center gap-2 text-xs text-rose-300 disabled:opacity-40"><RotateCcw className="h-3 w-3" /> Retry question</button></div> : <div role="status" className="flex items-center gap-2 text-xs text-slate-400"><LoaderCircle className="h-4 w-4 animate-spin" /> Reviewing {item.target} context…</div>}
              </div></div>
            </article>)}<div ref={end} /></div>}
          </div>

          <form onSubmit={event => { event.preventDefault(); handleAsk(); }} className="border-t border-slate-800/80 bg-slate-950/30 p-4 sm:p-5">
            <label htmlFor="research-question" className="sr-only">Your research question</label>
            <div className="flex items-end gap-3 rounded-xl border border-slate-700 bg-slate-900/80 p-3 focus-within:border-cyan-400/60 focus-within:ring-1 focus-within:ring-cyan-400/20">
              <textarea ref={input} id="research-question" value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); handleAsk(); } }} rows={2} maxLength={4000} placeholder={`Ask about ${target} or SPHEREx science…`} className="max-h-40 min-h-12 flex-1 resize-y bg-transparent text-sm leading-6 text-slate-100 outline-none placeholder:text-slate-500" />
              <button type="submit" disabled={loading || !query.trim()} aria-label="Send question" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-cyan-400 text-slate-950 transition hover:bg-cyan-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-600">{loading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-5 w-5" />}</button>
            </div>
            <div className="mt-2 flex justify-between gap-3 text-[10px] text-slate-500"><span>Enter to send · Shift + Enter for a new line</span><span>{query.length.toLocaleString()} / 4,000</span></div>
          </form>
        </section>
      </div>
    </main>
    <Footer />
  </div>;
}
