"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";
import { clampSourceTime, mediaToSourceTime, snapSourceTimeToFrame, snapSourceTimeToMarkers, sourceToMediaTime } from "../../../lib/editor-timeline";

type Segment = { startS: number; endS: number };
type Clip = {
  id: string;
  startS: number;
  endS: number;
  score: number | null;
  category: string | null;
  title: string | null;
  status: string;
  highlight?: { startS: number; endS: number; rationale: string | null; features?: unknown } | null;
  edit?: { aspectRatio: string; segments: Segment[]; version: number } | null;
};

const clock = (seconds: number, tenths = false) => {
  const safe = Math.max(0, Number.isFinite(seconds) ? seconds : 0);
  const mm = Math.floor(safe / 60).toString().padStart(2, "0");
  const ss = Math.floor(safe % 60).toString().padStart(2, "0");
  return tenths ? `${mm}:${ss}.${Math.floor((safe % 1) * 1000).toString().padStart(3, "0")}` : `${mm}:${ss}`;
};
const button = "inline-flex min-h-9 items-center justify-center gap-2 rounded-lg border border-white/[.09] bg-white/[.025] px-3 text-xs font-medium text-zinc-300 transition hover:border-white/20 hover:bg-white/[.07] disabled:cursor-not-allowed disabled:opacity-30";
const panelLabel = "text-[10px] font-semibold uppercase tracking-[.16em] text-zinc-500";
const assColorToHex = (value: string) => {
  const bgr = value.match(/&H[0-9A-Fa-f]{2}([0-9A-Fa-f]{6})/i)?.[1];
  return bgr ? `#${bgr.slice(4, 6)}${bgr.slice(2, 4)}${bgr.slice(0, 2)}` : "#ffffff";
};
const hexToAssColor = (hex: string) => `&H00${hex.replace("#", "").match(/.{2}/g)?.reverse().join("") ?? "FFFFFF"}`;

export default function Editor({ projectId, mediaId, duration, fps = 30, mediaOffsetSeconds = 0, clips, favoriteIds = [] }: {
  projectId: string; mediaId: string | null; duration: number; fps?: number | null; mediaOffsetSeconds?: number; clips: Clip[]; favoriteIds?: string[];
}) {
  const video = useRef<HTMLVideoElement>(null);
  const timeline = useRef<HTMLDivElement>(null);
  const initialSegments = clips[0]?.edit?.segments ?? (clips[0] ? [{ startS: clips[0].highlight?.startS ?? clips[0].startS, endS: clips[0].highlight?.endS ?? clips[0].endS }] : []);
  const initialAspect = clips[0]?.edit?.aspectRatio ?? "9:16";
  const savedSignature = useRef(JSON.stringify({ id: clips[0]?.id ?? null, segments: initialSegments, aspectRatio: initialAspect }));
  const [selected, setSelected] = useState<Clip | null>(clips[0] ?? null);
  const [segments, setSegments] = useState<Segment[]>(initialSegments);
  const [selectedSegment, setSelectedSegment] = useState(0);
  const [aspect, setAspect] = useState(initialAspect);
  const [time, setTime] = useState(mediaOffsetSeconds);
  const [playing, setPlaying] = useState(false);
  const [saving, setSaving] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [renderId, setRenderId] = useState<string | null>(null);
  const [renderStatus, setRenderStatus] = useState<string | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState<Segment[][]>([]);
  const [future, setFuture] = useState<Segment[][]>([]);
  const [waveform, setWaveform] = useState<number[]>([]);
  const [captionStyle, setCaptionStyle] = useState({ font: "Arial", size: 48, color: "&H00FFFFFF" });
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [favorites, setFavorites] = useState<string[]>(favoriteIds);
  const [favoriteBusy, setFavoriteBusy] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [volume, setVolume] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [videoLoading, setVideoLoading] = useState(true);
  const [videoError, setVideoError] = useState("");
  const [fullscreen, setFullscreen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [captionCues, setCaptionCues] = useState<{ start: number; end: number; text: string }[]>([]);
  const [captionsVisible, setCaptionsVisible] = useState(true);
  const captionState = useRef({ cues: captionCues, style: captionStyle });
  const captionBounds = useRef({ clipId: clips[0]?.id ?? "", startS: clips[0]?.startS ?? 0, endS: clips[0]?.endS ?? 0 });
  useEffect(() => { captionState.current = { cues: captionCues, style: captionStyle }; }, [captionCues, captionStyle]);
  const dragRef = useRef<{ segment: number; edge: "start" | "end"; pointerId: number } | null>(null);
  const dragBefore = useRef<Segment[] | null>(null);
  const selectedId = selected?.id;
  const current = segments[selectedSegment];
  const sourceBounds = (clip: Clip) => ({
    startS: clip.highlight?.startS ?? clip.startS,
    endS: clip.highlight?.endS ?? clip.endS,
  });

  const clipDuration = useMemo(() => segments.reduce((sum, segment) => sum + segment.endS - segment.startS, 0), [segments]);
  const timelineEnd = mediaOffsetSeconds + duration;
  const pct = useCallback((value: number) => duration > 0 ? Math.min(100, Math.max(0, (value - mediaOffsetSeconds) / duration * 100)) : 0, [duration, mediaOffsetSeconds]);

  const selectClip = (clip: Clip) => {
    const bounds = sourceBounds(clip);
    const nextSegments = clip.edit?.segments ?? [bounds];
    const nextAspect = clip.edit?.aspectRatio ?? "9:16";
    savedSignature.current = JSON.stringify({ id: clip.id, segments: nextSegments, aspectRatio: nextAspect });
    setSelected(clip);
    setSegments(nextSegments);
    setSelectedSegment(0);
    setAspect(nextAspect);
    captionBounds.current = { clipId: clip.id, startS: clip.startS, endS: clip.endS };
    seek(nextSegments[0]?.startS ?? bounds.startS);
    setHistory([]); setFuture([]); setMessage(""); setRenderId(null); setRenderStatus(null); setRenderError(null);
    setCaptionCues([]); setCaptionsVisible(true); setVideoError(""); setVideoLoading(false);
  };

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    fetch(`/api/clips/${selectedId}/captions?format=json`).then(r => r.ok ? r.json() : null).then(d => {
      if (!cancelled && d) {
        if (d.style) setCaptionStyle(x => ({ ...x, ...d.style }));
        if (Array.isArray(d.cues)) setCaptionCues(d.cues.map((cue: any) => ({ start: Number(cue.startS ?? cue.start) + (selected?.startS ?? 0), end: Number(cue.endS ?? cue.end) + (selected?.startS ?? 0), text: String(cue.text ?? "") })).filter((cue: any) => Number.isFinite(cue.start) && Number.isFinite(cue.end) && cue.end > cue.start));
      }
    }).catch(() => {});
    fetch(`/api/clips/${selectedId}/render`).then(r => r.ok ? r.json() : null).then(d => {
      if (!cancelled && d?.render) { setRenderId(d.render.id); setRenderStatus(d.render.status); setRenderError(d.render.error ?? null); }
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [selectedId, selected?.startS]);

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
      const next = mediaToSourceTime(element.currentTime, mediaOffsetSeconds);
      const index = segments.findIndex(s => next >= s.startS && next <= s.endS);
      if (element.paused && index < 0) { setTime(next); return; }
      if (!element.paused && index < 0) {
        const nextSegmentIndex = segments.findIndex(s => s.startS > next);
        if (nextSegmentIndex >= 0) {
          element.currentTime = sourceToMediaTime(segments[nextSegmentIndex].startS, mediaOffsetSeconds);
          setTime(segments[nextSegmentIndex].startS);
          setSelectedSegment(nextSegmentIndex);
          return;
        }
        const lastSegment = segments.at(-1);
        if (lastSegment) {
          element.currentTime = sourceToMediaTime(lastSegment.endS, mediaOffsetSeconds);
          element.pause();
          setTime(lastSegment.endS);
          return;
        }
      }
      setTime(next);
      if (index >= 0) setSelectedSegment(index);
    };
    element.addEventListener("timeupdate", update);
    return () => element.removeEventListener("timeupdate", update);
  }, [segments, mediaOffsetSeconds]);

  const seek = useCallback((target: number) => {
    const next = clampSourceTime(target, mediaOffsetSeconds, duration);
    if (video.current) video.current.currentTime = sourceToMediaTime(next, mediaOffsetSeconds);
    setTime(next);
  }, [duration, mediaOffsetSeconds]);

  const stepFrame = (direction: -1 | 1) => {
    video.current?.pause();
    seek(time + direction / (fps && fps > 0 ? fps : 30));
  };
  const setRate = (value: number) => { setPlaybackRate(value); if (video.current) video.current.playbackRate = value; };
  const setPlayerVolume = (value: number) => { setVolume(value); if (video.current) video.current.volume = value; };
  const toggleFullscreen = async () => {
    const frame = video.current?.parentElement;
    if (!frame) return;
    try {
      if (!document.fullscreenElement) { await frame.requestFullscreen(); setFullscreen(true); }
      else { await document.exitFullscreen(); setFullscreen(false); }
    } catch { setMessage("Fullscreen is unavailable in this browser."); }
  };

  const push = (next: Segment[]) => {
    setHistory(h => [...h.slice(-49), segments]);
    setFuture([]);
    setSegments(next);
  };
  const trimIn = () => {
    if (!current) return;
    push(segments.map((s, i) => i === selectedSegment ? { ...s, startS: Math.max(s.startS, Math.min(time, s.endS - .1)) } : s));
  };
  const trimOut = () => {
    if (!current) return;
    push(segments.map((s, i) => i === selectedSegment ? { ...s, endS: Math.min(s.endS, Math.max(time, s.startS + .1)) } : s));
  };
  const split = () => {
    if (!current) return;
    const cut = Math.max(current.startS + .1, Math.min(current.endS - .1, time));
    if (cut <= current.startS || cut >= current.endS) { setMessage("Move the playhead inside the selected segment to split it."); return; }
    push([...segments.slice(0, selectedSegment), { startS: current.startS, endS: cut }, { startS: cut, endS: current.endS }, ...segments.slice(selectedSegment + 1)]);
    setSelectedSegment(selectedSegment + 1);
    setMessage("Segment split.");
  };
  const removeSegment = () => {
    if (segments.length <= 1) return;
    push(segments.filter((_, i) => i !== selectedSegment));
    setSelectedSegment(Math.min(selectedSegment, segments.length - 2));
  };
  const undo = () => {
    const previous = history.at(-1);
    if (!previous) return;
    setFuture(f => [segments, ...f]); setSegments(previous);
    setSelectedSegment(i => Math.min(i, previous.length - 1)); setHistory(h => h.slice(0, -1));
  };
  const redo = () => {
    const next = future[0];
    if (!next) return;
    setHistory(h => [...h, segments]); setSegments(next);
    setSelectedSegment(i => Math.min(i, next.length - 1)); setFuture(f => f.slice(1));
  };

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
      const clipStart = segments[0].startS;
      const clipEnd = segments[segments.length - 1].endS;
      const captionBoundsChanged = captionBounds.current.clipId !== selectedId || captionBounds.current.startS !== clipStart || captionBounds.current.endS !== clipEnd;
      if (captionState.current.cues.length && captionBoundsChanged) {
        const cues = captionState.current.cues.flatMap(cue => {
          const start = Math.max(clipStart, cue.start);
          const end = Math.min(clipEnd, cue.end);
          return end > start ? [{ startS: start - clipStart, endS: end - clipStart, text: cue.text }] : [];
        });
        const captionResponse = await fetch(`/api/clips/${selectedId}/captions`, {
          method: "PUT", headers: { "content-type": "application/json" },
          body: JSON.stringify({ cues, style: captionState.current.style }),
        });
        const captionData = await captionResponse.json().catch(() => ({}));
        if (!captionResponse.ok) throw new Error(`Edit saved, but caption timing could not be updated: ${captionData.error ?? "caption save failed"}`);
        captionBounds.current = { clipId: selectedId, startS: clipStart, endS: clipEnd };
      }
      setSelected(c => c?.id === selectedId ? { ...c, startS: segments[0].startS, endS: segments[segments.length - 1].endS, edit: data } : c);
      savedSignature.current = JSON.stringify({ id: selectedId, segments, aspectRatio: aspect });
      setMessage("All edits saved");
      return true;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Save failed");
      return false;
    } finally { setSaving(false); }
  }, [selectedId, segments, aspect]);

  useEffect(() => {
    if (!selectedId || !segments.length) return;
    const signature = JSON.stringify({ id: selectedId, segments, aspectRatio: aspect });
    if (signature === savedSignature.current) return;
    const timer = setTimeout(() => { void save(); }, 850);
    return () => clearTimeout(timer);
  }, [selectedId, segments, aspect, save]);

  useEffect(() => {
    if (!renderId || !selectedId || renderStatus === "READY" || renderStatus === "FAILED") return;
    const timer = setInterval(() => {
      fetch(`/api/clips/${selectedId}/render`).then(r => r.ok ? r.json() : null).then(d => {
        if (d?.render) { setRenderId(d.render.id); setRenderStatus(d.render.status); setRenderError(d.render.error ?? null); }
      }).catch(() => {});
    }, 2500);
    return () => clearInterval(timer);
  }, [renderId, renderStatus, selectedId]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(target.tagName) || target.isContentEditable)) return;
      if (event.code === "Space") { event.preventDefault(); const v = video.current; if (v?.paused) void v.play(); else v?.pause(); }
      if (event.key === ",") { video.current?.pause(); seek(time - 1 / (fps && fps > 0 ? fps : 30)); }
      if (event.key === ".") { video.current?.pause(); seek(time + 1 / (fps && fps > 0 ? fps : 30)); }
      if (event.key.toLowerCase() === "f") { event.preventDefault(); const frame = video.current?.parentElement; if (frame) { if (document.fullscreenElement) void document.exitFullscreen(); else void frame.requestFullscreen(); } }
      if (event.key.toLowerCase() === "i") trimIn();
      if (event.key.toLowerCase() === "o") trimOut();
      if (event.key.toLowerCase() === "s") split();
      if (event.key === "Delete" || event.key === "Backspace") removeSegment();
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") { event.preventDefault(); undo(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") { event.preventDefault(); redo(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [trimIn, trimOut, split, removeSegment, undo, redo, fps, seek, time]);

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
      setRenderId(data.render.id); setRenderStatus(data.render.status); setRenderError(data.render.error ?? null); setMessage("Render queued. This panel updates as the worker progresses.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Render failed"); }
    finally { setRendering(false); }
  };

  const exportClip = async () => {
    if (!selectedId || renderStatus !== "READY") return;
    setExporting(true);
    try {
      const response = await fetch(`/api/clips/${selectedId}/export`, { method: "POST" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error ?? "Export failed.");
      if (data.url) { const link = document.createElement("a"); link.href = data.url; link.download = `clip-${selectedId}.mp4`; document.body.append(link); link.click(); link.remove(); setMessage("Your MP4 download has started."); }
      else setMessage("Export created, but the server did not return a download URL.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Export failed"); }
    finally { setExporting(false); }
  };

  const toggleFavorite = async () => {
    if (!selectedId || favoriteBusy) return;
    setFavoriteBusy(true);
    try {
      const response = await fetch(`/api/clips/${selectedId}/favorite`, { method: "POST" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error ?? "Could not update favorites.");
      setFavorites(current => data.favorite ? [...new Set([...current, selectedId])] : current.filter(id => id !== selectedId));
      setMessage(data.favorite ? "Added to favorites" : "Removed from favorites");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Favorite update failed"); }
    finally { setFavoriteBusy(false); }
  };

  const pointerTimeline = (event: ReactPointerEvent<HTMLDivElement>) => {
    const rect = timeline.current?.getBoundingClientRect() ?? event.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(rect.width, 1)));
    if (dragRef.current?.pointerId === event.pointerId) {
      let candidate = mediaOffsetSeconds + snapSourceTimeToFrame(ratio * duration, fps);
      const { segment, edge } = dragRef.current;
      const snapPoints = segments.flatMap((item, i) => i === segment ? [] : [item.startS, item.endS]).concat([mediaOffsetSeconds, timelineEnd]);
      candidate = snapSourceTimeToMarkers(candidate, snapPoints);
      setSegments(existing => existing.map((item, index) => {
        if (index !== segment) return item;
        const bounds = selected ? sourceBounds(selected) : { startS: 0, endS: duration };
        const minStart = index > 0 ? existing[index - 1].endS : bounds.startS;
        const maxEnd = index < existing.length - 1 ? existing[index + 1].startS : bounds.endS;
        return edge === "start"
          ? { ...item, startS: Math.max(minStart, Math.min(candidate, item.endS - .1)) }
          : { ...item, endS: Math.min(maxEnd, Math.max(candidate, item.startS + .1)) };
      }));
      return;
    }
    if (event.buttons) seek(mediaOffsetSeconds + ratio * duration);
  };
  const beginTrim = (event: ReactPointerEvent<HTMLButtonElement>, segment: number, edge: "start" | "end") => {
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    if (!dragRef.current) {
      dragBefore.current = segments;
      setHistory(h => [...h.slice(-49), segments]);
      setFuture([]);
      dragRef.current = { segment, edge, pointerId: event.pointerId };
      setDragging(true);
    }
  };
  const endTrim = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    dragRef.current = null; dragBefore.current = null; setDragging(false);
  };
  const keyTimeline = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.target !== event.currentTarget) return;
    const step = event.shiftKey ? 5 : 1;
    if (event.key === "ArrowLeft") { event.preventDefault(); seek(time - step); }
    else if (event.key === "ArrowRight") { event.preventDefault(); seek(time + step); }
    else if (event.key === "Home") { event.preventDefault(); seek(mediaOffsetSeconds); }
    else if (event.key === "End") { event.preventDefault(); seek(timelineEnd); }
  };
  const resetBoundaries = () => {
    if (!selected) return;
    push([sourceBounds(selected)]);
    setSelectedSegment(0);
    setMessage("Restored the original AI boundaries. Save to keep this change.");
  };
  const updateCaptionText = (index: number, text: string) => setCaptionCues(cues => cues.map((cue, i) => i === index ? { ...cue, text } : cue));
  const saveCaptions = async () => {
    if (!selectedId) return;
    try {
      const response = await fetch(`/api/clips/${selectedId}/captions`, {
        method: "PUT", headers: { "content-type": "application/json" },
        body: JSON.stringify({ cues: captionCues.map(cue => ({ startS: cue.start - (selected?.startS ?? 0), endS: cue.end - (selected?.startS ?? 0), text: cue.text })), style: captionStyle }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error ?? "Could not save captions.");
      if (selected) captionBounds.current = { clipId: selected.id, startS: selected.startS, endS: selected.endS };
      setMessage("Caption edits saved");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Caption save failed"); }
  };
  const activeCaption = captionsVisible && selected
    ? captionCues.find(cue => cue.start <= time && cue.end >= time)
    : undefined;

  useEffect(() => {
    const onFullscreen = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onFullscreen);
    return () => document.removeEventListener("fullscreenchange", onFullscreen);
  }, []);

  return <section className="overflow-hidden rounded-2xl border border-white/[.09] bg-[#0a0d12] text-white shadow-2xl shadow-black/20">
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[.08] bg-[#10151d] px-4 py-3">
      <div className="flex min-w-0 items-center gap-3">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[#c4f36b] text-sm font-black text-[#14190d]">CF</div>
        <div className="min-w-0"><div className="truncate text-sm font-semibold">{selected?.title || selected?.category || "Clip editor"}</div><div className="mt-0.5 text-[10px] text-zinc-500">CLIPFINDER STUDIO <span className="mx-1 text-zinc-700">/</span> {clock(clipDuration)} sequence</div></div>
      </div>
      <div className="flex items-center gap-2">
        <span className="hidden items-center gap-1.5 text-[10px] text-zinc-500 sm:inline-flex"><span className={`h-1.5 w-1.5 rounded-full ${saving ? "animate-pulse bg-amber-300" : "bg-emerald-300"}`}/>{saving ? "Saving" : "Autosaved"}</span>
        <button className={button} onClick={toggleFavorite} disabled={!selected || favoriteBusy}>{favorites.includes(selectedId ?? "") ? "♥ Favorited" : "♡ Favorite"}</button>
        <button className={button} onClick={() => setShowShortcuts(v => !v)}>⌘ Shortcuts</button>
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
          <div className="flex items-center gap-2"><span className="font-mono text-xs tabular-nums text-zinc-300">{clock(time, true)}</span><span className="text-zinc-700">/</span><span className="font-mono text-xs text-zinc-500">{clock(timelineEnd)}</span></div>
        </div>
        <div className="relative flex min-h-[300px] items-center justify-center overflow-hidden bg-[radial-gradient(ellipse_at_center,_#202833_0%,_#0a0d12_66%)] p-5 sm:min-h-[390px]">
          <div className={`relative overflow-hidden rounded-xl border border-white/10 bg-black shadow-[0_24px_80px_rgba(0,0,0,.45)] ${aspect === "9:16" ? "aspect-[9/16] max-h-[420px] w-auto max-w-full" : aspect === "1:1" ? "aspect-square max-h-[420px] w-full max-w-[420px]" : "aspect-video w-full max-w-[720px]"}`}>
            {mediaId ? <video ref={video} src={`/api/media/${mediaId}`} className={`h-full w-full ${aspect === "9:16" ? "object-cover" : "object-contain"}`} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onWaiting={() => setVideoLoading(true)} onCanPlay={() => { setVideoLoading(false); setVideoError(""); }} onLoadedMetadata={() => { setVideoLoading(false); if (video.current) { video.current.playbackRate = playbackRate; video.current.volume = volume; const first = segments[0]?.startS ?? mediaOffsetSeconds; video.current.currentTime = sourceToMediaTime(first, mediaOffsetSeconds); setTime(first); } }} onError={() => { setVideoLoading(false); setVideoError("The source preview could not be loaded. Check the media connection and try again."); }} onClick={() => video.current?.paused ? void video.current.play() : video.current?.pause()} playsInline /> : <div className="grid h-full place-items-center text-xs text-zinc-600">Source media is not attached yet.</div>}
            {videoLoading && !videoError && mediaId && <div className="absolute inset-0 grid place-items-center bg-black/45 text-xs text-zinc-300" role="status">Loading source preview…</div>}
            {videoError && <div className="absolute inset-0 grid place-items-center bg-black/75 p-5 text-center text-xs text-red-200" role="alert">{videoError}</div>}
            {activeCaption && <div className="pointer-events-none absolute inset-x-3 bottom-14 text-center"><span className="rounded bg-black/70 px-2 py-1 font-semibold [text-shadow:0_1px_4px_black]" style={{ fontFamily: captionStyle.font, fontSize: `${Math.max(12, Number(captionStyle.size) / 3)}px`, color: assColorToHex(String(captionStyle.color)) }}>{activeCaption.text}</span></div>}
            <button onClick={() => video.current?.paused ? void video.current.play() : video.current?.pause()} aria-label={playing ? "Pause preview" : "Play preview"} className="absolute bottom-3 left-3 grid h-10 w-10 place-items-center rounded-full border border-white/15 bg-black/65 text-sm backdrop-blur transition hover:bg-black/85">{playing ? "Ⅱ" : "▶"}</button>
            <div className="absolute right-3 top-3 rounded-md border border-white/10 bg-black/60 px-2 py-1 font-mono text-[10px] text-white/80">{aspect}</div>
            {selected && <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 to-transparent px-4 pb-4 pt-12"><div className="text-[9px] font-bold uppercase tracking-[.18em] text-[#c4f36b]">{selected.category || "AI highlight"}</div><div className="mt-1 line-clamp-2 text-sm font-semibold">{selected.title || "Untitled highlight"}</div></div>}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 border-t border-white/[.07] bg-[#10151d] px-4 py-3" aria-label="Video playback controls">
          <button className={button} onClick={() => stepFrame(-1)} aria-label="Previous frame">|◀</button>
          <button className={`${button} !min-w-20`} onClick={() => video.current?.paused ? void video.current.play() : video.current?.pause()} aria-label={playing ? "Pause" : "Play"}>{playing ? "Ⅱ Pause" : "▶ Play"}</button>
          <button className={button} onClick={() => stepFrame(1)} aria-label="Next frame">▶|</button>
          <label className="ml-2 flex items-center gap-2 text-[10px] text-zinc-500">Speed<select aria-label="Playback speed" className="rounded-md border border-white/10 bg-[#0a0d12] px-2 py-2 text-xs text-zinc-200" value={playbackRate} onChange={event => setRate(Number(event.target.value))}>{[0.25, 0.5, 0.75, 1, 1.25, 1.5, 2].map(rate => <option key={rate} value={rate}>{rate}×</option>)}</select></label>
          <label className="flex items-center gap-2 text-[10px] text-zinc-500"><span aria-hidden="true">◖</span><input aria-label="Preview volume" type="range" min="0" max="1" step="0.05" value={volume} onChange={event => setPlayerVolume(Number(event.target.value))} className="w-20 accent-[#c4f36b]"/></label>
          <button className={`${button} ml-auto`} onClick={() => void toggleFullscreen()} aria-label={fullscreen ? "Exit fullscreen" : "Enter fullscreen"}>{fullscreen ? "↙ Exit fullscreen" : "↗ Fullscreen"}</button>
          <span className="font-mono text-xs tabular-nums text-zinc-300" aria-live="off">{clock(time, true)} <span className="text-zinc-700">/</span> {clock(timelineEnd)}</span>
        </div>

        <div className="border-t border-white/[.08] bg-[#0e1218] p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3"><div><div className="text-xs font-semibold">Timeline</div><div className="mt-1 text-[10px] text-zinc-600">Click the ruler to seek · select a segment to edit</div></div><div className="flex gap-1.5"><button className={button} onClick={undo} disabled={!history.length}>↶ Undo</button><button className={button} onClick={redo} disabled={!future.length}>↷ Redo</button></div></div>
          <div className="mb-1 flex items-center justify-between gap-3"><span className="font-mono text-[9px] text-zinc-600">{clock(mediaOffsetSeconds)}</span><label className="flex items-center gap-2 text-[9px] text-zinc-600">Zoom <input aria-label="Timeline zoom" type="range" min="1" max="8" step="1" value={zoom} onChange={event => setZoom(Number(event.target.value))} className="accent-[#c4f36b]"/><span>{zoom}×</span></label><span className="font-mono text-[9px] text-zinc-600">{clock(timelineEnd)}</span></div>
          <div className="overflow-x-auto rounded-lg" onPointerMove={pointerTimeline} onPointerUp={endTrim} onPointerCancel={endTrim}>
          <div ref={timeline} role="group" aria-label="Video timeline. Focus and use left or right arrows to seek, Shift plus arrows to seek five seconds." tabIndex={0} onKeyDown={keyTimeline} onPointerDown={event => { if (!dragRef.current) { event.currentTarget.setPointerCapture(event.pointerId); seek(((event.clientX - event.currentTarget.getBoundingClientRect().left) / Math.max(1, event.currentTarget.clientWidth)) * duration); } }} className={`relative h-[100px] cursor-crosshair rounded-lg border border-white/[.06] bg-[#090c10] focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-300 ${dragging ? "cursor-ew-resize" : ""}`} style={{ width: `${Math.max(100, zoom * 100)}%`, minWidth: 360 }}>
            <div className="absolute inset-x-0 top-0 h-5 border-b border-white/[.05] bg-white/[.015]">{Array.from({ length: 21 }, (_, i) => <span key={i} className="absolute top-0 h-2 border-l border-white/10" style={{ left: `${i * 5}%` }}/>)}</div>
            <div className="absolute inset-x-2 top-7 h-8 overflow-hidden rounded-md bg-white/[.025]">
              {waveform.map((value, i) => <span key={i} className="absolute bottom-1/2 w-px bg-[#91a3b7]/55" style={{ left: `${i / Math.max(1, waveform.length - 1) * 100}%`, height: `${Math.max(5, Math.min(28, value * 28))}px`, transform: "translateY(50%)" }}/>)}
            </div>
              {segments.map((segment, index) => <div key={`${segment.startS}-${segment.endS}-${index}`} className={`absolute bottom-2 top-[62px] rounded border transition ${index === selectedSegment ? "border-[#c4f36b] bg-[#c4f36b]/25 shadow-[0_0_16px_rgba(196,243,107,.08)]" : "border-white/15 bg-white/[.08] hover:bg-white/[.14]"}`} style={{ left: `${pct(segment.startS)}%`, width: `${Math.max(.7, pct(segment.endS) - pct(segment.startS))}%` }}><button type="button" aria-label={`Trim segment ${index + 1} start`} onPointerDown={event => beginTrim(event, index, "start")} className="absolute inset-y-0 left-0 z-10 w-2 cursor-ew-resize rounded-l bg-[#c4f36b]"/><button type="button" aria-label={`Trim segment ${index + 1} end`} onPointerDown={event => beginTrim(event, index, "end")} className="absolute inset-y-0 right-0 z-10 w-2 cursor-ew-resize rounded-r bg-[#c4f36b]"/><button type="button" aria-label={`Select segment ${index + 1}`} onPointerDown={event => event.stopPropagation()} onClick={() => { setSelectedSegment(index); seek(segment.startS); }} className="absolute inset-0 w-full text-left"><span className="absolute left-3 top-0.5 truncate text-[8px] font-semibold text-white/80">{index + 1}</span></button></div>)}
            <div className="pointer-events-none absolute inset-y-0 z-10 w-px bg-[#f4f7fb]" style={{ left: `${pct(time)}%` }}><div className="-ml-[4px] h-2 w-2 rounded-sm bg-white"/></div>
          </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2"><button className={button} onClick={trimIn} disabled={!current}>⟪ Trim in <kbd className="text-[9px] text-zinc-600">I</kbd></button><button className={button} onClick={trimOut} disabled={!current}>Trim out ⟫ <kbd className="text-[9px] text-zinc-600">O</kbd></button><button className={button} onClick={split} disabled={!current}>✂ Split <kbd className="text-[9px] text-zinc-600">S</kbd></button><button className={button} onClick={removeSegment} disabled={segments.length <= 1}>− Remove segment</button><span className="ml-auto self-center font-mono text-[10px] text-zinc-600">{segments.length} segment{segments.length === 1 ? "" : "s"}</span></div>
          <button className={`${button} mt-2`} onClick={resetBoundaries} disabled={!selected}>Reset to AI boundaries</button>
        </div>
      </div>

      <aside className="border-t border-white/[.08] bg-[#0e1218] p-4 lg:border-l lg:border-t-0">
        <div className="mb-4 flex items-center justify-between"><span className={panelLabel}>Inspector</span><span className="text-[10px] text-zinc-600">EDIT PROPERTIES</span></div>
        <div className="rounded-xl border border-white/[.07] bg-black/10 p-3"><div className="text-xs font-semibold">AI clip review</div><div className="mt-3 space-y-3">{[{label:"Start",value:clock(segments[0]?.startS ?? 0,true)},{label:"End",value:clock(segments.at(-1)?.endS ?? 0,true)},{label:"Duration",value:clock(clipDuration,true)},{label:"AI score",value:selected?.score == null ? "Not scored" : `${Math.round(selected.score)} / 100`},{label:"Category",value:selected?.category ?? "Not categorized"}].map(item=><div key={item.label} className="flex items-center justify-between gap-2 text-xs"><span className="text-zinc-500">{item.label}</span><span className="max-w-[65%] truncate text-right font-mono text-zinc-200">{item.value}</span></div>)}</div>{selected?.highlight?.rationale && <p className="mt-3 border-t border-white/[.06] pt-3 text-[10px] leading-5 text-zinc-400">{selected.highlight.rationale}</p>}</div>
        <div className="mt-3 rounded-xl border border-white/[.07] p-3"><div className="text-xs font-semibold">Canvas</div><div className="mt-3 grid grid-cols-3 gap-1.5">{["9:16","1:1","16:9"].map(value=><button key={value} onClick={() => setAspect(value)} aria-pressed={aspect === value} className={`rounded-lg border py-2.5 text-[10px] font-semibold transition ${aspect === value ? "border-[#c4f36b]/50 bg-[#c4f36b]/[.08] text-[#d7f9a7]" : "border-white/[.07] text-zinc-500 hover:bg-white/[.04]"}`}>{value}</button>)}</div><p className="mt-2 text-[10px] leading-4 text-zinc-600">The selected ratio is applied by the render pipeline.</p></div>
        <details className="mt-3 rounded-xl border border-white/[.07] p-3"><summary className="cursor-pointer list-none text-xs font-semibold">Caption editor <span className="ml-1 text-[10px] font-normal text-zinc-600">{captionCues.length} cues</span></summary><div className="mt-3 flex items-center justify-between gap-2"><label className="text-[10px] text-zinc-500">Show on preview</label><input aria-label="Show captions in preview" type="checkbox" checked={captionsVisible} onChange={event => setCaptionsVisible(event.target.checked)} className="accent-[#c4f36b]"/></div><div className="mt-3 grid grid-cols-2 gap-2"><label className="text-[10px] text-zinc-500">Typeface<select aria-label="Caption font" className="mt-1 w-full rounded border border-white/10 bg-[#090c10] p-2 text-xs text-zinc-200" value={captionStyle.font} onChange={event => setCaptionStyle(style => ({ ...style, font: event.target.value }))}>{["Arial","Inter","Arial Black","DejaVu Sans"].map(font => <option key={font}>{font}</option>)}</select></label><label className="text-[10px] text-zinc-500">Size<input aria-label="Caption size" type="number" min="16" max="120" value={captionStyle.size} onChange={event => setCaptionStyle(style => ({ ...style, size: Math.max(16, Math.min(120, Number(event.target.value) || 48)) }))} className="mt-1 w-full rounded border border-white/10 bg-[#090c10] p-2 text-xs text-zinc-200"/></label></div><div className="mt-3 max-h-44 space-y-2 overflow-y-auto">{captionCues.map((cue, index) => <label key={`${cue.start}-${index}`} className="block text-[9px] text-zinc-600">{clock(cue.start,true)}<input aria-label={`Caption ${index + 1} text`} value={cue.text} onChange={event => updateCaptionText(index, event.target.value)} className="mt-1 w-full rounded border border-white/10 bg-[#090c10] p-2 text-xs text-zinc-200"/></label>)}</div><button className={`${button} mt-3 w-full`} onClick={() => void saveCaptions()}>Save caption edits</button>{selected && <a href={`/api/clips/${selected.id}/captions`} className={`${button} mt-2 w-full`}>↓ Download SRT</a>}<p className="mt-2 text-[9px] leading-4 text-zinc-600">Visibility controls the preview. The current render API always includes available transcript captions.</p></details>
        <div className="mt-3 rounded-xl border border-white/[.07] p-3"><div className="text-xs font-semibold">Review decision</div><div className="mt-3 grid grid-cols-2 gap-2"><button onClick={() => void decide("accept")} className="min-h-9 rounded-lg border border-emerald-300/20 bg-emerald-300/[.05] text-[10px] font-semibold text-emerald-200 hover:bg-emerald-300/10">✓ Approve</button><button onClick={() => void decide("reject")} className="min-h-9 rounded-lg border border-red-300/15 bg-red-300/[.035] text-[10px] font-semibold text-red-200 hover:bg-red-300/10">× Reject</button></div><p className="mt-2 text-[10px] text-zinc-600">Current status: {selected?.status?.toLowerCase() ?? "no clip selected"}</p></div>
        <div className="mt-3 rounded-xl border border-white/[.07] p-3"><div className="flex items-center justify-between"><div className="text-xs font-semibold">Render queue</div><span className={`rounded-full px-2 py-1 text-[9px] ${renderStatus === "READY" ? "bg-emerald-300/10 text-emerald-200" : renderStatus === "FAILED" ? "bg-red-300/10 text-red-200" : "bg-white/[.05] text-zinc-400"}`}>{renderStatus?.toLowerCase() ?? "not queued"}</span></div><p className="mt-2 text-[10px] leading-4 text-zinc-600">{renderStatus === "READY" ? "Your render is ready to preview and export." : renderStatus === "FAILED" ? renderError || "The render worker reported a failure." : "Save the edit and queue a render when the cut is ready."}</p>{renderStatus === "READY" && renderId && <><video src={`/api/renders/${renderId}`} controls className="mt-3 w-full rounded-lg bg-black"/><button className="mt-2 w-full rounded-lg border border-[#c4f36b]/20 py-2.5 text-xs font-semibold text-[#d7f9a7] hover:bg-[#c4f36b]/[.06] disabled:opacity-40" disabled={exporting} onClick={() => void exportClip()}>{exporting ? "Preparing download…" : "↓ Export MP4"}</button></>}</div>
        {message && <p role="status" aria-live="polite" className="mt-3 rounded-lg border border-white/[.07] bg-white/[.025] p-3 text-[10px] leading-4 text-zinc-300">{message}</p>}
        <button className={`${button} mt-3 w-full`} onClick={() => void save()} disabled={saving}>{saving ? "Saving edits…" : "✓ Save changes now"}</button>
      </aside>
    </div>
    <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-white/[.07] bg-[#0b0f14] px-4 py-2.5 text-[9px] text-zinc-600"><span>CLIPFINDER STUDIO · {projectId.slice(0, 8)}</span><span>Edits are saved to your project · Preview before publishing</span></footer>
  </section>;
}
