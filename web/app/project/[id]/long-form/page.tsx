import Link from "next/link";
import { notFound } from "next/navigation";
import { requireUser } from "../../../../lib/auth";
import { db } from "../../../../lib/db";
import TranscriptEditor from "./TranscriptEditor";

export default async function LongFormPage({ params }: { params: Promise<{ id: string }> }) {
  const user = await requireUser();
  const { id } = await params;
  const project = await db.project.findFirst({ where: { id, userId: user.id }, include: { longFormDocument: true, source: { include: { media: true } } } });
  if (!project) notFound();
  const document = project.longFormDocument;
  const chapters = Array.isArray(document?.chapters) ? document.chapters as Array<{ start?: number; title?: string }> : [];
  return <main className="min-h-screen">
    <header className="border-b border-white/[.07]"><div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-4 sm:px-7"><Link href={"/project/"+id} className="text-xs text-[#9ca6b4] hover:text-white">← Project editor</Link><span className="truncate text-xs font-semibold">{project.name}</span><span className="rounded-full border border-white/[.08] px-3 py-1.5 text-[9px] text-[#8792a1]">LONG-FORM</span></div></header>
    <section className="mx-auto max-w-7xl px-4 py-8 sm:px-7"><p className="cf-eyebrow">Long-form workspace</p><h1 className="mt-3 text-3xl font-semibold tracking-[-.055em] sm:text-4xl">{document?.title || "Long-form production"}</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-[#8792a1]">Review the stored long-form document, chapter outline, transcript, and render status for this project.</p>
      {!document ? <div className="cf-panel mt-8 rounded-2xl p-7 sm:p-10"><span className="grid h-11 w-11 place-items-center rounded-xl bg-white/[.04] text-xl text-[#c4f56b]">◷</span><h2 className="mt-5 text-xl font-semibold">Long-form analysis is not ready.</h2><p className="mt-2 max-w-xl text-sm leading-6 text-[#8792a1]">No long-form document is stored for this project yet. This screen will show the actual generated document once the processing pipeline persists it.</p></div> : <div className="mt-8 grid gap-4 xl:grid-cols-[1fr_340px]">
        <div className="space-y-4"><section className="cf-panel rounded-2xl p-5 sm:p-7"><p className="cf-eyebrow">Document</p><h2 className="mt-2 text-lg font-semibold">Description</h2><p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-[#aeb7c4]">{document.description || "No description has been saved."}</p></section>
          <section className="cf-panel rounded-2xl p-5 sm:p-7"><div className="flex items-center justify-between gap-3"><div><p className="cf-eyebrow">Chapter outline</p><h2 className="mt-2 text-lg font-semibold">Chapters</h2></div><span className="text-[10px] text-[#687383]">{chapters.length} saved</span></div>{chapters.length===0?<p className="mt-5 text-xs text-[#687383]">No chapter markers are saved yet.</p>:<div className="mt-5 space-y-2">{chapters.map((chapter,index)=>{const start=Number(chapter.start??0);return <div key={index} className="flex items-center gap-3 rounded-xl border border-white/[.06] bg-black/10 p-3"><span className="font-mono text-[10px] text-[#c4f56b]">{Math.floor(start/60).toString().padStart(2,"0")}:{Math.floor(start%60).toString().padStart(2,"0")}</span><span className="text-xs text-[#d2d7df]">{chapter.title||"Untitled chapter"}</span></div>})}</div>}</section>
          <section className="cf-panel rounded-2xl p-5 sm:p-7"><p className="cf-eyebrow">Transcript tools</p><h2 className="mt-2 text-lg font-semibold">Transcript editing</h2><p className="mt-2 mb-5 text-xs leading-6 text-[#8792a1]">Changes are handled by the connected transcript editor.</p><TranscriptEditor projectId={id}/></section>
        </div>
        <aside className="space-y-4"><section className="cf-panel rounded-2xl p-5"><p className="cf-eyebrow">Render status</p><p className="mt-2 text-xl font-semibold">{document.renderStatus.replaceAll("_"," ")}</p><p className="mt-2 text-[10px] leading-5 text-[#8792a1]">A render is ready only after the backend confirms a real output file.</p>{document.renderStatus==="READY"&&<video src={"/api/projects/"+id+"/long-form/media"} controls className="mt-4 w-full rounded-xl bg-black" />}</section>
          <section className="cf-panel rounded-2xl p-5"><p className="cf-eyebrow">Thumbnail</p>{document.thumbnailKey ? <img src={"/api/media/thumbnail/"+document.id} alt="Stored long-form thumbnail" className="mt-3 aspect-video w-full rounded-xl object-cover" /> : <div className="mt-3 grid aspect-video place-items-center rounded-xl border border-dashed border-white/[.1] text-xs text-[#687383]">No thumbnail saved</div>}<p className="mt-3 text-[10px] leading-5 text-[#687383]">Only a stored thumbnail is shown here.</p></section>
          <form action={"/api/projects/"+id+"/long-form"} method="post" className="cf-panel rounded-2xl p-5"><p className="text-xs font-semibold">Render long-form video</p><p className="mt-2 text-[10px] leading-5 text-[#8792a1]">Rendering uses the project's configured backend workflow.</p><button className="cf-button cf-button-primary mt-4 w-full">{document.renderStatus==="READY"?"Render again":"Start render"} ↗</button></form>
        </aside>
      </div>}
    </section>
  </main>;
}
