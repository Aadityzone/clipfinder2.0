import Link from "next/link";
import { requireUser } from "../../../lib/auth";
import { db } from "../../../lib/db";
import { deriveProjectProcessingState } from "../../../lib/job-progress";
import Editor from "./Editor";
import ProcessingExperience from "./ProcessingExperience";
import WorkspaceFrame from "../../../components/WorkspaceFrame";

function time(s: number) { return new Date(s * 1000).toISOString().slice(11, 19); }
function fileSize(bytes: bigint | number | null | undefined) { if (bytes == null) return "Not available"; const value = Number(bytes); return value < 1024 ** 3 ? `${(value / 1024 ** 2).toFixed(1)} MB` : `${(value / 1024 ** 3).toFixed(2)} GB`; }
function stateClass(status: string) {
  if (status === "READY") return "border-emerald-400/20 bg-emerald-400/[.08] text-emerald-300";
  if (status === "FAILED") return "border-red-400/20 bg-red-400/[.08] text-red-300";
  return "border-[#c4f36b]/20 bg-[#c4f36b]/[.07] text-[#d7f9a7]";
}

export default async function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const user = await requireUser();
  const { id } = await params;
  const project = await db.project.findFirst({ where: { id, userId: user.id }, include: { source: { include: { media: true } }, jobs: { orderBy: { createdAt: "desc" }, take: 8 }, clips: { orderBy: { score: "desc" }, include: { edit: true, highlight: true } } } });
  if (!project) return <main className="min-h-screen bg-[#080a0d] p-8 text-white"><div className="mx-auto max-w-3xl cf-card p-8"><p className="cf-kicker">Project unavailable</p><h1 className="mt-3 text-2xl font-semibold">We could not find this project.</h1><p className="mt-2 text-sm text-zinc-500">It may have been removed or belong to another account.</p><Link href="/dashboard" className="cf-button mt-6">Back to workspace</Link></div></main>;
  const favoriteRows = await db.favorite.findMany({ where: { userId: user.id, projectId: project.id, clipId: { not: null } }, select: { clipId: true } });
  const favoriteIds = favoriteRows.map(row => row.clipId).filter((clipId): clipId is string => Boolean(clipId));
  const asset = project.source?.media[0] ?? null;
  const ingestPayload = project.jobs.find(job => job.type === "INGEST")?.payload as { rangeLimitedDownload?: boolean; sourceRange?: { startSeconds?: number } } | undefined;
  const mediaOffsetSeconds = ingestPayload?.rangeLimitedDownload && project.source?.type !== "GOOGLE_DRIVE" ? Number(ingestPayload.sourceRange?.startSeconds ?? 0) : 0;
  const latest = project.jobs[0];
  const processingState = deriveProjectProcessingState(project);
  const sourceLabel = project.source?.url ?? project.source?.name ?? "Uploaded source";
  return <WorkspaceFrame active="/dashboard" email={user.email ?? undefined} eyebrow="Project workspace" title={project.name} description={sourceLabel} action={<Link href={`/project/${project.id}/long-form`} className="cf-button-secondary !min-h-9 !rounded-[10px] !px-3 text-xs">Long-form workspace &rarr;</Link>}>
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <span className={`rounded-full border px-2.5 py-1 text-[10px] ${stateClass(latest?.status ?? "READY")}`}>{(latest?.status ?? "READY").replaceAll("_", " ")}</span>
        <span className="rounded-xl border border-white/[.08] bg-white/[.025] px-3 py-2 text-xs text-zinc-400">{project.mode === "SHORTS" ? "Vertical shorts" : "Long form"}</span>
        <span className="rounded-xl border border-white/[.08] bg-white/[.025] px-3 py-2 text-xs text-zinc-400">Transcript: {project.outputLanguage.toUpperCase()}</span>
      </div>
      {latest && <ProcessingExperience projectId={project.id} initialState={processingState} />}

      <div id="clip-editor" className="mt-7 scroll-mt-8 grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <section className="min-w-0"><div className="mb-3 flex items-center justify-between"><div><h2 className="text-sm font-semibold">Clip editor</h2><p className="mt-1 text-xs text-zinc-600">Review candidates and adjust the final cut.</p></div><span className="rounded-lg border border-white/[.08] px-2.5 py-1.5 text-[10px] text-zinc-500">{project.clips.length} candidates</span></div>
          {asset && project.clips.length > 0 ? <div className="overflow-hidden rounded-2xl border border-white/[.08] bg-[#0d1117] p-2 sm:p-4"><Editor projectId={project.id} mediaId={asset.id} duration={asset.durationS ?? 0} fps={asset.fps} mediaOffsetSeconds={mediaOffsetSeconds} favoriteIds={favoriteIds} clips={project.clips.map(c => ({ ...c, edit: c.edit ? { ...c.edit, segments: c.edit.segments as any } : null }))}/></div> : <div className="cf-card flex min-h-[320px] flex-col items-center justify-center px-6 py-12 text-center"><div className="grid h-14 w-14 place-items-center rounded-2xl border border-white/10 bg-white/[.025] text-2xl text-[#c4f36b]">{asset ? "◷" : "↑"}</div><h2 className="mt-5 text-lg font-semibold">{asset ? "Waiting for clip candidates" : "Waiting for source media"}</h2><p className="mt-2 max-w-md text-sm leading-6 text-zinc-500">{asset ? "Media is attached, but no real candidates are available yet. Check the job status and worker logs if this state persists." : "The source needs to be ingested before the editor can load a preview or timeline."}</p><div className="mt-5 flex flex-wrap justify-center gap-2"><Link href="/dashboard" className="cf-button-secondary">Back to projects</Link><Link href="/project/new" className="cf-button">Add another source ↗</Link></div></div>}
        </section>
        <aside className="space-y-4"><div className="cf-card p-5"><div className="text-xs text-zinc-500">Source details</div><div className="mt-4 space-y-4">{[{label:"Source type",value:project.source?.type ?? "Not attached"},{label:"Duration",value:asset?.durationS ? time(asset.durationS) : "Pending probe"},{label:"Resolution",value:asset?.width && asset?.height ? `${asset.width} × ${asset.height}` : "Not available"},{label:"Format",value:asset?.mimeType?.split("/").pop()?.toUpperCase() ?? "Not available"},{label:"File size",value:fileSize(asset?.sizeBytes)},{label:"Audio track",value:asset?.hasAudio == null ? "Not checked" : asset.hasAudio ? "Detected" : "No audio detected"}].map(x=><div key={x.label} className="flex items-start justify-between gap-4 border-b border-white/[.06] pb-3 last:border-0 last:pb-0"><span className="text-xs text-zinc-600">{x.label}</span><span className="max-w-[150px] break-words text-right text-xs text-zinc-300">{x.value}</span></div>)}</div></div>
          <div className="rounded-2xl border border-white/[.07] bg-white/[.015] p-4"><div className="text-xs font-semibold">A quick reminder</div><p className="mt-2 text-xs leading-5 text-zinc-500">AI scores are suggestions, not a replacement for your editorial judgment. Preview every clip before exporting.</p></div>
        </aside>
      </div>
  </WorkspaceFrame>;
}
