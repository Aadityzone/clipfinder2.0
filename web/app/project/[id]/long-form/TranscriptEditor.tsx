"use client";

import { useEffect, useMemo, useState } from "react";

type Segment = { id: string; startS: number; endS: number; text: string };
type SaveState = "idle" | "saving" | "saved" | "error";
const stamp = (seconds: number) => {
  const s = Math.max(0, Number(seconds) || 0);
  return `${Math.floor(s / 60).toString().padStart(2, "0")}:${Math.floor(s % 60).toString().padStart(2, "0")}`;
};

export default function TranscriptEditor({ projectId }: { projectId: string }) {
  const [transcriptId, setTranscriptId] = useState("");
  const [rows, setRows] = useState<Segment[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [states, setStates] = useState<Record<string, SaveState>>({});
  const [query, setQuery] = useState("");
  const [loadError, setLoadError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/projects/${projectId}/transcript`).then(async response => {
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.error ?? "Could not load the transcript.");
      if (!cancelled) {
        setTranscriptId(data?.id ?? "");
        setRows(Array.isArray(data?.segments) ? data.segments : []);
      }
    }).catch(error => { if (!cancelled) setLoadError(error instanceof Error ? error.message : "Transcript failed to load."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [projectId]);

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase();
    return rows.map((row, index) => ({ ...row, index })).filter(row => !term || row.text.toLowerCase().includes(term));
  }, [rows, query]);

  async function save(segment: Segment) {
    if (!transcriptId) { setStates(s => ({ ...s, [segment.id]: "error" })); return; }
    setBusyId(segment.id);
    setStates(s => ({ ...s, [segment.id]: "saving" }));
    try {
      const response = await fetch(`/api/transcripts/${transcriptId}/segments/${segment.id}`, {
        method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify({ text: segment.text }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error ?? "Save failed");
      setStates(s => ({ ...s, [segment.id]: "saved" }));
    } catch {
      setStates(s => ({ ...s, [segment.id]: "error" }));
    } finally { setBusyId(null); }
  }

  return <section className="overflow-hidden rounded-2xl border border-white/[.08] bg-[#10141a]">
    <header className="border-b border-white/[.07] p-4 sm:p-5"><div className="flex items-center justify-between gap-3"><div><div className="text-sm font-semibold">Transcript editor</div><div className="mt-1 text-[10px] text-zinc-500">Edit a segment and save it when you leave the field.</div></div><span className="rounded-lg border border-white/[.07] px-2 py-1 font-mono text-[10px] text-zinc-500">{rows.length} lines</span></div><label className="mt-4 flex items-center gap-2 rounded-xl border border-white/[.08] bg-black/20 px-3"><span className="text-zinc-600">⌕</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Find a phrase in transcript…" className="h-10 min-w-0 flex-1 bg-transparent text-xs outline-none placeholder:text-zinc-600"/>{query && <button type="button" onClick={() => setQuery("")} className="text-xs text-zinc-500 hover:text-white">Clear</button>}</label></header>
    {loadError && <div role="alert" className="m-4 rounded-xl border border-red-300/20 bg-red-300/[.05] p-3 text-xs text-red-200">{loadError}</div>}
    <div className="max-h-[680px] overflow-y-auto">
      {loading ? <div className="p-8 text-center text-xs text-zinc-500">Loading transcript…</div> : !rows.length ? <div className="p-8 text-center"><div className="text-sm font-medium">Transcript not available yet</div><p className="mt-2 text-xs leading-5 text-zinc-600">When transcription completes, editable timestamped lines will appear here.</p></div> : !visible.length ? <div className="p-8 text-center text-xs text-zinc-500">No lines match “{query}”.</div> : visible.map(segment => <article key={segment.id} className="border-b border-white/[.05] px-4 py-4 last:border-0 hover:bg-white/[.012] sm:px-5"><div className="mb-2 flex items-center justify-between gap-3"><div className="flex items-center gap-2"><span className="font-mono text-[10px] text-[#c4f36b]">{stamp(segment.startS)}</span><span className="text-[9px] text-zinc-700">→</span><span className="font-mono text-[10px] text-zinc-600">{stamp(segment.endS)}</span></div><span className={`text-[9px] ${states[segment.id] === "error" ? "text-red-300" : states[segment.id] === "saved" ? "text-emerald-300" : "text-zinc-600"}`}>{states[segment.id] === "saving" || busyId === segment.id ? "Saving…" : states[segment.id] === "saved" ? "Saved" : states[segment.id] === "error" ? "Save failed · blur to retry" : `LINE ${String(segment.index + 1).padStart(3, "0")}`}</span></div><textarea aria-label={`Transcript line ${segment.index + 1}`} value={segment.text} onChange={event => { const text = event.target.value; setRows(current => current.map(row => row.id === segment.id ? { ...row, text } : row)); setStates(current => ({ ...current, [segment.id]: "idle" })); }} onBlur={() => { const current = rows.find(row => row.id === segment.id); if (current && current.text !== segment.text) void save(current); }} className="min-h-[64px] w-full resize-y rounded-lg border border-transparent bg-black/15 p-3 text-xs leading-6 text-zinc-300 outline-none transition focus:border-[#c4f36b]/20 focus:bg-black/25"/><div className="mt-2 text-right"><button type="button" onClick={() => void save(segment)} disabled={busyId === segment.id || states[segment.id] === "saved"} className="text-[10px] font-semibold text-zinc-500 transition hover:text-[#c4f36b] disabled:opacity-40">{busyId === segment.id ? "Saving…" : states[segment.id] === "saved" ? "✓ Saved" : "Save line ↗"}</button></div></article>)}
    </div>
    <footer className="border-t border-white/[.07] px-4 py-3 text-[10px] text-zinc-600">Changes update the saved transcript through the authenticated API.</footer>
  </section>;
}
