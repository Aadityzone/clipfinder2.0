"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import ConcentricProcessingRings from "./ConcentricProcessingRings";
import { formatTimeOnly, type ProjectProcessingState } from "../lib/processing-types";

interface ProcessingWorkspaceProps {
  projectId: string;
  initialState?: ProjectProcessingState | null;
  onCompleted?: () => void;
}

interface PhaseItem {
  label: string;
  value: number | undefined;
  tone: string;
  text: string;
  match: RegExp;
}

function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return "--:--";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatElapsed(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export default function ProcessingWorkspace({
  projectId,
  initialState = null,
  onCompleted,
}: ProcessingWorkspaceProps) {
  const router = useRouter();
  const [state, setState] = useState<ProjectProcessingState | null>(initialState);
  const [loading, setLoading] = useState(!initialState);
  const [showTechnical, setShowTechnical] = useState(false);
  const [showActivity, setShowActivity] = useState(true);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [connection, setConnection] = useState<"connecting" | "connected" | "reconnecting" | "stale">(initialState ? "connected" : "connecting");
  const [connectionError, setConnectionError] = useState("");
  const [lastConfirmedAt, setLastConfirmedAt] = useState<number | null>(null);
  const consecutiveErrors = useRef(0);
  const [elapsedTime, setElapsedTime] = useState(initialState?.elapsedMs || 0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const isPollingRef = useRef<boolean>(true);

  // Live timer tick for smooth elapsed time count
  useEffect(() => {
    if (state?.isTerminal) return;
    const interval = setInterval(() => {
      setElapsedTime((prev) => prev + 1000);
    }, 1000);
    return () => clearInterval(interval);
  }, [state?.isTerminal]);

  // Fetch updated status from /api/projects/[id]/status
  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`/api/projects/${projectId}/status`, {
        cache: "no-store",
        headers: { "Cache-Control": "no-cache" },
      });
      if (!res.ok) throw new Error(res.status === 401 ? "Your session expired. Sign in again to keep monitoring this project." : `Status request returned ${res.status}.`);
      const data: ProjectProcessingState = await res.json();
      setState(data);
      setLoading(false);
      setElapsedTime(data.elapsedMs);
      consecutiveErrors.current = 0;
      setConnection("connected");
      setConnectionError("");
      setLastConfirmedAt(Date.now());

      // Check if job transitioned to READY
      if (data.status === "READY") {
        isPollingRef.current = false;
        if (onCompleted) {
          onCompleted();
        } else {
          // Single refresh to let parent page render the ready editor
          router.refresh();
        }
      } else if (data.isTerminal) {
        isPollingRef.current = false;
      }
    } catch (err) {
      console.warn("[ProcessingWorkspace] Status poll error:", err);
      consecutiveErrors.current += 1;
      setConnection(consecutiveErrors.current >= 4 ? "stale" : "reconnecting");
      setConnectionError(err instanceof Error ? err.message : "Connection interrupted. Retrying automatically.");
    }
  }, [projectId, onCompleted, router]);

  // Adaptive Polling Lifecycle
  useEffect(() => {
    isPollingRef.current = true;
    const initialPoll = window.setTimeout(() => { void fetchStatus(); }, 0);

    const scheduleNextPoll = () => {
      if (!isPollingRef.current) return;

      // Determine interval based on state and tab visibility
      let delay = 2000;
      if (typeof document !== "undefined" && document.visibilityState === "hidden") {
        delay = 12000; // Throttle when tab is backgrounded
      } else if (state?.status === "QUEUED") {
        delay = 3500;
      } else if (state?.status === "STALLED") {
        delay = 4000;
      } else if (state?.status === "PROCESSING") {
        delay = 1800;
      }
      if (connection !== "connected") delay = Math.min(2500 * (2 ** Math.min(consecutiveErrors.current, 4)), 30000);

      timerRef.current = setTimeout(async () => {
        if (!isPollingRef.current) return;
        await fetchStatus();
        scheduleNextPoll();
      }, delay);
    };

    scheduleNextPoll();

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible" && isPollingRef.current) {
        fetchStatus();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      isPollingRef.current = false;
      clearTimeout(initialPoll);
      if (timerRef.current) clearTimeout(timerRef.current);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [fetchStatus, state?.status, connection]);

  // Action: Retry job
  const handleRetry = async () => {
    if (!state?.activeJobId || actionBusy) return;
    setActionError("");
    setActionBusy(true);
    try {
      const res = await fetch(`/api/jobs/${state.activeJobId}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action: "retry" }),
      });
      if (res.ok) {
        isPollingRef.current = true;
        await fetchStatus();
      } else {
        const body = await res.json().catch(() => ({}));
        setActionError(body.error || `Retry request returned ${res.status}.`);
      }
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Could not retry processing.");
    } finally {
      setActionBusy(false);
    }
  };

  // Action: Cancel job
  const handleCancel = async () => {
    if (!state?.activeJobId || actionBusy) return;
    setActionError("");
    setActionBusy(true);
    try {
      const res = await fetch(`/api/jobs/${state.activeJobId}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action: "cancel" }),
      });
      if (res.ok) {
        await fetchStatus();
      } else {
        const body = await res.json().catch(() => ({}));
        setActionError(body.error || `Cancel request returned ${res.status}.`);
      }
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Could not cancel processing.");
    } finally {
      setActionBusy(false);
    }
  };

  // Tone badge for status
  const getStatusBadge = () => {
    const s = state?.status || "QUEUED";
    switch (s) {
      case "PROCESSING":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-cyan-400/30 bg-cyan-950/40 px-3 py-1 text-xs font-semibold text-cyan-300">
            <span className="h-2 w-2 animate-pulse rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
            AI Processing Active
          </span>
        );
      case "QUEUED":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/30 bg-amber-950/40 px-3 py-1 text-xs font-semibold text-amber-300">
            <span className="h-2 w-2 animate-ping rounded-full bg-amber-400" />
            Queued · Waiting for Worker
          </span>
        );
      case "STALLED":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-500/30 bg-rose-950/40 px-3 py-1 text-xs font-semibold text-rose-300">
            <span className="h-2 w-2 rounded-full bg-rose-500" />
            Worker Unresponsive
          </span>
        );
      case "RETRYING":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-purple-400/30 bg-purple-950/40 px-3 py-1 text-xs font-semibold text-purple-300">
            <span className="h-2 w-2 animate-spin rounded-full border-2 border-purple-400 border-t-transparent" />
            Retrying Milestone...
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-red-500/30 bg-red-950/40 px-3 py-1 text-xs font-semibold text-red-300">
            <span className="h-2 w-2 rounded-full bg-red-500" />
            Processing Failed
          </span>
        );
      case "READY":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/30 bg-emerald-950/40 px-3 py-1 text-xs font-semibold text-emerald-300">
            <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
            100% Ready
          </span>
        );
      default:
        return null;
    }
  };

  const isFailed = state?.status === "FAILED";
  const isStalled = state?.status === "STALLED";
  const isQueued = state?.status === "QUEUED";

  return (
    <div className="relative mx-auto max-w-[1200px] space-y-8 px-2 py-6 sm:px-4">
      {/* Background Deep Purple / Black Cyber Glow */}
      <div
        className="pointer-events-none absolute -top-24 left-1/2 -z-10 h-[500px] w-[700px] -translate-x-1/2 rounded-full bg-gradient-to-b from-purple-900/20 via-cyan-900/10 to-transparent blur-3xl"
        aria-hidden="true"
      />

      {/* Hero Section: Concentric Rings & Dancing Mascot */}
      <div className="flex flex-col items-center justify-center pt-2">
        <ConcentricProcessingRings
          sourceProgress={state?.sourceProgress ?? 0}
          aiProgress={state?.aiProgress ?? 0}
          clipProgress={state?.clipProgress ?? 0}
          currentStage={state?.stageLabel || "Initializing"}
          isProcessing={state?.status === "PROCESSING"}
          isStalled={isStalled}
          isFailed={isFailed}
        />
      </div>

      {/* Main Status & Diagnosis Card */}
      <div className="rounded-3xl border border-white/[.08] bg-[#0d0f17]/90 p-6 shadow-2xl backdrop-blur-xl sm:p-8">
        <div className="flex flex-col items-start justify-between gap-4 border-b border-white/[.07] pb-6 sm:flex-row sm:items-center">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-[11px] font-bold uppercase tracking-widest text-cyan-400">
                PROCESSING WORKSPACE
              </span>
              {getStatusBadge()}
              <span role="status" className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] ${connection === "connected" ? "border-emerald-400/20 bg-emerald-950/30 text-emerald-200" : "border-amber-300/20 bg-amber-950/30 text-amber-200"}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${connection === "connected" ? "bg-emerald-300" : "bg-amber-300"}`} />
                {connection === "connected" ? "Live updates" : connection === "stale" ? "Status is stale" : connection === "connecting" ? "Connecting" : "Reconnecting"}
              </span>
            </div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
              {state?.diagnosis || "Preparing pipeline..."}
            </h2>
            <p className="mt-1.5 max-w-2xl text-sm leading-6 text-zinc-400">
              {state?.diagnosisSubtext || "Analyzing source video to generate timecoded short clips."}
            </p>
          </div>

          {/* Action buttons (Retry / Cancel) */}
          <div className="flex flex-wrap gap-2.5">
            {state?.canRetry && (
              <button
                onClick={handleRetry}
                disabled={actionBusy}
                className="cf-button !min-h-10 !rounded-xl !bg-purple-600 !px-5 text-xs font-semibold text-white hover:!bg-purple-500 shadow-[0_0_15px_rgba(168,85,247,0.3)]"
              >
                {actionBusy ? "Retrying..." : "↺ Resume / Retry"}
              </button>
            )}
            {!state?.isTerminal && (
              <button
                onClick={handleCancel}
                disabled={actionBusy}
                className="cf-button-secondary !min-h-10 !rounded-xl !px-4 text-xs hover:border-red-500/30 hover:text-red-300"
              >
                Cancel
              </button>
            )}
          </div>
        </div>
        {connectionError && <div role="status" aria-live="polite" className="mt-4 rounded-xl border border-amber-300/15 bg-amber-300/[.04] px-4 py-3 text-xs text-amber-100/90">{connectionError}<span className="ml-2 text-[10px] text-zinc-500">Last confirmed {lastConfirmedAt ? new Date(lastConfirmedAt).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "not yet"} · retrying automatically</span></div>}
        {actionError && <div role="alert" className="mt-3 rounded-xl border border-rose-300/15 bg-rose-300/[.04] px-4 py-3 text-xs text-rose-100/90">{actionError}</div>}
        {loading && <p role="status" className="mt-3 text-xs text-zinc-500">Loading the latest persisted processing state…</p>}

        {/* Informational Guidance for Queued & Stalled States */}
        {isQueued && (
          <div className="mt-6 rounded-2xl border border-amber-500/20 bg-amber-950/20 p-4">
            <div className="flex items-start gap-3">
              <span className="grid h-6 w-6 place-items-center rounded-lg bg-amber-500/20 text-sm font-bold text-amber-300">
                !
              </span>
              <div className="text-xs text-amber-200">
                <p className="font-semibold">Worker queue notice</p>
                <p className="mt-1 leading-5 text-amber-200/80">
                  This project is waiting for an available background worker process to claim it.
                  If running locally, ensure the queue worker is active by running{" "}
                  <code className="rounded bg-black/40 px-1.5 py-0.5 font-mono text-[11px] text-amber-300">
                    npm run worker
                  </code>{" "}
                  in the project terminal.
                </p>
              </div>
            </div>
          </div>
        )}

        {isStalled && (
          <div className="mt-6 rounded-2xl border border-rose-500/25 bg-rose-950/25 p-4">
            <div className="flex items-start gap-3">
              <span className="grid h-6 w-6 place-items-center rounded-lg bg-rose-500/20 text-sm font-bold text-rose-300">
                ⚠
              </span>
              <div className="text-xs text-rose-200">
                <p className="font-semibold">Worker heartbeat paused</p>
                <p className="mt-1 leading-5 text-rose-200/80">
                  The processing worker has stopped responding. All previously completed stages and source
                  downloads have been durably preserved. Click &quot;Resume / Retry&quot; above to re-engage processing.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Compact phase summaries mirror the three rings above. */}
        <div className="mt-6 grid gap-3 sm:grid-cols-3" aria-label="Processing phase progress">
          {([
            { label: "Source preparation", value: state?.sourceProgress, tone: "bg-violet-400", text: "text-violet-200", match: /source|download|ingest|probe|media prep|extract/ },
            { label: "AI intelligence", value: state?.aiProgress, tone: "bg-sky-400", text: "text-sky-200", match: /transcrib|analys|rank|whisper|audio|visual|candidate/ },
            { label: "Clip generation", value: state?.clipProgress, tone: "bg-fuchsia-400", text: "text-fuchsia-200", match: /render|clip output|candidate/ },
          ] as PhaseItem[]).map((phase: PhaseItem) => {
            const confirmed = Number.isFinite(phase.value) && Number(phase.value) >= 100;
            const stageText = `${state?.stage ?? ""} ${state?.stageLabel ?? ""}`.toLowerCase();
            const atStage = phase.match.test(stageText);
            const inProgress = !confirmed && ["PROCESSING", "STALLED"].includes(state?.status ?? "") && atStage;
            const phaseStatus = state?.status === "FAILED" ? "Failed" : state?.status === "STALLED" && inProgress ? "Paused · \u2014" : confirmed ? "Complete · 100%" : inProgress ? "Working · \u2014" : "Waiting · \u2014";
            return <div key={phase.label} className="rounded-2xl border border-white/[.07] bg-black/25 px-4 py-3" role="progressbar" aria-label={`${phase.label}: ${phaseStatus}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={confirmed ? 100 : undefined} aria-valuetext={phaseStatus}>
              <div className="flex items-center justify-between gap-2"><span className="text-[11px] font-medium text-zinc-300">{phase.label}</span><span className={`font-mono text-[10px] ${phase.text}`}>{phaseStatus}</span></div>
              <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/[.07]"><div className={`h-full rounded-full ${confirmed ? phase.tone : ""} ${inProgress ? `cf-progress-indeterminate ${phase.text}` : ""} transition-[width] duration-700`} style={{ width: confirmed ? "100%" : undefined }}/></div>
            </div>;
          })}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[10px] text-zinc-500"><span>Source length <strong className="ml-1 font-mono text-zinc-300">{formatDuration(state?.sourceDurationS || 0)}</strong></span><span>Elapsed <strong className="ml-1 font-mono text-zinc-300">{formatElapsed(elapsedTime)}</strong></span><span>Candidates <strong className="ml-1 font-mono text-emerald-300">{state?.candidatesFound ?? 0}</strong></span><span>Clips ready <strong className="ml-1 font-mono text-zinc-300">{state?.completedClips ?? 0}</strong></span><span className="ml-auto">Worker <strong className="ml-1 font-mono text-violet-200">{state?.technicalDetails.workerStatus ?? "waiting"}</strong></span></div>

        {/* Live Processing Activity Panel (Requirement 2) */}
        <div className="mt-8 rounded-2xl border border-white/[.06] bg-black/40 p-5">
          <button type="button" onClick={() => setShowActivity(value => !value)} aria-expanded={showActivity} className="flex w-full items-center justify-between border-b border-white/[.07] pb-3 text-left">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
                Live Processing Activity
              </h3>
            </div>
            <span className="text-[10px] text-zinc-500">{showActivity ? "Hide activity" : "Show activity"}</span>
          </button>

          {showActivity && <div className="mt-4 max-h-56 space-y-3 overflow-y-auto pr-1">
            {state?.activity && state.activity.length > 0 ? (
              state.activity.map((ev, idx) => (
                <div key={idx} className="flex items-start gap-3 text-xs">
                  <span className="shrink-0 font-mono text-[11px] text-cyan-400/80">
                    {formatTimeOnly(ev.timestamp)}
                  </span>
                  <span className="text-zinc-600">—</span>
                  <span className="text-zinc-300 leading-5">{ev.message}</span>
                </div>
              ))
            ) : (
              <div className="py-4 text-center text-xs text-zinc-600">
                Initializing activity stream...
              </div>
            )}
          </div>}
        </div>

        {/* Expandable Technical Details (Requirement 2) */}
        <div className="mt-6 border-t border-white/[.07] pt-4">
          <button
            onClick={() => setShowTechnical((prev) => !prev)}
            className="flex items-center gap-2 text-xs font-medium text-zinc-400 transition hover:text-white"
            aria-expanded={showTechnical}
          >
            <span>{showTechnical ? "▾ Hide" : "▸ Show"} technical details & worker diagnosis</span>
          </button>

          {showTechnical && (
            <div className="mt-4 space-y-3 rounded-2xl border border-white/[.06] bg-black/30 p-4 font-mono text-xs">
              <div className="flex justify-between border-b border-white/[.04] pb-2">
                <span className="text-zinc-500">Active Job ID</span>
                <span className="text-zinc-300">{state?.technicalDetails.jobId || "None"}</span>
              </div>
              <div className="flex justify-between border-b border-white/[.04] pb-2">
                <span className="text-zinc-500">Job Type</span>
                <span className="text-zinc-300">{state?.technicalDetails.jobType || "None"}</span>
              </div>
              <div className="flex justify-between border-b border-white/[.04] pb-2">
                <span className="text-zinc-500">Worker Status</span>
                <span className="capitalize text-zinc-300">
                  {state?.technicalDetails.workerStatus || "unknown"}
                </span>
              </div>
              <div className="flex justify-between border-b border-white/[.04] pb-2">
                <span className="text-zinc-500">Last Heartbeat</span>
                <span className="text-zinc-300">
                  {state?.technicalDetails.lastHeartbeat
                    ? `${formatTimeOnly(state.technicalDetails.lastHeartbeat)} (${Math.round((state.technicalDetails.heartbeatAgeMs || 0) / 1000)}s ago)`
                    : "No heartbeat yet"}
                </span>
              </div>
              <div className="flex justify-between border-b border-white/[.04] pb-2">
                <span className="text-zinc-500">Retry Count</span>
                <span className="text-zinc-300">
                  {state?.technicalDetails.retryCount ?? 0} / 3 attempts
                </span>
              </div>
              <div className="flex justify-between border-b border-white/[.04] pb-2">
                <span className="text-zinc-500">Current Processing Stage</span>
                <span className="text-zinc-300">
                  {state?.technicalDetails.currentStage || "QUEUED"}
                </span>
              </div>
              <div className="flex justify-between border-b border-white/[.04] pb-2">
                <span className="text-zinc-500">Last Completed Checkpoint</span>
                <span className="text-zinc-300">
                  {state?.technicalDetails.lastCheckpoint || "None"}
                </span>
              </div>
              {state?.technicalDetails.error && (
                <div className="pt-2 text-red-300">
                  <span className="block text-zinc-500">Sanitized Error:</span>
                  <p className="mt-1 whitespace-pre-wrap rounded-lg bg-red-950/30 p-2 text-[11px] text-red-200">
                    {state.technicalDetails.error}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
