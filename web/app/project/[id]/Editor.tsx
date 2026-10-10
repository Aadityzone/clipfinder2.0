"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent } from "react";

type Segment = { startS: number; endS: number };
type Clip = {
  id: string;
  startS: number;
  endS: number;
  score: number | null;
  category: string | null;
  title: string | null;
  status: string;
  edit?: { aspectRatio: string; segments: Segment[]; version: number } | null;
};

const clock = (seconds: number, tenths = false) => {
  const safe = Math.max(0, Number.isFinite(seconds) ? seconds : 0);
  const mm = Math.floor(safe / 60).toString().padStart(2, "0");
  const ss = Math.floor(safe % 60).toString().padStart(2, "0");
  return tenths ? `${mm}:${ss}.${Math.floor((safe % 1) * 10)}` : `${mm}:${ss}`;
};
const button = "inline-flex min-h-9 items-center justify-center gap-2 rounded-lg border border-white/[.09] bg-white/[.025] px-3 text-xs font-medium text-zinc-300 transition hover:border-white/20 hover:bg-white/[.07] disabled:cursor-not-allowed disabled:opacity-30";
const panelLabel = "text-[10px] font-semibold uppercase tracking-[.16em] text-zinc-500";

export default function Editor({ projectId, mediaId, duration, clips }: {
  projectId: string; mediaId: string | null; duration: number; clips: Clip[];
}) {
  const video = useRef<HTMLVideoElement>(null);
  const timeline = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<Clip | null>(clips[0] ?? null);
  const [segments, setSegments] = useState<Segment[]>(clips[0]?.edit?.segments ?? (clips[0] ? [{ startS: clips[0].startS, endS: clips[0].endS }] : []));
  const [selectedSegment, setSelectedSegment] = useState(0);
  const [aspect, setAspect] = useState(initialAspect);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [saving, setSaving] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [renderId, setRenderId] = useState<string | null>(null);
  const [renderStatus, setRenderStatus] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState<Segment[][]>([]);
  const [future, setFuture] = useState<Segment[][]>([]);
  const [waveform, setWaveform] = useState<number[]>([]);
  const [captionStyle, setCaptionStyle] = useState({ font: "Arial", size: 48, color: "&H00FFFFFF" });
  const [showShortcuts, setShowShortcuts] = useState(false);\n  const [favorites, setFavorites] = useState<string[]>(favoriteIds);\n  const [favoriteBusy, setFavoriteBusy] = useState(false);
  const selectedId = selected?.id;
  const current = segments[selectedSegment];
  const clipDuration = useMemo(() => segments.reduce((sum, segment) => sum + segment.endS - segment.startS, 0), [segments]);
  const pct = useCallback((value: number) => duration > 0 ? Math.min(100, Math.max(0, value / duration * 100)) : 0, [duration]);

  const selectClip = (clip: Clip) => {
    setSelected(clip);
    setSegments(clip.edit?.segments ?? [{ startS: clip.startS, endS: clip.endS }]);
    setSelectedSegment(0);
    setAspect(clip.edit?.aspectRatio ?? "9:16");
    setHistory([]); setFuture([]); setMessage(""); setRenderId(null); setRenderStatus(null);
  };

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    fetch(`/api/clips/${selectedId}/captions?format=json`).then(r => r.ok ? r.json() : null).then(d => {
      if (!cancelled && d?.style) setCaptionStyle(x => ({ ...x, ...d.style }));
    }).catch(() => {});
    fetch(`/api/clips/${selectedId}/render`).then(r => r.ok ? r.json() : null).then(d => {
      if (!cancelled && d?.render) { setRenderId(d.render.id); setRenderStatus(d.render.status); }
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [selectedId]);

  useEffect(() => {
    if (!mediaId) return;
    let cancelled = false;
    fetch(`/api/media/${mediaId}/waveform`).then(r => r.ok ? r.json() : null).then(d => {
      if (!cancelled) setWaveform(Array.isArray(d?.samples) ? d.samples : []);
    }).catch(() => setWaveform([]));
    return () => { cancelled = true; };
  }, [mediaId]);

  useEffect(() => {
    const element = video.current;
    if (!element) return;
    const update = () => {
      const next = element.currentTime;
      setTime(next);
      const index = segments.findIndex(s => next >= s.startS && next <= s.endS);
      if (index >= 0) setSelectedSegment(index);
    };
    element.addEventListener("timeupdate", update);
    return () => element.removeEventListener("timeupdate", update);
  }, [segments]);

  const seek = useCallback((target: number) => {
    const next = Math.max(0, Math.min(duration || target, target));
    if (video.current) video.current.currentTime = next;
    setTime(next);
  }, [duration]);

  const push = (next: Segment[]) => {
    setHistory(h => [...h.slice(-49), segments]);
    setFuture([]);
    setSegments(next);
  };
  const trimIn = useCallback(() => {
    if (!current) return;
    push(segments.map((s, i) => i === selectedSegment ? { ...s, startS: Math.max(s.startS, Math.min(time, s.endS - .1)) } : s));
  }, [current, segments, selectedSegment, time]);
  const trimOut = useCallback(() => {
    if (!current) return;
    push(segments.map((s, i) => i === selectedSegment ? { ...s, endS: Math.min(s.endS, Math.max(time, s.startS + .1)) } : s));
  }, [current, segments, selectedSegment, time]);
  const split = useCallback(() => {
    if (!current) return;
    const cut = Math.max(current.startS + .1, Math.min(current.endS - .1, time));
    if (cut <= current.startS || cut >= current.endS) { setMessage("Move the playhead inside the selected segment to split it."); return; }
    push([...segments.slice(0, selectedSegment), { startS: current.startS, endS: cut }, { startS: cut, endS: current.endS }, ...segments.slice(selectedSegment + 1)]);
    setSelectedSegment(selectedSegment + 1);
    setMessage("Segment split.");
  }, [current, segments, selectedSegment, time]);
  const removeSegment = useCallback(() => {
    if (segments.length <= 1) return;
    push(segments.filter((_, i) => i !== selectedSegment));
    setSelectedSegment(Math.min(selectedSegment, segments.length - 2));
  }, [segments, selectedSegment]);
  const undo = useCallback(() => {
    const previous = history.at(-1);
    if (!previous) return;
    setFuture(f => [segments, ...f]); setSegments(previous);
    setSelectedSegment(i => Math.min(i, previous.length - 1)); setHistory(h => h.slice(0, -1));
  }, [history, segments]);
  const redo = useCallback(() => {
    const next = future[0];
    if (!next) return;
    setHistory(h => [...h, segments]); setSegments(next);
    setSelectedSegment(i => Math.min(i, next.length - 1)); setFuture(f => f.slice(1));
  }, [future, segments]);

  const save = useCallback(async () => {
    if (!selectedId || !segments.length) return false;
    setSaving(true);
    try {
      const response = await fetch(`/api/clips/${selectedId}/edit`, {
        method: "PUT", headers: { "content-type": "application/json" },
        body: JSON.stringify({ startS: segments[0].startS, endS: segments[segments.length - 1].endS, segments, aspectRatio: aspect }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error ?? "Could not save your edit.");
      setSelected(c => c?.id === selectedId ? { ...c, startS: segments[0].startS, endS: segments[segments.length - 1].endS, edit: data } : c);
      setMessage("All edits saved");
      return true;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Save failed");
      return false;
    } finally { setSaving(false); }
  }, [selectedId, segments, aspect]);

  useEffect(() => {
    if (!selectedId || !segments.length) return;
    const timer = setTimeout(() => { void save(); }, 850);
    return () => clearTimeout(timer);
  }, [selectedId, segments, aspect, save]);

  useEffect(() => {
    if (!renderId || !selectedId || renderStatus === "READY" || renderStatus === "FAILED") return;
    const timer = setInterval(() => {
      fetch(`/api/clips/${selectedId}/render`).then(r => r.ok ? r.json() : null).then(d => {
        if (d?.render) { setRenderId(d.render.id); setRenderStatus(d.render.status); }
      }).catch(() => {});
    }, 2500);
    return () => clearInterval(timer);
  }, [renderId, renderStatus, selectedId]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (event.code === "Space") { event.preventDefault(); const v = video.current; if (v?.paused) void v.play(); else v?.pause(); }
      if (event.key.toLowerCase() === "i") trimIn();
      if (event.key.toLowerCase() === "o") trimOut();
      if (event.key.toLowerCase() === "s") split();
      if (event.key === "Delete" || event.key === "Backspace") removeSegment();
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") { event.preventDefault(); undo(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") { event.preventDefault(); redo(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [trimIn, trimOut, split, removeSegment, undo, redo]);

  const decide = async (decision: "accept" | "reject") => {
    if (!selectedId) return;
    try {
      const response = await fetch(`/api/clips/${selectedId}/decision`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ decision }) });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error ?? "Could not update clip.");
      setSelected(c => c?.id === selectedId ? { ...c, status: data.status } : c);
      setMessage(decision === "accept" ? "Clip approved" : "Clip rejected");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Decision failed"); }
  };

  const render = async () => {
    if (!selectedId) return;
    const saved = await save();
    if (!saved) return;
    setRendering(true); setMessage("");
    try {
      const response = await fetch(`/api/clips/${selectedId}/render`, { method: "POST" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error ?? "Could not queue render.");
      setRenderId(data.render.id); setRenderStatus(data.render.status); setMessage("Render queued. This panel updates as the worker progresses.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Render failed"); }
    finally { setRendering(false); }
  };

  const exportClip = async () => {
    if (!selectedId || renderStatus !== "READY") return;
    try {
      const response = await fetch(`/api/clips/${selectedId}/export`, { method: "POST" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error ?? "Export failed.");
      if (data.url) window.open(data.url, "_blank", "noopener,noreferrer");
      else setMessage("Export created, but the server did not return a download URL.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Export failed"); }
  };

  const toggleFavorite = async () => {\n    if (!selectedId || favoriteBusy) return;\n    setFavoriteBusy(true);\n    try {\n      const response = await fetch(`/api/clips/${selectedId}/favorite`, { method: "POST" });\n      const data = await response.json().catch(() => ({}));\n      if (!response.ok) throw new Error(data.error ?? "Could not update favorites.");\n      setFavorites(current => data.favorite ? [...new Set([...current, selectedId])] : current.filter(id => id !== selectedId));\n      setMessage(data.favorite ? "Added to favorites" : "Removed from favorites");\n    } catch (error) { setMessage(error instanceof Error ? error.message : "Favorite update failed"); }\n    finally { setFavoriteBusy(false); }\n  };\n\n  const clickTimeline = (event: MouseEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    seek(((event.clientX - rect.left) / Math.max(rect.width, 1)) * duration);
  };

  return <section className="overflow-hidden rounded-2xl border border-white/[.09] bg-[#0a0d12] text-white shadow-2xl shadow-black/20">
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[.08] bg-[#10151d] px-4 py-3">
      <div className="flex min-w-0 items-center gap-3">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[#c4f36b] text-sm font-black text-[#14190d]">CF</div>
        <div className="min-w-0"><div className="truncate text-sm font-semibold">{selected?.title || selected?.category || "Clip editor"}</div><div className="mt-0.5 text-[10px] text-zinc-500">CLIPFINDER STUDIO <span className="mx-1 text-zinc-700">/</span> {clock(clipDuration)} sequence</div></div>
      </div>
      <div className="flex items-center gap-2">
        <span className="hidden items-center gap-1.5 text-[10px] text-zinc-500 sm:inline-flex"><span className={`h-1.5 w-1.5 rounded-full ${saving ? "animate-pulse bg-amber-300" : "bg-emerald-300"}`}/>{saving ? "Saving" : "Autosaved"}</span>
        <button className={button} onClick={toggleFavorite} disabled={!selected || favoriteBusy}>{favorites.includes(selectedId ?? "") ? "♥ Favorited" : "♡ Favorite"}</button>\n        <button className={button} onClick={() => setShowShortcuts(v => !v)}>⌘ Shortcuts</button>
        <button className="inline-flex min-h-9 items-center gap-2 rounded-lg bg-[#c4f36b] px-3.5 text-xs font-bold text-[#14190d] transition hover:brightness-110 disabled:opacity-40" onClick={render} disabled={!selected || saving || rendering}>{rendering ? "Queueing…" : "↗ Render clip"}</button>
      </div>
    </header>

    {showShortcuts && <div className="grid grid-cols-2 gap-2 border-b border-white/[.08] bg-[#111720] p-4 text-[11px] sm:grid-cols-4">{[["Space","Play / pause"],["I","Trim selected segment in"],["O","Trim selected segment out"],["S","Split at playhead"],["⌘ Z","Undo"],["⌘ Y","Redo"],["Delete","Remove segment"],["Click timeline","Seek source"]].map(([key,label])=><div key={key} className="flex items-center gap-2"><kbd className="rounded-md border border-white/10 bg-black/20 px-2 py-1 font-mono text-zinc-300">{key}</kbd><span className="text-zinc-500">{label}</span></div>)}</div>}

    <div className="grid min-w-0 lg:grid-cols-[220px_minmax(0,1fr)_248px]">
      <aside className="border-b border-white/[.08] bg-[#0e1218] p-3 lg:border-b-0 lg:border-r">
        <div className="flex items-center justify-between px-1 pb-3"><span className={panelLabel}>Detected clips</span><span className="rounded-md bg-white/[.05] px-1.5 py-1 text-[10px] text-zinc-500">{clips.length}</span></div>
        <div className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible">
          {clips.map((clip, index) => <button key={clip.id} onClick={() => selectClip(clip)} className={`group min-w-[175px] flex-1 rounded-xl border p-3 text-left transition lg:min-w-0 ${selected?.id === clip.id ? "border-[#c4f36b]/45 bg-[#c4f36b]/[.07]" : "border-white/[.07] bg-white/[.015] hover:bg-white/[.04]"}`}>
            <div className="flex items-center justify-between gap-2"><span className="truncate text-xs font-semibold">{clip.title || clip.category || `Candidate ${index + 1}`}</span><span className="shrink-0 font-mono text-[10px] text-[#c4f36b]">{clip.score == null ? "—" : Math.round(clip.score)}</span></div>
            <div className="mt-3 flex items-center justify-between text-[10px] text-zinc-500"><span>{clock(clip.startS)} – {clock(clip.endS)}</span><span className="rounded bg-white/[.05] px-1.5 py-0.5">{clip.status.toLowerCase()}</span></div>
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/[.07]"><div className="h-full rounded-full bg-[#c4f36b]/80" style={{ width: `${Math.max(4, Math.min(100, clip.score ?? 4))}%` }}/></div>
          </button>)}
        </div>
        <div className="mt-4 hidden rounded-xl border border-white/[.07] p-3 lg:block"><div className={panelLabel}>Source</div><div className="mt-2 flex items-center gap-2"><span className="grid h-8 w-8 place-items-center rounded-lg bg-white/[.05] text-xs">▶</span><div className="min-w-0"><div className="truncate text-xs font-medium">Original media</div><div className="mt-1 text-[10px] text-zinc-600">{clock(duration)} total</div></div></div></div>
      </aside>

      <div className="min-w-0">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[.07] px-4 py-3">
          <div className="flex items-center gap-1.5"><span className="mr-2 text-[10px] uppercase tracking-[.15em] text-zinc-500">Preview</span><button className={button} onClick={() => seek(current?.startS ?? 0)} disabled={!current}>↤ Start</button><button className={button} onClick={() => seek(current?.endS ?? 0)} disabled={!current}>End ↦</button></div>
          <div className="flex items-center gap-2"><span className="font-mono text-xs tabular-nums text-zinc-300">{clock(time, true)}</span><span className="text-zinc-700">/</span><span className="font-mono text-xs text-zinc-500">{clock(duration)}</span></div>
        </div>
        <div className="relative flex min-h-[300px] items-center justify-center overflow-hidden bg-[radial-gradient(ellipse_at_center,_#202833_0%,_#0a0d12_66%)] p-5 sm:min-h-[390px]">
          <div className={`relative overflow-hidden rounded-xl border border-white/10 bg-black shadow-[0_24px_80px_rgba(0,0,0,.45)] ${aspect === "9:16" ? "aspect-[9/16] max-h-[420px] w-auto max-w-full" : aspect === "1:1" ? "aspect-square max-h-[420px] w-full max-w-[420px]" : "aspect-video w-full max-w-[720px]"}`}>
            {mediaId ? <video ref={video} src={`/api/media/${mediaId}`} className="h-full w-full object-contain" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onClick={() => video.current?.paused ? void video.current.play() : video.current?.pause()} playsInline /> : <div className="grid h-full place-items-center text-xs text-zinc-600">Source media is not attached yet.</div>}
            <button onClick={() => video.current?.paused ? void video.current.play() : video.current?.pause()} aria-label={playing ? "Pause preview" : "Play preview"} className="absolute bottom-3 left-3 grid h-10 w-10 place-items-center rounded-full border border-white/15 bg-black/65 text-sm backdrop-blur transition hover:bg-black/85">{playing ? "Ⅱ" : "▶"}</button>
            <div className="absolute right-3 top-3 rounded-md border border-white/10 bg-black/60 px-2 py-1 font-mono text-[10px] text-white/80">{aspect}</div>
            {selected && <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 to-transparent px-4 pb-4 pt-12"><div className="text-[9px] font-bold uppercase tracking-[.18em] text-[#c4f36b]">{selected.category || "AI highlight"}</div><div className="mt-1 line-clamp-2 text-sm font-semibold">{selected.title || "Untitled highlight"}</div></div>}
          </div>
        </div>

        <div className="border-t border-white/[.08] bg-[#0e1218] p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3"><div><div className="text-xs font-semibold">Timeline</div><div className="mt-1 text-[10px] text-zinc-600">Click the ruler to seek · select a segment to edit</div></div><div className="flex gap-1.5"><button className={button} onClick={undo} disabled={!history.length}>↶ Undo</button><button className={button} onClick={redo} disabled={!future.length}>↷ Redo</button></div></div>
          <div className="mb-1 flex justify-between px-0.5 font-mono text-[9px] text-zinc-600"><span>00:00</span><span>{clock(duration * .25)}</span><span>{clock(duration * .5)}</span><span>{clock(duration * .75)}</span><span>{clock(duration)}</span></div>
          <div ref={timeline} className="relative h-[92px] cursor-crosshair overflow-hidden rounded-lg border border-white/[.06] bg-[#090c10]" onClick={clickTimeline}>
            <div className="absolute inset-x-0 top-0 h-5 border-b border-white/[.05] bg-white/[.015]">{Array.from({ length: 21 }, (_, i) => <span key={i} className="absolute top-0 h-2 border-l border-white/10" style={{ left: `${i * 5}%` }}/>)}</div>
            <div className="absolute inset-x-2 top-7 h-8 overflow-hidden rounded-md bg-white/[.025]">
              {waveform.map((value, i) => <span key={i} className="absolute bottom-1/2 w-px bg-[#91a3b7]/55" style={{ left: `${i / Math.max(1, waveform.length - 1) * 100}%`, height: `${Math.max(5, Math.min(28, value * 28))}px`, transform: "translateY(50%)" }}/>)}
            </div>
            {segments.map((segment, index) => <button type="button" key={`${segment.startS}-${segment.endS}-${index}`} aria-label={`Select segment ${index + 1}`} onClick={event => { event.stopPropagation(); setSelectedSegment(index); seek(segment.startS); }} className={`absolute bottom-2 top-[62px] rounded border transition ${index === selectedSegment ? "border-[#c4f36b] bg-[#c4f36b]/25 shadow-[0_0_16px_rgba(196,243,107,.08)]" : "border-white/15 bg-white/[.08] hover:bg-white/[.14]"}`} style={{ left: `${pct(segment.startS)}%`, width: `${Math.max(.7, pct(segment.endS) - pct(segment.startS))}%` }}><span className="absolute left-1 top-0.5 truncate text-[8px] font-semibold text-white/80">{index + 1}</span></button>)}
            <div className="pointer-events-none absolute inset-y-0 z-10 w-px bg-[#f4f7fb]" style={{ left: `${pct(time)}%` }}><div className="-ml-[4px] h-2 w-2 rounded-sm bg-white"/></div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2"><button className={button} onClick={trimIn} disabled={!current}>⟪ Trim in <kbd className="text-[9px] text-zinc-600">I</kbd></button><button className={button} onClick={trimOut} disabled={!current}>Trim out ⟫ <kbd className="text-[9px] text-zinc-600">O</kbd></button><button className={button} onClick={split} disabled={!current}>✂ Split <kbd className="text-[9px] text-zinc-600">S</kbd></button><button className={button} onClick={removeSegment} disabled={segments.length <= 1}>− Remove segment</button><span className="ml-auto self-center font-mono text-[10px] text-zinc-600">{segments.length} segment{segments.length === 1 ? "" : "s"}</span></div>
        </div>
      </div>

      <aside className="border-t border-white/[.08] bg-[#0e1218] p-4 lg:border-l lg:border-t-0">
        <div className="mb-4 flex items-center justify-between"><span className={panelLabel}>Inspector</span><span className="text-[10px] text-zinc-600">EDIT PROPERTIES</span></div>
        <div className="rounded-xl border border-white/[.07] bg-black/10 p-3"><div className="text-xs font-semibold">Clip details</div><div className="mt-3 space-y-3">{[{label:"Start",value:clock(segments[0]?.startS ?? 0,true)},{label:"End",value:clock(segments.at(-1)?.endS ?? 0,true)},{label:"Duration",value:clock(clipDuration,true)},{label:"AI score",value:selected?.score == null ? "Not scored" : `${Math.round(selected.score)} / 100`}].map(item=><div key={item.label} className="flex items-center justify-between gap-2 text-xs"><span className="text-zinc-500">{item.label}</span><span className="font-mono text-zinc-200">{item.value}</span></div>)}</div></div>
        <div className="mt-3 rounded-xl border border-white/[.07] p-3"><div className="text-xs font-semibold">Canvas</div><div className="mt-3 grid grid-cols-3 gap-1.5">{["9:16","1:1","16:9"].map(value=><button key={value} onClick={() => setAspect(value)} aria-pressed={aspect === value} className={`rounded-lg border py-2.5 text-[10px] font-semibold transition ${aspect === value ? "border-[#c4f36b]/50 bg-[#c4f36b]/[.08] text-[#d7f9a7]" : "border-white/[.07] text-zinc-500 hover:bg-white/[.04]"}`}>{value}</button>)}</div><p className="mt-2 text-[10px] leading-4 text-zinc-600">The selected ratio is applied by the render pipeline.</p></div>
        <div className="mt-3 rounded-xl border border-white/[.07] p-3"><div className="flex items-center justify-between"><div className="text-xs font-semibold">Captions</div><span className="text-[10px] text-zinc-600">{captionStyle.font}</span></div><p className="mt-1.5 text-[10px] leading-4 text-zinc-600">Download the generated caption file for this cut.</p>{selected && <a href={`/api/clips/${selected.id}/captions`} className={`${button} mt-3 w-full`}>↓ Download SRT</a>}</div>
        <div className="mt-3 rounded-xl border border-white/[.07] p-3"><div className="text-xs font-semibold">Review decision</div><div className="mt-3 grid grid-cols-2 gap-2"><button onClick={() => void decide("accept")} className="min-h-9 rounded-lg border border-emerald-300/20 bg-emerald-300/[.05] text-[10px] font-semibold text-emerald-200 hover:bg-emerald-300/10">✓ Approve</button><button onClick={() => void decide("reject")} className="min-h-9 rounded-lg border border-red-300/15 bg-red-300/[.035] text-[10px] font-semibold text-red-200 hover:bg-red-300/10">× Reject</button></div><p className="mt-2 text-[10px] text-zinc-600">Current status: {selected?.status?.toLowerCase() ?? "no clip selected"}</p></div>
        <div className="mt-3 rounded-xl border border-white/[.07] p-3"><div className="flex items-center justify-between"><div className="text-xs font-semibold">Render queue</div><span className={`rounded-full px-2 py-1 text-[9px] ${renderStatus === "READY" ? "bg-emerald-300/10 text-emerald-200" : renderStatus === "FAILED" ? "bg-red-300/10 text-red-200" : "bg-white/[.05] text-zinc-400"}`}>{renderStatus?.toLowerCase() ?? "not queued"}</span></div><p className="mt-2 text-[10px] leading-4 text-zinc-600">{renderStatus === "READY" ? "Your render is ready to preview and export." : renderStatus === "FAILED" ? "The worker reported a render failure. Check job logs." : "Save the edit and queue a render when the cut is ready."}</p>{renderStatus === "READY" && renderId && <><video src={`/api/renders/${renderId}`} controls className="mt-3 w-full rounded-lg bg-black"/><button className="mt-2 w-full rounded-lg border border-[#c4f36b]/20 py-2.5 text-xs font-semibold text-[#d7f9a7] hover:bg-[#c4f36b]/[.06]" onClick={() => void exportClip()}>↓ Export MP4</button></>}</div>
        {message && <p role="status" aria-live="polite" className="mt-3 rounded-lg border border-white/[.07] bg-white/[.025] p-3 text-[10px] leading-4 text-zinc-300">{message}</p>}
        <button className={`${button} mt-3 w-full`} onClick={() => void save()} disabled={saving}>{saving ? "Saving edits…" : "✓ Save changes now"}</button>
      </aside>
    </div>
    <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-white/[.07] bg-[#0b0f14] px-4 py-2.5 text-[9px] text-zinc-600"><span>CLIPFINDER STUDIO · {projectId.slice(0, 8)}</span><span>Edits are saved to your project · Preview before publishing</span></footer>
  </section>;
}
