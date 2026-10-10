import Link from "next/link";
import { requireUser } from "../../lib/auth";
import { db } from "../../lib/db";

export default async function FavoritesPage() {
  const user = await requireUser();
  const rows = await db.favorite.findMany({ where: { userId: user.id, clipId: { not: null } }, orderBy: { createdAt: "desc" }, include: { clip: true, project: true } });
  return <main className="min-h-screen">
    <header className="border-b border-white/[.07]"><div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5 sm:px-8"><Link href="/dashboard" className="flex items-center gap-2 text-xs text-[#9ca6b4] hover:text-white"><span className="text-[#c4f56b]">←</span> Workspace</Link><Link href="/project/new" className="cf-button cf-button-primary">＋ New project</Link></div></header>
    <section className="mx-auto max-w-6xl px-5 py-10 sm:px-8"><p className="cf-eyebrow">Your collection</p><h1 className="mt-3 text-4xl font-semibold tracking-[-.06em]">Saved clips</h1><p className="mt-3 max-w-xl text-sm leading-6 text-[#8792a1]">The moments you marked for later, connected to their source projects.</p>
      {rows.length===0 ? <div className="cf-panel mt-8 rounded-2xl p-8 sm:p-12"><span className="grid h-11 w-11 place-items-center rounded-xl bg-white/[.04] text-xl text-[#c4f56b]">☆</span><h2 className="mt-5 text-xl font-semibold">Your collection starts here.</h2><p className="mt-2 max-w-md text-sm leading-6 text-[#8792a1]">Saved clips will appear when you favorite a real candidate from a project. We don't fill this space with sample content.</p><Link href="/dashboard" className="cf-button cf-button-secondary mt-5">Browse projects</Link></div> : <div className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{rows.map((item)=><Link key={item.id} href={item.projectId ? "/project/"+item.projectId : "/dashboard"} className="cf-panel group rounded-2xl p-5 transition hover:-translate-y-0.5 hover:border-[#c4f56b]/25"><div className="flex items-start justify-between"><span className="grid h-10 w-10 place-items-center rounded-xl bg-[#c4f56b]/[.07] text-lg text-[#c4f56b]">☆</span><span className="text-[9px] text-[#687383]">{item.createdAt.toLocaleDateString()}</span></div><h2 className="mt-5 text-sm font-semibold group-hover:text-[#c4f56b]">{item.clip?.title || item.clip?.category || "Saved clip"}</h2><p className="mt-1 truncate text-[10px] text-[#687383]">{item.project?.name ?? "Source project"}</p><div className="mt-5 flex justify-between border-t border-white/[.06] pt-3 text-[10px] text-[#8792a1]"><span>{item.clip ? `${item.clip.startS.toFixed(1)}s → ${item.clip.endS.toFixed(1)}s` : "Clip unavailable"}</span><span>Score {item.clip?.score?.toFixed(0) ?? "—"} ↗</span></div></Link>)}</div>}
    </section>
  </main>;
}
