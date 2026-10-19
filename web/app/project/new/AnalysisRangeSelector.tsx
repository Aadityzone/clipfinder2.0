"use client";

import { useEffect, useMemo, useState } from "react";

export type RangeMetadata = {
  title: string | null;
  platform: string;
  duration: number;
  thumbnail: string | null;
  sourceType: string;
  entitlement: { plan: "free" | "pro"; maxDurationMs: number; canSelectCustomDuration: boolean };
};

const formatTime = (seconds: number) => {
  const value = Math.max(0, Math.floor(seconds));
  return [Math.floor(value / 3600), Math.floor(value / 60) % 60, value % 60]
    .map((part) => String(part).padStart(2, "0")).join(":");
};

export default function AnalysisRangeSelector({ metadata, value, onChange }: {
  metadata: RangeMetadata;
  value: { startSeconds: number; endSeconds: number };
  onChange: (range: { startSeconds: number; endSeconds: number }) => void;
}) {
  const sourceMs = Math.round(metadata.duration * 1000);
  const maxDurationMs = Math.min(metadata.entitlement.maxDurationMs, sourceMs);
  const shortSource = sourceMs < 60 * 60 * 1000;
  const maxSeconds = maxDurationMs / 1000;
  const allowedPresets = useMemo(() => {
    if (shortSource) return [maxSeconds];
    if (!metadata.entitlement.canSelectCustomDuration) return [3600, maxSeconds].filter((seconds, index, values) => seconds <= maxSeconds && values.indexOf(seconds) === index);
    const presets = [3600, 7200, 10800].filter((seconds) => seconds <= maxSeconds && seconds <= metadata.duration);
    if (metadata.duration <= maxSeconds && !presets.includes(metadata.duration)) presets.push(metadata.duration);
    return presets.length ? presets : [maxSeconds];
  }, [maxSeconds, metadata.duration, metadata.entitlement.canSelectCustomDuration, shortSource]);
  const initialDuration = allowedPresets[0];
  const [durationSeconds, setDurationSeconds] = useState(initialDuration);
  const [customHours, setCustomHours] = useState("1");
  const [startSeconds, setStartSeconds] = useState(0);
  const [custom, setCustom] = useState(false);
  const selectedDuration = shortSource ? metadata.duration : custom ? Number(customHours) * 3600 : durationSeconds;
  const safeDuration = Math.min(maxSeconds, metadata.duration, Math.max(shortSource ? 0.001 : 3600, selectedDuration));
  const maxStart = Math.max(0, metadata.duration - safeDuration);
  const safeStartSeconds = Math.min(startSeconds, maxStart);
  const endSeconds = safeStartSeconds + safeDuration;

  useEffect(() => {
    onChange({ startSeconds: Math.round(safeStartSeconds * 1000) / 1000, endSeconds: Math.round(endSeconds * 1000) / 1000 });
  }, [endSeconds, onChange, safeStartSeconds]);

  if (maxSeconds <= 0) return <section className="mt-5 rounded-2xl border border-amber-300/20 bg-amber-300/[.04] p-4" role="status">
    <p className="text-sm font-medium text-amber-100">Range analysis is unavailable on this plan.</p>
    <p className="mt-2 text-xs leading-5 text-zinc-400">Your account has no analysis duration configured. Visit billing to review the existing Pro upgrade option.</p>
    <a className="cf-button-secondary mt-3 inline-flex" href="/usage">Review plans</a>
  </section>;

  return <section aria-label="Analysis range" className="mt-5 rounded-2xl border border-[#39ff14]/15 bg-[#39ff14]/[.025] p-4 sm:p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="cf-kicker">Choose an analysis range</p><h3 className="mt-2 text-sm font-semibold">Source duration · {formatTime(metadata.duration)}</h3></div>
      <span className="rounded-lg border border-[#39ff14]/20 bg-[#39ff14]/[.06] px-2.5 py-1.5 text-[11px] text-[#b2ff9b]">{metadata.entitlement.plan === "pro" ? "Pro" : "Free"} maximum · {formatTime(maxSeconds)}</span>
    </div>
    {shortSource ? <p className="mt-4 text-xs leading-5 text-zinc-400">This source is shorter than one hour, so the full video will be analyzed.</p> : <>
      <div className="mt-5 flex flex-wrap gap-2">
        {allowedPresets.map((seconds) => <button key={seconds} type="button" onClick={() => { setDurationSeconds(seconds); setCustom(false); }} aria-pressed={!custom && durationSeconds === seconds} className={`rounded-xl border px-3 py-2 text-xs transition ${!custom && durationSeconds === seconds ? "border-[#39ff14]/50 bg-[#39ff14]/10 text-[#b2ff9b]" : "border-white/10 text-zinc-400 hover:bg-white/[.04]"}`}>
          {metadata.duration <= maxSeconds && Math.abs(seconds - metadata.duration) < 0.001 ? `Full source · ${formatTime(seconds)}` : `Analyze ${formatTime(seconds)}`}
        </button>)}
        {metadata.entitlement.canSelectCustomDuration && <button type="button" onClick={() => setCustom(true)} aria-pressed={custom} className={`rounded-xl border px-3 py-2 text-xs ${custom ? "border-[#39ff14]/50 bg-[#39ff14]/10 text-[#b2ff9b]" : "border-white/10 text-zinc-400"}`}>Custom</button>}
      </div>
      {custom && <label className="mt-4 block text-xs text-zinc-400">Custom duration in hours
        <input className="cf-input mt-2 max-w-48" type="number" min="1" max={maxSeconds / 3600} step="0.25" value={customHours} onChange={(event) => setCustomHours(event.target.value)} />
      </label>}
      <label className="mt-5 block text-xs text-zinc-400">Start time · {formatTime(safeStartSeconds)}
        <input className="mt-3 w-full accent-[#39ff14]" type="range" min="0" max={Math.floor(maxStart)} step="1" value={safeStartSeconds} onChange={(event) => setStartSeconds(Number(event.target.value))} aria-label="Select source start time" />
      </label>
      <div className="relative mt-2 h-3 overflow-hidden rounded-full bg-white/[.08]" aria-label="Selected section timeline">
        <div className="absolute inset-y-0 rounded-full bg-[#39ff14]/80" style={{ left: `${metadata.duration ? (safeStartSeconds / metadata.duration) * 100 : 0}%`, width: `${metadata.duration ? (safeDuration / metadata.duration) * 100 : 0}%` }} />
      </div>
      <div className="mt-3 flex justify-between gap-3 text-[11px] text-zinc-500"><span>Start {formatTime(safeStartSeconds)}</span><span>End {formatTime(endSeconds)}</span></div>
    </>}
    <p className="mt-4 rounded-xl border border-white/[.06] bg-black/20 p-3 text-xs leading-5 text-zinc-300">
      We will analyze <strong>{formatTime(safeStartSeconds)}–{formatTime(endSeconds)}</strong> ({formatTime(safeDuration)}). Source timestamps remain aligned to the original video.
    </p>
    {metadata.entitlement.plan === "free" && <p className="mt-3 text-[11px] leading-5 text-zinc-500">Free analyses are limited to one hour. Pro supports custom ranges up to the configured maximum.</p>}
  </section>;
}
