"use client";

import { useState } from "react";
import Link from "next/link";

type SearchResult = { segments?: any[]; clips?: any[]; error?: string };
async function safeJson(response: Response): Promise<SearchResult> {
  const type = response.headers.get("content-type") ?? "";
  if (!type.includes("application/json")) return { error: "The server returned an unexpected response." };
  try { return await response.json() as SearchResult; } catch { return { error: "The server returned an invalid response." }; }
}
export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function search(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy || query.trim().length < 2) return;
    setBusy(true); setError(""); setResult(null);
    try { const response = await fetch("/api/search?q=" + encodeURIComponent(query.trim())); const data = await safeJson(response); if (!response.ok) { setError(data.error ?? "Search failed. Please try again."); return; } setResult(data); }
    catch { setError("Couldn't reach Clip Finder. Check your connection and try again."); }
    finally { setBusy(false); }
  }
  return <main className="min-h-screen bg-[#080a0d] px-5 pb-12 text-white sm:px-8"><header className="mx-auto flex max-w-6xl items-center justify-between border-b border-white/[.07] py-5"><Link href="/dashboard" className="text-sm text-zinc-400 hover:text-white">← Workspace</Link><Link href="/" className="font-semibold">clip<span className="text-[#c4f36b]">finder</span></Link></header><div className="mx-auto max-w-6xl pt-10"><p className="cf-kicker">Find across your source</p><h1 className="mt-3 text-4xl font-semibold tracking-tight">Search your content<span className="text-[#c4f36b]">.</span></h1><p className="mt-2 text-sm text-zinc-500">Search indexed transcript segments and real analyzed clips.</p><form onSubmit={search} className="cf-card mt-7 flex flex-col gap-3 p-3 sm:flex-row"><label className="sr-only" htmlFor="search-query">Search transcript and clips</label><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-white/[.035] text-xl text-zinc-500">⌕</span><input id="search-query" value={query} onChange={e=>setQuery(e.target.value)} minLength={2} maxLength={200} placeholder="Try: biggest win, unexpected reaction, funny moment…" className="cf-input min-w-0 flex-1 border-transparent bg-transparent focus:border-white/10 focus:shadow-none"/><button disabled={busy||query.trim().length<2} className="cf-button !min-h-11">{busy?"Searching…":"Search content"} <span aria-hidden="true">↗</span></button></form>{error&&<p role="alert" className="mt-4 rounded-xl border border-red-400/20 bg-red-400/[.08] p-3 text-sm text-red-300">{error}</p>}{result&&<div className="mt-9 grid gap-5 lg:grid-cols-2"><section><div className="flex items-center justify-between"><h2 className="font-semibold">Transcript matches</h2><span className="text-xs text-zinc-600">{result.segments?.length??0} results</span></div>{!result.segments?.length?<div className="cf-card mt-3 p-6 text-sm text-zinc-500">No transcript matches. Try another phrase or wait for transcription to complete.</div>:result.segments.map((s:any)=><div key={s.id} className="cf-card mt-3 p-4"><div className="font-mono text-xs text-[#c4f36b]">{Number(s.startS).toFixed(1)}s → {Number(s.endS).toFixed(1)}s</div><p className="mt-2 text-sm leading-6 text-zinc-300">{s.text}</p><p className="mt-3 truncate text-[11px] text-zinc-600">{s.transcript?.mediaAsset?.source?.name??"Source"}</p></div>)}</section><section><div className="flex items-center justify-between"><h2 className="font-semibold">Clip matches</h2><span className="text-xs text-zinc-600">{result.clips?.length??0} results</span></div>{!result.clips?.length?<div className="cf-card mt-3 p-6 text-sm text-zinc-500">No matching clips found.</div>:result.clips.map((c:any)=><Link key={c.id} href={"/project/"+c.projectId} className="cf-card mt-3 block p-4 transition hover:border-white/20"><div className="flex items-center justify-between gap-3"><span className="text-sm font-medium">{c.title??c.category??"Clip candidate"}</span><span className="font-mono text-sm text-[#c4f36b]">{c.score?.toFixed(0)??"—"}</span></div><div className="mt-2 text-xs text-zinc-500">{Number(c.startS).toFixed(1)}s → {Number(c.endS).toFixed(1)}s</div><div className="mt-3 text-xs text-zinc-600">Open project editor →</div></Link>)}</section></div>}</div></main>;
}
