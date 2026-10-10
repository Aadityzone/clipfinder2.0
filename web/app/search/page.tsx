"use client";
import Link from "next/link";
import { useState } from "react";

type SegmentMatch = { id: string; startS: number; endS: number; text: string; transcript?: { mediaAsset?: { source?: { name?: string | null } } } };
type ClipMatch = { id: string; projectId: string; category: string | null; score: number | null; startS: number; endS: number };
type SearchResult = { segments?: SegmentMatch[]; clips?: ClipMatch[]; error?: string };
export default function SearchPage() {
  const [query,setQuery]=useState("");
  const [result,setResult]=useState<SearchResult|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  async function search(event:React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if(busy || query.trim().length<2) return;
    setBusy(true); setError(""); setResult(null);
    try {
      const response=await fetch("/api/search?q="+encodeURIComponent(query.trim()));
      const data=await response.json() as SearchResult;
      if(!response.ok) throw new Error(data.error || "Search failed. Please try again.");
      setResult(data);
    } catch(cause) { setError(cause instanceof Error?cause.message:"Couldn't search your content."); }
    finally { setBusy(false); }
  }
  return <main className="min-h-screen">
    <header className="border-b border-white/[.07]"><div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5 sm:px-8"><Link href="/dashboard" className="flex items-center gap-2 text-xs text-[#9ca6b4] hover:text-white"><span className="text-[#c4f56b]">←</span> Workspace</Link><span className="text-[10px] text-[#687383]">TRANSCRIPT & CLIP SEARCH</span></div></header>
    <section className="mx-auto max-w-6xl px-5 py-10 sm:px-8"><p className="cf-eyebrow">Search your source library</p><h1 className="mt-3 text-4xl font-semibold tracking-[-.06em]">Find that moment.</h1><p className="mt-3 max-w-xl text-sm leading-6 text-[#8792a1]">Search persisted transcript segments and analyzed clips. Results depend on what has actually been processed.</p>
      <form onSubmit={search} className="cf-panel mt-7 flex flex-col gap-3 rounded-2xl p-3 sm:flex-row"><label className="flex min-w-0 flex-1 items-center gap-3 px-3"><span className="text-xl text-[#c4f56b]">⌕</span><input aria-label="Search transcript and clips" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Try “quitting”, “biggest win”, or a quote…" className="min-w-0 flex-1 bg-transparent py-3 text-sm outline-none placeholder:text-[#687383]" /></label><button disabled={busy||query.trim().length<2} className="cf-button cf-button-primary disabled:cursor-not-allowed disabled:opacity-50">{busy?"Searching…":"Search content ↗"}</button></form>
      {error&&<p role="alert" className="mt-4 rounded-xl border border-rose-400/20 bg-rose-400/[.07] p-3 text-xs text-rose-300">{error}</p>}
      {!result&&!busy&&!error&&<div className="mt-6 rounded-2xl border border-dashed border-white/[.1] p-7 text-xs leading-6 text-[#687383]">Enter at least two characters to search real transcript and clip data.</div>}
      {busy&&<div aria-live="polite" className="mt-6 rounded-2xl border border-white/[.07] p-7 text-xs text-[#8792a1]">Searching analyzed content…</div>}
      {result&&<div className="mt-8 grid gap-6 lg:grid-cols-2"><section><div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-semibold">Transcript matches</h2><span className="text-[10px] text-[#687383]">{result.segments?.length??0} found</span></div>{!result.segments?.length?<p className="rounded-2xl border border-white/[.07] p-5 text-xs leading-6 text-[#687383]">No matching transcript segments. Check that your source has finished transcription.</p>:<div className="space-y-2">{result.segments.map(segment=><article key={segment.id} className="cf-panel rounded-xl p-4"><p className="font-mono text-[10px] text-[#c4f56b]">{segment.startS.toFixed(1)}s → {segment.endS.toFixed(1)}s</p><p className="mt-2 text-xs leading-6 text-[#d2d7df]">{segment.text}</p><p className="mt-3 truncate text-[9px] text-[#687383]">{segment.transcript?.mediaAsset?.source?.name??"Source media"}</p></article>)}</div>}</section><section><div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-semibold">Clip matches</h2><span className="text-[10px] text-[#687383]">{result.clips?.length??0} found</span></div>{!result.clips?.length?<p className="rounded-2xl border border-white/[.07] p-5 text-xs leading-6 text-[#687383]">No matching clips were found in analyzed projects.</p>:<div className="space-y-2">{result.clips.map(clip=><Link key={clip.id} href={"/project/"+clip.projectId} className="cf-panel block rounded-xl p-4 transition hover:border-[#c4f56b]/25"><div className="flex items-center justify-between"><span className="text-xs font-semibold">{clip.category??"AI Detect"}</span><span className="font-mono text-[10px] text-[#c4f56b]">Score {clip.score?.toFixed(0)??"—"}</span></div><p className="mt-3 text-[10px] text-[#8792a1]">{clip.startS.toFixed(1)}s → {clip.endS.toFixed(1)}s</p><p className="mt-3 text-[10px] text-[#c4f56b]">Open source project ↗</p></Link>)}</div>}</section></div>}
    </section>
  </main>;
}
