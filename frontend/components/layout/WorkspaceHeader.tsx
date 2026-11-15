import type { ReactNode } from "react";
import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

export function WorkspaceHeader({ section, title, description, action }: { section: string; title: string; description: string; action?: ReactNode }) {
  return <header className="flex flex-wrap items-end justify-between gap-5 pb-1">
    <div className="max-w-2xl"><p className="mb-2 text-[10px] font-semibold uppercase tracking-[.25em] text-cyan-400">SPHEREx / {section}</p><h1 className="text-3xl font-semibold tracking-tight text-slate-100 sm:text-4xl">{title}</h1><p className="mt-3 text-sm leading-7 text-slate-400">{description}</p></div>
    {action && <div className="flex flex-wrap items-center gap-3">{action}</div>}
  </header>;
}

export function WorkspaceLink({ href, children }: { href: string; children: ReactNode }) {
  return <Link href={href} className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/50 px-4 py-2.5 text-xs text-slate-300 transition hover:border-cyan-400/40 hover:text-cyan-200">{children}<ArrowUpRight className="h-3.5 w-3.5" /></Link>;
}

export function WorkspaceMetric({ label, value, detail }: { label: string; value: ReactNode; detail?: string }) {
  return <div className="rounded-xl border border-slate-800 bg-slate-900/30 px-5 py-4"><p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">{label}</p><p className="mt-2 break-words text-xl font-medium tracking-tight text-slate-100">{value}</p>{detail && <p className="mt-1.5 text-[11px] leading-5 text-slate-500">{detail}</p>}</div>;
}
