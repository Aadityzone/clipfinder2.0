import Link from "next/link";
import { requireUser } from "../../lib/auth";
import { db } from "../../lib/db";

export default async function ExportsPage() {
  const user = await requireUser();
  const rows = await db.export.findMany({ where: { userId: user.id }, orderBy: { createdAt: "desc" }, take: 100, include: { clip: true, render: true } });
  return <main className="min-h-screen">
    <header className="border-b border-white/[.07]"><div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5 sm:px-8"><Link href="/dashboard" className="flex items-center gap-2 text-xs text-[#9ca6b4] hover:text-white"><span className="text-[#c4f56b]">←</span> Workspace</Link><Link href="/project/new" className="cf-button cf-button-primary">＋ New project</Link></div></header>
    <section className="mx-auto max-w-6xl px-5 py-10 sm:px-8"><p className="cf-eyebrow">Your output library</p><h1 className="mt-3 text-4xl font-semibold tracking-[-.06em]">Exports</h1><p className="mt-3 max-w-xl text-sm leading-6 text-[#8792a1]">Download real output files created by the render pipeline. Items appear here only when an export record exists.</p>
      <div className="mt-8 flex items-center justify-between border-b border-white/[.07] pb-3"><span className="text-xs font-semibold">Recent exports</span><span className="text-[10px] text-[#687383]">{rows.length} records</span></div>
      {rows.length===0 ? <div className="cf-panel mt-4 rounded-2xl p-8 sm:p-12"><span className="grid h-11 w-11 place-items-center rounded-xl bg-white/[.04] text-xl text-[#c4f56b]">↧</span><h2 className="mt-5 text-xl font-semibold">Nothing exported yet.</h2><p className="mt-2 max-w-md text-sm leading-6 text-[#8792a1]">Once a clip has been rendered and an export is created, its download action will appear here. No placeholder files are shown.</p><Link href="/dashboard" className="cf-button cf-button-secondary mt-5">Back to projects</Link></div> : <div className="mt-4 space-y-2">{rows.map((item)=><article key={item.id} className="cf-panel flex flex-col gap-4 rounded-2xl p-4 sm:flex-row sm:items-center sm:justify-between"><div className="flex min-w-0 items-center gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-white/[.08] bg-white/[.025] text-lg text-[#c4f56b]">▶</span><div className="min-w-0"><p className="truncate text-sm font-semibold">{item.clip.title || item.clip.category || `Clip ${item.clipId.slice(0,8)}`}</p><p className="mt-1 text-[10px] text-[#687383]">Created {item.createdAt.toLocaleString()} · {item.status}</p></div></div><div className="flex items-center gap-2"><span className="rounded-full border border-white/[.08] px-3 py-1.5 text-[9px] text-[#9ca6b4]">{item.render?.status ?? item.status}</span><a href={"/api/exports/"+item.id} className="cf-button cf-button-secondary min-h-9 text-[10px]">Download ↗</a></div></article>)}</div>}
    </section>
  </main>;
}
