"use client";

import { useId } from "react";
import AnimeMascot from "./AnimeMascot";

interface ConcentricProcessingRingsProps {
  sourceProgress: number; // 0 - 100
  aiProgress: number; // 0 - 100
  clipProgress: number; // 0 - 100
  currentStage?: string;
  isProcessing?: boolean;
  isStalled?: boolean;
  isFailed?: boolean;
}

export default function ConcentricProcessingRings({
  sourceProgress,
  aiProgress,
  clipProgress,
  currentStage = "Processing",
  isProcessing = true,
  isStalled = false,
  isFailed = false,
}: ConcentricProcessingRingsProps) {
  const filterId = useId().replace(/:/g, "");

  // Clamped percentages
  const pSource = Math.min(100, Math.max(0, Math.round(sourceProgress)));
  const pAi = Math.min(100, Math.max(0, Math.round(aiProgress)));
  const pClip = Math.min(100, Math.max(0, Math.round(clipProgress)));

  // Center coordinate
  const cx = 230;
  const cy = 230;

  // Concentric circle radii
  const rOuter = 195;
  const rMiddle = 155;
  const rInner = 115;

  // Circumferences
  const cOuter = 2 * Math.PI * rOuter;
  const cMiddle = 2 * Math.PI * rMiddle;
  const cInner = 2 * Math.PI * rInner;

  // Stroke dash offsets
  // Only a persisted phase completion is precise enough to render as a percentage.
  const offsetOuter = pSource >= 100 ? 0 : cOuter;
  const offsetMiddle = pAi >= 100 ? 0 : cMiddle;
  const offsetInner = pClip >= 100 ? 0 : cInner;
  const stage = currentStage.toLowerCase();
  const sourceActive = isProcessing && /(source|download|ingest|probe|media prep|extract)/.test(stage);
  const aiActive = isProcessing && /(transcrib|analys|rank|whisper|audio|visual|candidate)/.test(stage);
  const clipActive = isProcessing && /(render|clip output)/.test(stage);
  const phaseLabel = (progress: number, active: boolean) => isFailed
    ? "Failed"
    : isStalled && active
      ? "Paused · —"
      : progress >= 100
        ? "Complete · 100%"
        : active
          ? "Working · —"
          : "Waiting · —";

  return (
    <div className="relative flex flex-col items-center">
      {/* Central Hero Visualization Container */}
      <div className="relative aspect-square w-[min(360px,calc(100vw-2.5rem))] sm:h-[440px] sm:w-[440px] md:h-[470px] md:w-[470px]">
        {/* SVG Concentric Rings */}
        <svg
          viewBox="0 0 460 460"
          className="absolute inset-0 h-full w-full -rotate-90 transform"
          aria-hidden="true"
        >
          <defs>
            {/* Outer Ring Gradient (Electric Violet -> Indigo) */}
            <linearGradient id={`grad-outer-${filterId}`} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#c084fc" />
              <stop offset="50%" stopColor="#a855f7" />
              <stop offset="100%" stopColor="#6366f1" />
            </linearGradient>

            {/* Middle Ring Gradient (Vibrant Cyan -> Sky Blue) */}
            <linearGradient id={`grad-middle-${filterId}`} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#38bdf8" />
              <stop offset="50%" stopColor="#06b6d4" />
              <stop offset="100%" stopColor="#0891b2" />
            </linearGradient>

            {/* Inner Ring Gradient (Emerald -> Neon Accent Green) */}
            <linearGradient id={`grad-inner-${filterId}`} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#4ade80" />
            <stop offset="50%" stopColor="#c084fc" />
            <stop offset="100%" stopColor="#a855f7" />
            </linearGradient>

            {/* Glow Filters */}
            <filter id={`glow-outer-${filterId}`} x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor="#a855f7" floodOpacity="0.45" />
            </filter>
            <filter id={`glow-middle-${filterId}`} x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor="#06b6d4" floodOpacity="0.5" />
            </filter>
            <filter id={`glow-inner-${filterId}`} x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor="#10b981" floodOpacity="0.5" />
            </filter>
          </defs>

          {/* 1. OUTER RING (Source Processing) */}
          {/* Background track */}
          <circle
            cx={cx}
            cy={cy}
            r={rOuter}
            fill="none"
            stroke="rgba(168, 85, 247, 0.12)"
            strokeWidth="11"
            className="transition-colors duration-500"
          />
          {/* Active progress stroke */}
          <circle
            cx={cx}
            cy={cy}
            r={rOuter}
            fill="none"
            stroke={`url(#grad-outer-${filterId})`}
            strokeWidth="11"
            strokeDasharray={cOuter}
            strokeDashoffset={offsetOuter}
            strokeLinecap="round"
            filter={`url(#glow-outer-${filterId})`}
            className={`transition-[stroke-dashoffset] duration-700 ease-out ${isFailed ? "cf-ring-error" : ""}`}
          />
          {sourceActive && <g className="cf-ring-active"><circle cx={cx} cy={cy - rOuter} r="5" fill="#c084fc" filter={`url(#glow-outer-${filterId})`} /></g>}

          {/* 2. MIDDLE RING (AI Intelligence) */}
          {/* Background track */}
          <circle
            cx={cx}
            cy={cy}
            r={rMiddle}
            fill="none"
            stroke="rgba(6, 182, 212, 0.12)"
            strokeWidth="11"
            className="transition-colors duration-500"
          />
          {/* Active progress stroke */}
          <circle
            cx={cx}
            cy={cy}
            r={rMiddle}
            fill="none"
            stroke={`url(#grad-middle-${filterId})`}
            strokeWidth="11"
            strokeDasharray={cMiddle}
            strokeDashoffset={offsetMiddle}
            strokeLinecap="round"
            filter={`url(#glow-middle-${filterId})`}
            className={`transition-[stroke-dashoffset] duration-700 ease-out ${isFailed ? "cf-ring-error" : ""}`}
          />
          {aiActive && <g className="cf-ring-active"><circle cx={cx} cy={cy - rMiddle} r="5" fill="#38bdf8" filter={`url(#glow-middle-${filterId})`} /></g>}

          {/* 3. INNER RING (Clip Generation) */}
          {/* Background track */}
          <circle
            cx={cx}
            cy={cy}
            r={rInner}
            fill="none"
            stroke="rgba(16, 185, 129, 0.12)"
            strokeWidth="11"
            className="transition-colors duration-500"
          />
          {/* Active progress stroke */}
          <circle
            cx={cx}
            cy={cy}
            r={rInner}
            fill="none"
            stroke={`url(#grad-inner-${filterId})`}
            strokeWidth="11"
            strokeDasharray={cInner}
            strokeDashoffset={offsetInner}
            strokeLinecap="round"
            filter={`url(#glow-inner-${filterId})`}
            className={`transition-[stroke-dashoffset] duration-700 ease-out ${isFailed ? "cf-ring-error" : ""}`}
          />
          {clipActive && <g className="cf-ring-active"><circle cx={cx} cy={cy - rInner} r="5" fill="#c084fc" filter={`url(#glow-inner-${filterId})`} /></g>}
        </svg>

        {/* Dancing Mascot Centered Inside the Rings */}
        <div className="absolute inset-0 flex items-center justify-center">
          <AnimeMascot
            stage={currentStage}
            isProcessing={isProcessing && !isStalled && !isFailed}
          />
        </div>
      </div>

      {/* Ring Legend & Status Badges */}
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3 sm:gap-6">
        {/* Outer Ring Tag */}
        <div role="progressbar" aria-label={`Source processing: ${phaseLabel(pSource, sourceActive)}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pSource >= 100 ? 100 : undefined} aria-valuetext={phaseLabel(pSource, sourceActive)} className="flex items-center gap-2 rounded-xl border border-purple-500/25 bg-purple-950/30 px-3.5 py-1.5 backdrop-blur-md">
          <span className="h-2.5 w-2.5 rounded-full bg-gradient-to-r from-purple-400 to-indigo-500 shadow-[0_0_8px_#a855f7]" />
          <span className="text-xs font-medium text-purple-200">Outer: Source</span>
          <span className="font-mono text-[10px] font-semibold text-purple-300">{phaseLabel(pSource, sourceActive)}</span>
        </div>

        {/* Middle Ring Tag */}
        <div role="progressbar" aria-label={`AI analysis: ${phaseLabel(pAi, aiActive)}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pAi >= 100 ? 100 : undefined} aria-valuetext={phaseLabel(pAi, aiActive)} className="flex items-center gap-2 rounded-xl border border-cyan-500/25 bg-cyan-950/30 px-3.5 py-1.5 backdrop-blur-md">
          <span className="h-2.5 w-2.5 rounded-full bg-gradient-to-r from-cyan-400 to-blue-500 shadow-[0_0_8px_#06b6d4]" />
          <span className="text-xs font-medium text-cyan-200">Middle: AI Analysis</span>
          <span className="font-mono text-[10px] font-semibold text-cyan-300">{phaseLabel(pAi, aiActive)}</span>
        </div>

        {/* Inner Ring Tag */}
        <div role="progressbar" aria-label={`Clip generation: ${phaseLabel(pClip, clipActive)}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pClip >= 100 ? 100 : undefined} aria-valuetext={phaseLabel(pClip, clipActive)} className="flex items-center gap-2 rounded-xl border border-purple-500/25 bg-purple-950/30 px-3.5 py-1.5 backdrop-blur-md">
          <span className="h-2.5 w-2.5 rounded-full bg-gradient-to-r from-emerald-400 to-lime-400 shadow-[0_0_8px_#10b981]" />
          <span className="text-xs font-medium text-emerald-200">Inner: Clips</span>
          <span className="font-mono text-[10px] font-semibold text-purple-300">{phaseLabel(pClip, clipActive)}</span>
        </div>
      </div>
    </div>
  );
}
