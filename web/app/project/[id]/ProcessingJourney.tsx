"use client";

import { useEffect, useMemo, useState } from "react";

type JobState = { id: string; status: string; progress: number; error?: string | null };
const stages = [
  { key: "DOWNLOADING", title: "Retrieving the selected segment", detail: "Fetching the confirmed time range from the source provider.", icon: "↓" },
  { key: "INGESTING", title: "Preparing the selected segment", detail: "Rechecking source duration and validating the confirmed range.", icon: "◫" },
  { key: "TRANSCRIBING", title: "Transcribing the selected range", detail: "Creating timestamped transcript chunks within the selected interval.", icon: "≋" },
  { key: "ANALYZING", title: "Finding moments in the range", detail: "Examining only the selected interval for potential highlights.", icon: "✳" },
  { key: "EDITING", title: "Scoring the clips", detail: "Ranking candidate moments and removing overlapping duplicates.", icon: "⌁" },
  { key: "RENDERING", title: "Finishing the output", detail: "Rendering the requested media output.", icon: "▣" },
];
const statusStage: Record<string, number> = { QUEUED: -1, RETRYING: -1, DOWNLOADING: 0, INGESTING: 1, TRANSCRIBING: 2, ANALYZING: 3, EDITING: 4, RENDERING: 5, READY: 6, FAILED: 0, CANCELLED: 0 };

export default function ProcessingJourney({ projectId, jobId, initialStatus, initialProgress }: { projectId: string; jobId: string; initialStatus: string; initialProgress: number }) {
  const [job, setJob] = useState<JobState>({ id: jobId, status: initialStatus, progress: initialProgress ?? 0 });
  const [lastUpdate, setLastUpdate] = useState(0);
  useEffect(() => {
    let stopped = false;
    const refresh = async () => {
      try {
        const response = await fetch(`/api/projects/${projectId}`, { cache: "no-store" });
        if (!response.ok) return;
        const data = await response.json();
        const latest = Array.isArray(data.jobs) ? data.jobs[0] : null;
        if (!stopped && latest) { setJob({ id: latest.id, status: latest.status, progress: Number(latest.progress ?? 0), error: latest.error ?? null }); setLastUpdate(Date.now()); }
      } catch { /* Keep the last confirmed state if a poll fails. */ }
    };
    void refresh();
    const timer = window.setInterval(refresh, 2500);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [projectId, jobId]);
  const activeIndex = statusStage[job.status] ?? -1;
  const progress = Math.max(0, Math.min(100, job.progress <= 1 ? job.progress * 100 : job.progress));
  const terminal = ["READY", "FAILED", "CANCELLED"].includes(job.status);
  const headline = job.status === "QUEUED" ? "Your video is in line" : job.status === "RETRYING" ? "Picking up where we left off" : job.status === "READY" ? "Your clips are ready" : job.status === "FAILED" ? "Processing hit a problem" : job.status === "CANCELLED" ? "Analysis cancelled" : (stages[activeIndex]?.title ?? "Processing your video");
  const description = job.status === "QUEUED" ? "Your job is waiting for a worker. The journey will update as soon as processing starts." : job.status === "FAILED" ? (job.error || "The job failed. Check the worker and AI service logs for details.") : job.status === "CANCELLED" ? "This job was cancelled." : job.status === "READY" ? "The backend marked this job complete. Your results are available below." : (stages[activeIndex]?.detail ?? "The worker is preparing your video.");
  const elapsed = useMemo(() => new Date(lastUpdate).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }), [lastUpdate]);
  return (
    <section className="cf-processing mt-6 overflow-hidden rounded-3xl border border-white/[.09] bg-[#0d1015]">
      <div className="relative border-b border-white/[.07] px-5 py-5 sm:px-7">
        <div className="cf-processing-orbit pointer-events-none absolute right-8 top-1/2 hidden h-24 w-24 -translate-y-1/2 rounded-full border border-[#39ff14]/20 sm:block"><span className="cf-processing-dot absolute left-1/2 top-0 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#39ff14] shadow-[0_0_18px_rgba(57,255,20,.85)]"/><span className="absolute inset-3 rounded-full border border-[#20c96b]/20"/><span className="absolute inset-[30px] rounded-full bg-[#39ff14]/10"/></div>
        <div className="text-[10px] font-bold uppercase tracking-[.22em] text-[#39ff14]">Live processing journey</div>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-3 sm:pr-28"><div><h2 className="text-xl font-semibold tracking-tight text-white">{headline}</h2><p className="mt-1 max-w-2xl text-xs leading-5 text-zinc-400">{description}</p></div><div className="rounded-xl border border-white/[.08] bg-white/[.03] px-3 py-2"><div className="text-[10px] text-zinc-500">Backend progress</div><div className="mt-0.5 text-lg font-semibold tabular-nums text-white">{Math.round(progress)}%</div></div></div>
        <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-white/[.07]"><div className={`h-full rounded-full bg-gradient-to-r from-[#39ff14] to-[#20c96b] transition-[width] duration-700 ${!terminal && job.status !== "QUEUED" ? "cf-processing-bar" : ""}`} style={{ width: `${job.status === "READY" ? 100 : progress}%` }}/></div>
        <div className="mt-2 flex justify-between text-[10px] text-zinc-600"><span>{job.status.replaceAll("_", " ")}</span><span>Last confirmed update · {elapsed}</span></div>
      </div>
      <div className="grid gap-2 p-4 sm:grid-cols-2 sm:p-5 lg:grid-cols-3">
        {stages.map((stage, index) => {
          const complete = activeIndex > index || job.status === "READY";
          const current = activeIndex === index && !terminal;
          return <div key={stage.key} className={`relative rounded-2xl border p-4 transition-colors duration-300 ${complete ? "border-[#39ff14]/20 bg-[#39ff14]/[.045]" : current ? "cf-processing-active border-[#20c96b]/35 bg-[#20c96b]/[.055]" : "border-white/[.06] bg-white/[.015]"}`}>
            <div className="flex items-center gap-3"><div className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl border text-lg ${complete ? "border-[#39ff14]/25 bg-[#39ff14]/10 text-[#b2ff9b]" : current ? "border-[#20c96b]/30 bg-[#20c96b]/10 text-[#a4efbd]" : "border-white/10 bg-white/[.025] text-zinc-500"}`}>{complete ? "✓" : stage.icon}</div><div className="min-w-0"><div className="text-[10px] uppercase tracking-[.15em] text-zinc-600">Step {index + 1}</div><div className={`mt-0.5 text-sm font-medium ${complete ? "text-[#d7ffd0]" : current ? "text-white" : "text-zinc-400"}`}>{stage.title}</div></div></div>
            <p className="mt-3 text-xs leading-5 text-zinc-500">{stage.detail}</p>
            <div className="mt-3 flex items-center gap-2 text-[10px] font-medium">{complete ? <span className="text-[#39ff14]">Completed</span> : current ? <><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#20c96b]"/><span className="text-[#a4efbd]">In progress</span></> : <span className="text-zinc-600">Up next</span>}</div>
          </div>;
        })}
      </div>
      {job.status === "FAILED" && <div role="alert" className="mx-4 mb-4 rounded-xl border border-red-300/20 bg-red-300/[.04] p-3 text-xs text-red-200 sm:mx-5">{job.error || "No error message was returned by the job API."}</div>}
      <style jsx>{`
        .cf-processing-orbit { animation: orbit 9s linear infinite; }
        .cf-processing-dot { animation: pulse 1.8s ease-in-out infinite; }
        .cf-processing-active { animation: breathe 2.4s ease-in-out infinite; }
        .cf-processing-bar { background-size: 200% 100%; animation: shimmer 2.4s linear infinite; }
        @keyframes orbit { to { transform: translateY(-50%) rotate(360deg); } }
        @keyframes pulse { 50% { opacity: .35; box-shadow: 0 0 4px rgba(57,255,20,.22); } }
        @keyframes breathe { 50% { border-color: rgba(125,211,252,.65); } }
        @keyframes shimmer { to { background-position: -200% 0; } }
        @media (prefers-reduced-motion: reduce) { .cf-processing-orbit,.cf-processing-dot,.cf-processing-active,.cf-processing-bar { animation: none; } }
      `}</style>
    </section>
  );
}
