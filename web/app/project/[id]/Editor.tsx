"use client";

import { useCallback, useEffect, useRef, useState } from "react";

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

const fmt = (s: number) => {
  const safe = Math.max(0, Number.isFinite(s) ? s : 0);
  const m = Math.floor(safe / 60);
  const sec = Math.floor(safe % 60);
  const ms = Math.floor((safe % 1) * 10);
  return `${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}.${ms}`;
};

export default function Editor({
  projectId: _projectId,
  mediaId,
  duration,
  clips,
}: {
  projectId: string;
  mediaId: string | null;
  duration: number;
  clips: Clip[];
}) {
  const video = useRef<HTMLVideoElement>(null);
  const [selected, setSelected] = useState<Clip | null>(clips[0] ?? null);
  const [segments, setSegments] = useState<Segment[]>(
    clips[0]?.edit?.segments ??
      (clips[0] ? [{ startS: clips[0].startS, endS: clips[0].endS }] : []),
  );
  const [selectedSegment, setSelectedSegment] = useState(0);
  const [aspect, setAspect] = useState(clips[0]?.edit?.aspectRatio ?? "9:16");
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [saving, setSaving] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [renderId, setRenderId] = useState<string | null>(null);
  const [renderStatus, setRenderStatus] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState<Segment[][]>([]);
  const [waveform, setWaveform] = useState<number[]>([]);\n  const [captionStyle, setCaptionStyle] = useState({ font: "Arial", size: 48, color: "&H00FFFFFF" });
  const [future, setFuture] = useState<Segment[][]>([]);

  const current = segments[selectedSegment];

  useEffect(() => { if (!selected) return; fetch(`/api/clips/${selected.id}/captions?format=json`).then((r) => r.json()).then((d) => { if (d?.style) setCaptionStyle((x) => ({ ...x, ...d.style })); }).catch(() => {}); }, [selected?.id]);\n\n  useEffect(() => { if (!mediaId) return; fetch(`/api/media/${mediaId}/waveform`).then((r) => r.json()).then((d) => setWaveform(Array.isArray(d.samples) ? d.samples : [])).catch(() => setWaveform([])); }, [mediaId]);

  useEffect(() => {
    if (!selected) return;
    const nextSegments =
      selected.edit?.segments ?? [{ startS: selected.startS, endS: selected.endS }];
    setSegments(nextSegments);
    setSelectedSegment(0);
    setAspect(selected.edit?.aspectRatio ?? "9:16");
    setHistory([]);
    setFuture([]);
    setMessage("");
    setRenderId(null);
    setRenderStatus(null);

    fetch(`/api/clips/${selected.id}/render`)
      .then((r) => r.json())
      .then((d) => {
        if (d.render) {
          setRenderId(d.render.id);
          setRenderStatus(d.render.status);
        }
      })
      .catch(() => {});
  }, [selected?.id]);

  useEffect(() => {
    const v = video.current;
    if (!v) return;
    const onTime = () => {
      const next = v.currentTime;
      setTime(next);
      const index = segments.findIndex((s) => next >= s.startS && next <= s.endS);
      if (index >= 0) setSelectedSegment(index);
    };
    v.addEventListener("timeupdate", onTime);
    return () => v.removeEventListener("timeupdate", onTime);
  }, [segments]);

  const push = (next: Segment[]) => {
    setHistory((h) => [...h, segments]);
    setFuture([]);
    setSegments(next);
  };

  const seek = (t: number) => {
    const next = Math.max(0, Math.min(duration, t));
    if (video.current) video.currentTime = next;
    setTime(next);
  };

  const split = () => {
    if (!current) return;
    const cut = Math.max(current.startS + 0.1, Math.min(current.endS - 0.1, time));
    if (cut <= current.startS || cut >= current.endS) return;
    const next = [
      ...segments.slice(0, selectedSegment),
      { startS: current.startS, endS: cut },
      { startS: cut, endS: current.endS },
      ...segments.slice(selectedSegment + 1),
    ];
    push(next);
    setSelectedSegment(selectedSegment + 1);
  };

  const trimIn = () => {
    if (!current) return;
    const next = { ...current, startS: Math.min(time, current.endS - 0.1) };
    push(segments.map((s, i) => (i === selectedSegment ? next : s)));
  };

  const trimOut = () => {
    if (!current) return;
    const next = { ...current, endS: Math.max(time, current.startS + 0.1) };
    push(segments.map((s, i) => (i === selectedSegment ? next : s)));
  };

  const remove = () => {
    if (segments.length <= 1) return;
    push(segments.filter((_, i) => i !== selectedSegment));
    setSelectedSegment(Math.min(selectedSegment, segments.length - 2));
  };

  const undo = () => {
    const prev = history.at(-1);
    if (!prev) return;
    setFuture((f) => [segments, ...f]);
    setSegments(prev);
    setSelectedSegment(Math.min(selectedSegment, prev.length - 1));
    setHistory((h) => h.slice(0, -1));
  };

  const redo = () => {
    const next = future[0];
    if (!next) return;
    setHistory((h) => [...h, segments]);
    setSegments(next);
    setSelectedSegment(Math.min(selectedSegment, next.length - 1));
    setFuture((f) => f.slice(1));
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target?.tagName === "INPUT" || target?.tagName === "TEXTAREA") return;

      if (e.key === " ") {
        e.preventDefault();
        const v = video.current;
        if (!v) return;
        if (v.paused) void v.play();
        else v.pause();
      }
      if (e.key.toLowerCase() === "i") trimIn();
      if (e.key.toLowerCase() === "o") trimOut();
      if (e.key.toLowerCase() === "s") split();
      if (e.key === "Delete") remove();
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        undo();
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") {
        e.preventDefault();
        redo();
      }
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const save = useCallback(async () => {
    if (!selected || !segments.length) return;
    setSaving(true);
    setMessage("");

    try {
      const first = segments[0];
      const last = segments[segments.length - 1];
      const r = await fetch(`/api/clips/${selected.id}/edit`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          startS: first.startS,
          endS: last.endS,
          segments,
          aspectRatio: aspect,
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error ?? "Save failed");
      setSelected((c) => (c ? { ...c, startS: first.startS, endS: last.endS, edit: d } : c));
      setMessage("Saved");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [selected, segments, aspect]);

  useEffect(() => {
    if (!selected || !segments.length) return;
    const timer = setTimeout(() => void save(), 700);
    return () => clearTimeout(timer);
  }, [selected, segments, aspect, save]);

  useEffect(() => {
    if (!renderId || renderStatus === "READY" || renderStatus === "FAILED" || !selected) return;
    const id = setInterval(() => {
      fetch(`/api/clips/${selected.id}/render`)
        .then((r) => r.json())
        .then((d) => {
          if (d.render) {
            setRenderId(d.render.id);
            setRenderStatus(d.render.status);
          }
        })
        .catch(() => {});
    }, 2000);
    return () => clearInterval(id);
  }, [renderId, renderStatus, selected?.id]);

  const decide = async (decision: "accept" | "reject") => {
    if (!selected) return;
    const r = await fetch(`/api/clips/${selected.id}/decision`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ decision }),
    });
    const d = await r.json();
    if (!r.ok) {
      setMessage(d.error ?? "Decision failed");
      return;
    }
    setSelected((c) => (c ? { ...c, status: d.status } : c));
    setMessage(decision === "accept" ? "Clip approved" : "Clip rejected");
  };

  const exportClip = async () => {
    if (!selected || renderStatus !== "READY") return;
    const r = await fetch(`/api/clips/${selected.id}/export`, { method: "POST" });
    const d = await r.json();
    if (!r.ok) {
      setMessage(d.error ?? "Export failed");
      return;
    }
    window.open(d.url, "_blank", "noopener,noreferrer");
  };

  const render = async () => {
    if (!selected) return;
    await save();
    setRendering(true);
    setMessage("");

    try {
      const r = await fetch(`/api/clips/${selected.id}/render`, { method: "POST" });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error ?? "Render failed");
      setRenderId(d.render.id);
      setRenderStatus(d.render.status);
      setMessage("Render queued — the worker will process it.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Render failed");
    } finally {
      setRendering(false);
    }
  };

  const pct = (t: number) => (duration ? Math.min(100, Math.max(0, (t / duration) * 100)) : 0);

  return (
    <div className="grid min-h-[760px] grid-cols-[260px_1fr_300px] overflow-hidden rounded-3xl border border-white/10 bg-[#0d0f0b]">
      <aside className="border-r border-white/10 p-4">
        <div className="mb-4 text-xs uppercase tracking-[.2em] text-zinc-500">Clips</div>
        {clips.map((c) => (
          <button
            key={c.id}
            onClick={() => setSelected(c)}
            className={`mb-2 w-full rounded-xl border p-3 text-left ${
              selected?.id === c.id ? "border-lime-300/60 bg-lime-300/10" : "border-white/10 bg-white/[.02]"
            }`}
          >
            <div className="flex justify-between">
              <span className="font-medium">{c.category ?? "AI Detect"}</span>
              <span className="text-xs text-zinc-500">{c.score?.toFixed(0) ?? "—"}</span>
            </div>
            <div className="mt-1 text-xs text-zinc-500">{fmt(c.startS)} → {fmt(c.endS)}</div>
          </button>
        ))}
      </aside>

      <section className="flex min-w-0 flex-col">
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-3">
          <div>
            <span className="text-sm font-semibold">Editor</span>
            {selected && <span className="ml-3 text-xs text-zinc-500">{selected.status}</span>}
          </div>
          <div className="flex gap-2">
            <button onClick={undo} disabled={!history.length} className="rounded-lg border border-white/10 px-3 py-1.5 text-xs disabled:opacity-30">Undo</button>
            <button onClick={redo} disabled={!future.length} className="rounded-lg border border-white/10 px-3 py-1.5 text-xs disabled:opacity-30">Redo</button>
          </div>
        </div>

        <div className="relative flex flex-1 items-center justify-center bg-black p-6">
          <div className={`relative h-full max-h-[540px] w-full overflow-hidden rounded-2xl bg-zinc-950 ${
            aspect === "9:16" ? "max-w-[390px]" : aspect === "1:1" ? "max-w-[540px]" : "max-w-[760px]"
          }`}>
            <video
              ref={video}
              src={mediaId ? `/api/media/${mediaId}` : undefined}
              controls={false}
              className="h-full w-full object-contain"
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onClick={() => {
                if (!video.current) return;
                if (video.current.paused) void video.current.play();
                else video.current.pause();
              }}
            />
            <button
              onClick={() => {
                if (!video.current) return;
                if (video.current.paused) void video.current.play();
                else video.current.pause();
              }}
              className="absolute bottom-4 left-4 rounded-full bg-black/70 px-4 py-2 text-xs"
            >
              {playing ? "Pause" : "Play"}
            </button>
          </div>
        </div>

        <div className="border-t border-white/10 p-5">
          <div className="mb-3 flex items-center justify-between text-xs text-zinc-400">
            <span>{fmt(time)}</span>
            <span>{fmt(duration)}</span>
          </div>

          <div
            className="relative h-14 cursor-pointer rounded-xl bg-white/[.04]"
            onClick={(e) => {
              const r = e.currentTarget.getBoundingClientRect();
              seek(((e.clientX - r.left) / r.width) * duration);
            }}
          >
            {waveform.map((v, i) => <div key={i} className="absolute bottom-1 top-1 w-px bg-white/20" style={{ left: `${(i / Math.max(1, waveform.length - 1)) * 100}%`, transform: `scaleY(${Math.max(0.04, v)})`, transformOrigin: "center" }} />)}\n            {segments.map((s, i) => (
              <button
                key={`${s.startS}-${s.endS}-${i}`}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedSegment(i);
                  seek(s.startS);
                }}
                className={`absolute inset-y-2 rounded-lg border ${
                  i === selectedSegment ? "border-lime-300/80 bg-lime-300/20" : "border-white/10 bg-white/10"
                }`}
                style={{ left: `${pct(s.startS)}%`, width: `${Math.max(0.5, pct(s.endS) - pct(s.startS))}%` }}
                aria-label={`Select segment ${i + 1}`}
              />
            ))}
            <div className="absolute inset-y-0 w-0.5 bg-lime-300" style={{ left: `${pct(time)}%` }} />
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <button onClick={trimIn} disabled={!current} className="tool disabled:opacity-30">Trim in</button>
            <button onClick={trimOut} disabled={!current} className="tool disabled:opacity-30">Trim out</button>
            <button onClick={split} disabled={!current} className="tool disabled:opacity-30">Split</button>
            <button onClick={remove} disabled={segments.length <= 1} className="tool disabled:opacity-30">Delete segment</button>
            <button onClick={() => seek(current?.startS ?? 0)} disabled={!current} className="tool disabled:opacity-30">Go to start</button>
          </div>
          <div className="mt-3 text-xs text-zinc-500">
            Space play · I trim in · O trim out · S split · Delete remove · Ctrl/Cmd+Z undo
          </div>
        </div>
      </section>

      <aside className="border-l border-white/10 p-5">
        <div className="text-xs uppercase tracking-[.2em] text-zinc-500">Inspector</div>

        <div className="mt-6">
          <label className="text-sm text-zinc-400">Aspect ratio</label>
          <div className="mt-2 grid grid-cols-3 gap-2">
            {["9:16", "1:1", "16:9"].map((a) => (
              <button
                key={a}
                onClick={() => setAspect(a)}
                className={`rounded-xl border py-3 text-xs ${
                  aspect === a ? "border-lime-300 bg-lime-300/10 text-lime-200" : "border-white/10"
                }`}
              >
                {a}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-8">
          <div className="text-sm text-zinc-400">Captions</div>
          {selected && (
            <a
              href={`/api/clips/${selected.id}/captions`}
              className="mt-2 block rounded-xl border border-white/10 px-3 py-3 text-center text-xs hover:bg-white/[.04]"
            >
              Download SRT
            </a>
          )}
        </div>

        <div className="mt-8">
          <div className="text-sm text-zinc-400">Segments</div>
          {segments.map((s, i) => (
            <button
              key={i}
              type="button"
              onClick={() => {
                setSelectedSegment(i);
                seek(s.startS);
              }}
              className={`mt-2 w-full rounded-xl p-3 text-left text-xs ${
                i === selectedSegment ? "bg-lime-300/10 ring-1 ring-lime-300/30" : "bg-white/[.04]"
              }`}
            >
              {i + 1}. {fmt(s.startS)} → {fmt(s.endS)}
            </button>
          ))}
        </div>

        <div className="mt-8 rounded-2xl border border-white/10 bg-white/[.03] p-4">
          <div className="text-sm font-medium">Approval</div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button onClick={() => decide("accept")} className="rounded-xl border border-lime-300/30 px-3 py-2 text-xs">Approve</button>
            <button onClick={() => decide("reject")} className="rounded-xl border border-red-300/20 px-3 py-2 text-xs">Reject</button>
          </div>
        </div>

        <div className="mt-4 rounded-2xl border border-white/10 bg-white/[.03] p-4">
          <div className="text-sm font-medium">Render</div>
          <p className="mt-1 text-xs text-zinc-500">
            {renderStatus ? `Status: ${renderStatus.toLowerCase()}` : "FFmpeg will render the saved edit asynchronously."}
          </p>
          <button
            disabled={!selected || saving || rendering}
            onClick={render}
            className="mt-4 w-full rounded-xl bg-lime-300 px-4 py-3 text-sm font-semibold text-black disabled:opacity-40"
          >
            {rendering ? "Queueing…" : "Render clip"}
          </button>
          {renderStatus === "READY" && renderId && (
            <>
              <video src={`/api/renders/${renderId}`} controls className="mt-4 w-full rounded-xl" />
              <button onClick={exportClip} className="mt-3 w-full rounded-xl border border-white/10 px-4 py-3 text-sm font-semibold">
                Export MP4
              </button>
            </>
          )}
        </div>

        {message && <p className="mt-4 text-xs text-zinc-400">{message}</p>}
      </aside>
    </div>
  );
}
