import Link from "next/link";
import { notFound } from "next/navigation";
import { requireUser } from "../../../lib/auth";
import { db } from "../../../lib/db";
import Editor from "./Editor";

function time(seconds: number) {
  const safe = Math.max(0, Math.floor(seconds));
  return `${Math.floor(safe / 3600).toString().padStart(2, "0")}:${Math.floor((safe % 3600) / 60).toString().padStart(2, "0")}:${(safe % 60).toString().padStart(2, "0")}`;
}
function label(status: string) { return status.toLowerCase().replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase()); }

export default async function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const user = await requireUser();
  const { id } = await params;
  const project = await db.project.findFirst({
    where: { id, userId: user.id },
    include: {
      source: { include: { media: true } },
      jobs: { orderBy: { createdAt: "desc" }, take: 8 },
      clips: { orderBy: { score: "desc" }, include: { edit: true, highlight: true } },
    },
  });
  if (!project) notFound();
  const asset = project.source?.media[0] ?? null;
  const activeJob = project.jobs.find((job) => !["READY", "FAILED", "CANCELLED"].includes(job.status));
  const failedJob = project.jobs.find((job) => job.status === "FAILED");
  return <main className="min-h-screen">
    <header className="sticky top-0 z-20 border-b border-white/[.07] bg-[#080a0e]/90 backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-4 py-3 sm:px-7">
        <div className="flex min-w-0 items-center gap-3"><Link href="/dashboard" className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-white/[.08] text-sm text-[#9ca6b4] transition hover:bg-white/[.05] hover:text-white" aria-label="Back to workspace">←</Link><div className="min-w-0"><p className="truncate text-sm font-semibold">{project.name}</p><p className="mt-0.5 truncate text-[10px] text-[#687383]">{project.mode === "SHORTS" ? "Short-form project" : "Long-form project"} · {project.outputLanguage.toUpperCase()}</p></div></div>
        <div className="flex shrink-0 items-center gap-2"><span className={`hidden rounded-full border px-3 py-1.5 text-[10px] sm:inline-flex ${failedJob ? "border-rose-400/20 bg-rose-400/[.06] text-rose-300" : activeJob ? "border-[#c4f56b]/20 bg-[#c4f56b]/[.06] text-[#c4f56b]" : "border-white/[.08] text-[#9ca6b4]"}`}>{failedJob ? "Processing failed" : activeJob ? label(activeJob.status) : "Current state saved"}</span><Link href={`/project/${id}/long-form`} className="cf-button cf-button-secondary min-h-9 px-3 text-[10px]">Long-form workspace ↗</Link></div>
      </div>
    </header>
    <div className="mx-auto max-w-[1600px] px-4 py-6 sm:px-7 sm:py-8">
      <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="cf-eyebrow">Edit & review</p><h1 className="mt-2 text-2xl font-semibold tracking-[-.05em] sm:text-3xl">Your cut, your call.</h1><p className="mt-2 max-w-2xl text-xs leading-6 text-[#8792a1]">{project.source?.url ?? (asset ? "Uploaded source media" : "Source media is not attached yet.")}{asset?.durationS ? ` · ${time(asset.durationS)} source duration` : ""}</p></div><div className="flex gap-2"><Link href="/exports" className="cf-button cf-button-secondary min-h-9 text-[10px]">View exports</Link><Link href="/project/new" className="cf-button cf-button-primary min-h-9 text-[10px]">＋ New project</Link></div></div>
      {failedJob && <div role="alert" className="mb-5 rounded-2xl border border-rose-400/20 bg-rose-400/[.06] p-4"><p className="text-xs font-semibold text-rose-300">Processing needs attention</p><p className="mt-1 text-xs leading-5 text-[#c2c9d3]">{failedJob.error || "The latest job failed without a detailed error message."}</p><p className="mt-2 text-[10px] text-[#8792a1]">No clips will be shown as complete unless the pipeline actually creates them.</p></div>}
      {activeJob && <div className="mb-5 flex items-start gap-3 rounded-2xl border border-[#c4f56b]/15 bg-[#c4f56b]/[.035] p-4"><span className="mt-1 h-2 w-2 shrink-0 animate-pulse rounded-full bg-[#c4f56b]" /><div><p className="text-xs font-semibold text-[#c4f56b]">Source processing in progress</p><p className="mt-1 text-xs leading-5 text-[#9ca6b4]">Current job: {label(activeJob.status)}. Candidate clips will appear after the processing pipeline persists real results.</p></div></div>}
      {asset && project.clips.length > 0 ? <div className="overflow-hidden rounded-2xl border border-white/[.08] bg-[#0b0e13]"><Editor projectId={project.id} mediaId={asset.id} duration={asset.durationS ?? 0} clips={project.clips.map((clip) => ({ ...clip, edit: clip.edit ? { ...clip.edit, segments: clip.edit.segments as unknown as { startS: number; endS: number }[] } : null }))} /></div> : <div className="cf-panel relative overflow-hidden rounded-3xl p-6 sm:p-10"><div className="cf-glow pointer-events-none absolute -right-10 -top-24 h-72 w-72" /><div className="relative max-w-2xl"><span className="grid h-12 w-12 place-items-center rounded-2xl border border-white/[.09] bg-white/[.03] text-xl text-[#c4f56b]">{failedJob ? "!" : activeJob ? "◷" : "◫"}</span><p className="cf-eyebrow mt-6">{failedJob ? "Pipeline status" : activeJob ? "Analysis in progress" : "Ready for a source"}</p><h2 className="mt-2 text-2xl font-semibold tracking-[-.05em]">{failedJob ? "This run did not finish." : activeJob ? "Finding moments in your actual source." : asset ? "No candidate clips have been saved yet." : "Connect a source to begin."}</h2><p className="mt-3 text-sm leading-7 text-[#8792a1]">{failedJob ? "Review the error above and check the worker and AI service logs. We will not fabricate results to fill this space." : activeJob ? "The workspace will show clips when the pipeline has generated and persisted them. You can safely leave this page and return later." : asset ? "The media exists, but there are no persisted clip candidates to edit yet." : "Create a project from a supported URL or upload a source file. Ingestion, transcription, and analysis must complete before editing can start."}</p>{!asset && <Link href="/project/new" className="cf-button cf-button-primary mt-6">Add a source <span aria-hidden="true">↗</span></Link>}</div></div>}
      <footer className="mt-6 flex flex-col justify-between gap-2 border-t border-white/[.06] pt-4 text-[9px] text-[#687383] sm:flex-row"><span>Project ID: {project.id}</span><span>Only persisted analysis and actual media are shown as results.</span></footer>
    </div>
  </main>;
}
