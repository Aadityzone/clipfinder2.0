"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import WorkspaceFrame from "../../components/WorkspaceFrame";

type TranscriptMatch = { id: string; startS: number; endS: number; text: string; transcript?: { mediaAsset?: { source?: { name?: string | null } | null } | null } | null };
type ClipMatch = { id: string; projectId: string; startS: number; endS: number; score: number | null; category: string | null; title: string | null };
type SearchResult = { segments?: TranscriptMatch[]; clips?: ClipMatch[]; error?: string };
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
  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || query.trim().length < 2) return;
    setBusy(true); setError(""); setResult(null);
    try {
      const response = await fetch("/api/search?q=" + encodeURIComponent(query.trim()));
      const data = await safeJson(response);
      if (!response.ok) { setError(data.error ?? "Search failed. Please try again."); return; }
      setResult(data);
    } catch { setError("Couldn't reach Clip Finder. Check your connection and try again."); }
    finally { setBusy(false); }
  }
  return <WorkspaceFrame active="/search" eyebrow="Find across your source" title="Search library" description="Search indexed transcript segments and real analyzed clips.">
    <form onSubmit={search} className="flex flex-col gap-3 rounded-2xl border border-white/[.08] bg-[#10141a] p-3 sm:flex-row sm:items-center"><label className="sr-only" htmlFor="search-query">Search transcript and clips</label><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-white/[.06] bg-white/[.025] text-xl text-[#c4f36b]">⌕</span><input id="search-query" value={query} onChange={event => setQuery(event.target.value)} minLength={2} maxLength={200} placeholder="Try: biggest win, unexpected reaction, funny moment…" className="cf-input min-w-0 flex-1 border-transparent bg-transparent focus:border-white/10 focus:shadow-none"/><button disabled={busy || query.trim().length < 2} className="cf-button !min-h-11">{busy ? "Searching…" : "Search content"} <span aria-hidden="true">↗</span></button></form>
    {error && <p role="alert" className="mt-4 rounded-xl border border-red-400/20 bg-red-400/[.08] p-3 text-sm text-red-300">{error}</p>}
    {!result && !error && <div className="mt-5 grid gap-3 md:grid-cols-3">{[{key:"TRANSCRIPT",title:"Search what was said",body:"Find words and phrases across completed transcripts."},{key:"MOMENTS",title:"Find a specific moment",body:"Look up a reaction, win, fail, or story beat."},{key:"CLIPS",title:"Return to a clip",body:"Jump from a real match back to its project editor."}].map((item,index)=><div key={item.key} className="rounded-xl border border-white/[.07] bg-white/[.015] p-4"><div className="font-mono text-[9px] tracking-[.16em] text-[#c4f36b]">0{index+1} / {item.key}</div><div className="mt-3 text-xs font-semibold">{item.title}</div><p className="mt-2 text-[11px] leading-5 text-zinc-500">{item.body}</p></div>)}</div>}
    {result && <div className="mt-7"><div className="mb-4 flex flex-wrap items-center justify-between gap-2"><div><h2 className="text-sm font-semibold">Results for “{query.trim()}”</h2><p className="mt-1 text-xs text-zinc-600">Matches returned by your saved transcript and clip records.</p></div><button type="button" onClick={() => { setResult(null); setQuery(""); }} className="text-xs text-zinc-500 hover:text-white">Clear results ×</button></div><div className="grid gap-5 xl:grid-cols-2"><section><div className="flex items-center justify-between"><h3 className="text-xs font-semibold uppercase tracking-[.12em] text-zinc-400">Transcript matches</h3><span className="text-[10px] text-zinc-600">{result.segments?.length ?? 0} results</span></div>{!result.segments?.length ? <div className="mt-3 rounded-xl border border-dashed border-white/[.1] p-6 text-xs text-zinc-500">No transcript matches. Try another phrase or wait for transcription to complete.</div> : result.segments.map(segment => <article key={segment.id} className="mt-3 rounded-xl border border-white/[.07] bg-[#10141a] p-4"><div className="font-mono text-[10px] text-[#c4f36b]">{Number(segment.startS).toFixed(1)}s → {Number(segment.endS).toFixed(1)}s</div><p className="mt-2 text-xs leading-6 text-zinc-300">{segment.text}</p><p className="mt-3 truncate text-[10px] text-zinc-600">{segment.transcript?.mediaAsset?.source?.name ?? "Source"}</p></article>)}</section><section><div className="flex items-center justify-between"><h3 className="text-xs font-semibold uppercase tracking-[.12em] text-zinc-400">Clip matches</h3><span className="text-[10px] text-zinc-600">{result.clips?.length ?? 0} results</span></div>{!result.clips?.length ? <div className="mt-3 rounded-xl border border-dashed border-white/[.1] p-6 text-xs text-zinc-500">No matching clips found.</div> : result.clips.map(clip => <Link key={clip.id} href={`/project/${clip.projectId}`} className="mt-3 block rounded-xl border border-white/[.07] bg-[#10141a] p-4 transition hover:border-[#c4f36b]/25"><div className="flex items-center justify-between gap-3"><span className="truncate text-sm font-medium">{clip.title ?? clip.category ?? "Clip candidate"}</span><span className="font-mono text-sm text-[#c4f36b]">{clip.score?.toFixed(0) ?? "—"}</span></div><div className="mt-2 text-[10px] text-zinc-500">{Number(clip.startS).toFixed(1)}s → {Number(clip.endS).toFixed(1)}s</div><div className="mt-3 text-[10px] text-zinc-600">Open project editor →</div></Link>)}</section></div></div>}
  </WorkspaceFrame>;
}
