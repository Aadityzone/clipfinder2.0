import Link from "next/link";
import { requireUser } from "../../../lib/auth";
import { db } from "../../../lib/db";
import Editor from "./Editor";
import ProcessingJourney from "./ProcessingJourney";

function time(s: number) { return new Date(s * 1000).toISOString().slice(11, 19); }
function stateClass(status: string) {
  if (status === "READY") return "border-emerald-400/20 bg-emerald-400/[.08] text-emerald-300";
  if (status === "FAILED") return "border-red-400/20 bg-red-400/[.08] text-red-300";
  return "border-[#39ff14]/20 bg-[#39ff14]/[.07] text-[#b2ff9b]";
}

export default async function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const user = await requireUser();
  const { id } = await params;
  const project = await db.project.findFirst({ where: { id, userId: user.id }, include: { source: { include: { media: true } }, jobs: { orderBy: { createdAt: "desc" }, take: 8 }, clips: { orderBy: { score: "desc" }, include: { edit: true, highlight: true } } } });
  if (!project) return <main className="min-h-screen bg-[#080a08] p-8 text-white"><div className="mx-auto max-w-3xl cf-card p-8"><p className="cf-kicker">Project unavailable</p><h1 className="mt-3 text-2xl font-semibold">We couldn&apos;t find this project.</h1><p className="mt-2 text-sm text-zinc-500">It may have been removed or belong to another account.</p><Link href="/dashboard" className="cf-button mt-6">Back to workspace</Link></div></main>;
  const asset = project.source?.media[0] ?? null;
  const ingest = await db.job.findFirst({ where: { projectId: project.id, userId: user.id, type: { in: ["INGEST", "TRANSCRIBE"] } }, orderBy: { createdAt: "asc" }, select: { payload: true } });
  const ingestPayload = ingest?.payload && typeof ingest.payload === "object" ? ingest.payload as Record<string, unknown> : {};
  const selectedRange = ingestPayload.sourceRange && typeof ingestPayload.sourceRange === "object" ? ingestPayload.sourceRange as { startSeconds?: number; endSeconds?: number } : null;
  const sourceDuration = Number(ingestPayload.sourceDurationS || asset?.durationS || 0);
  const sourceOffset = ingestPayload.rangeLimitedDownload && selectedRange ? Number(selectedRange.startSeconds || 0) : 0;
  const active = project.jobs.some(j => !["READY", "FAILED", "CANCELLED"].includes(j.status));
  const latest = project.jobs[0];
  return <main className="min-h-screen bg-[#080a08] px-4 pb-12 text-white sm:px-6">
    <header className="mx-auto flex max-w-[1500px] items-center justify-between border-b border-white/[.07] py-5"><Link href="/dashboard" className="inline-flex items-center gap-2 text-sm text-zinc-400 transition hover:text-white">← <span>Workspace</span></Link><Link href="/" className="font-semibold tracking-tight">clip<span className="text-[#39ff14]">finder</span><span className="ml-1 text-[10px] text-zinc-600">2.0</span></Link><Link href={"/project/"+project.id+"/long-form"} className="cf-button-secondary !min-h-9 !rounded-[10px] !px-3 text-xs">Long-form workspace ↗</Link></header>
    <div className="mx-auto max-w-[1500px] pt-8">
      <div className="cf-enter flex flex-col justify-between gap-5 xl:flex-row xl:items-end"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="cf-kicker">Project workspace</span><span className={`rounded-full border px-2.5 py-1 text-[10px] ${stateClass(latest?.status ?? "READY")}`}>{(latest?.status ?? "READY").replaceAll("_"," ")}</span></div><h1 className="mt-3 break-words text-3xl font-semibold tracking-[-.045em] sm:text-4xl">{project.name}</h1><p className="mt-2 max-w-3xl truncate text-sm text-zinc-500">{project.source?.url ?? project.source?.name ?? "Uploaded source"}{sourceDuration ? " · source " + time(sourceDuration) : ""}</p>{selectedRange && <p className="mt-2 text-xs text-[#b2ff9b]">Analyzed source range {time(Number(selectedRange.startSeconds || 0))}–{time(Number(selectedRange.endSeconds || 0))}</p>}</div><div className="flex flex-wrap gap-2"><span className="rounded-xl border border-white/[.08] bg-white/[.025] px-3 py-2 text-xs text-zinc-400">{project.mode === "SHORTS" ? "Vertical shorts" : "Long form"}</span><span className="rounded-xl border border-white/[.08] bg-white/[.025] px-3 py-2 text-xs text-zinc-400">Transcript: {project.outputLanguage.toUpperCase()}</span></div></div>
      {active && latest && <ProcessingJourney projectId={project.id} jobId={latest.id} initialStatus={latest.status} initialProgress={latest.progress} /> }
      {latest?.status === "FAILED" && <div role="alert" className="mt-6 rounded-2xl border border-red-400/20 bg-red-400/[.05] p-4"><div className="text-sm font-medium text-red-200">Processing needs attention</div><p className="mt-1 break-words text-xs text-red-200/70">{latest.error || "The latest job failed without a recorded error. Check the worker logs before retrying."}</p></div>}
      <div className="mt-7 grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <section className="min-w-0"><div className="mb-3 flex items-center justify-between"><div><h2 className="text-sm font-semibold">Clip editor</h2><p className="mt-1 text-xs text-zinc-600">Review candidates and adjust the final cut.</p></div><span className="rounded-lg border border-white/[.08] px-2.5 py-1.5 text-[10px] text-zinc-500">{project.clips.length} candidates</span></div>
          {asset && project.clips.length > 0 ? <div className="overflow-hidden rounded-2xl border border-white/[.08] bg-[#0d1117] p-2 sm:p-4"><Editor projectId={project.id} mediaId={asset.id} duration={asset.durationS ?? 0} sourceOffset={sourceOffset} sourceDuration={sourceDuration} clips={project.clips.map(c => ({ ...c, edit: c.edit ? { ...c.edit, segments: c.edit.segments as any } : null }))}/></div> : <div className="cf-card flex min-h-[320px] flex-col items-center justify-center px-6 py-12 text-center"><div className="grid h-14 w-14 place-items-center rounded-2xl border border-white/10 bg-white/[.025] text-2xl text-[#39ff14]">{asset ? "◷" : "↑"}</div><h2 className="mt-5 text-lg font-semibold">{asset ? "Waiting for clip candidates" : "Waiting for source media"}</h2><p className="mt-2 max-w-md text-sm leading-6 text-zinc-500">{asset ? "Media is attached, but no real candidates are available yet. Check the job status and worker logs if this state persists." : "The source needs to be ingested before the editor can load a preview or timeline."}</p><div className="mt-5 flex flex-wrap justify-center gap-2"><Link href="/dashboard" className="cf-button-secondary">Back to projects</Link><Link href="/project/new" className="cf-button">Add another source ↗</Link></div></div>}
        </section>
        <aside className="space-y-4"><div className="cf-card p-5"><div className="text-xs text-zinc-500">Source details</div><div className="mt-4 space-y-4">{[{label:"Source type",value:project.source?.type ?? "Not attached"},{label:"Duration",value:asset?.durationS ? time(asset.durationS) : "Pending probe"},{label:"Resolution",value:asset?.width && asset?.height ? `${asset.width} × ${asset.height}` : "Not available"},{label:"Audio track",value:asset?.hasAudio == null ? "Not checked" : asset.hasAudio ? "Detected" : "No audio detected"}].map(x=><div key={x.label} className="flex items-start justify-between gap-4 border-b border-white/[.06] pb-3 last:border-0 last:pb-0"><span className="text-xs text-zinc-600">{x.label}</span><span className="max-w-[150px] break-words text-right text-xs text-zinc-300">{x.value}</span></div>)}</div></div>
          <div className="cf-card p-5"><div className="text-xs text-zinc-500">Processing activity</div>{project.jobs.length ? <div className="mt-4 space-y-4">{project.jobs.map((job,i)=><div key={job.id} className="flex gap-3"><div className={`mt-1 h-2 w-2 shrink-0 rounded-full ${i===0 && active ? "animate-pulse bg-[#39ff14]" : "bg-zinc-600"}`}/><div className="min-w-0"><div className="text-xs font-medium">{job.type.replaceAll("_"," ")}</div><div className="mt-1 text-[10px] text-zinc-600">{job.status.replaceAll("_"," ")} · {new Date(job.createdAt).toLocaleString("en-IN",{dateStyle:"medium",timeStyle:"short"})}</div></div></div>)}</div> : <p className="mt-3 text-xs text-zinc-600">No jobs recorded for this project.</p>}</div>
          <div className="rounded-2xl border border-white/[.07] bg-white/[.015] p-4"><div className="text-xs font-semibold">A quick reminder</div><p className="mt-2 text-xs leading-5 text-zinc-500">AI scores are suggestions, not a replacement for your editorial judgment. Preview every clip before exporting.</p></div>
        </aside>
      </div>
    </div>
  </main>;
}
