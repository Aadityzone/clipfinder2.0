import Link from "next/link";
import { requireUser } from "../../lib/auth";
import { db } from "../../lib/db";

function fmt(d: Date) { return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" }); }
function statusLabel(status?: string) {
  if (!status) return "No job";
  return status.toLowerCase().replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());
}
export default async function DashboardPage() {
  const u = await requireUser();
  const projects = await db.project.findMany({
    where: { userId: u.id }, orderBy: { updatedAt: "desc" },
    include: { source: true, clips: { orderBy: { score: "desc" }, take: 1 }, jobs: { orderBy: { createdAt: "desc" }, take: 1 } },
  });
  const usage = await db.usage.findUnique({ where: { userId: u.id } });
  const active = projects.filter((p) => p.jobs[0] && !["READY", "FAILED", "CANCELLED"].includes(p.jobs[0].status)).length;
  return <main className="min-h-screen">
    <aside className="fixed inset-y-0 left-0 z-20 hidden w-[238px] flex-col border-r border-white/[.07] bg-[#0b0e13] px-4 py-5 lg:flex">
      <Link href="/" className="flex items-center gap-3 px-2"><span className="grid h-9 w-9 place-items-center rounded-xl bg-[#c4f56b] font-black text-[#141b0b]">c.</span><span className="text-sm font-semibold">clipfinder<span className="ml-1 text-[#8792a1]">/ studio</span></span></Link>
      <p className="mb-3 mt-10 px-3 text-[9px] font-bold tracking-[.18em] text-[#687383]">WORKSPACE</p>
      <nav className="space-y-1 text-[12px]">
        <Link href="/dashboard" className="flex items-center gap-3 rounded-xl border border-[#c4f56b]/15 bg-[#c4f56b]/[.07] px-3 py-3 text-[#c4f56b]"><span>▦</span> Overview</Link>
        <Link href="/search" className="flex items-center gap-3 rounded-xl px-3 py-3 text-[#9ca6b4] transition hover:bg-white/[.04] hover:text-white"><span>⌕</span> Search content</Link>
        <Link href="/favorites" className="flex items-center gap-3 rounded-xl px-3 py-3 text-[#9ca6b4] transition hover:bg-white/[.04] hover:text-white"><span>☆</span> Favorites</Link>
        <Link href="/exports" className="flex items-center gap-3 rounded-xl px-3 py-3 text-[#9ca6b4] transition hover:bg-white/[.04] hover:text-white"><span>↧</span> Exports</Link>
      </nav>
      <p className="mb-3 mt-8 px-3 text-[9px] font-bold tracking-[.18em] text-[#687383]">YOUR ACCOUNT</p>
      <nav className="space-y-1 text-[12px]">
        <Link href="/usage" className="block rounded-xl px-3 py-3 text-[#9ca6b4] hover:bg-white/[.04]">Usage</Link>
        <Link href="/analytics" className="block rounded-xl px-3 py-3 text-[#9ca6b4] hover:bg-white/[.04]">Analytics</Link>
        <Link href="/calendar" className="block rounded-xl px-3 py-3 text-[#9ca6b4] hover:bg-white/[.04]">Calendar</Link>
        <Link href="/templates" className="block rounded-xl px-3 py-3 text-[#9ca6b4] hover:bg-white/[.04]">Templates</Link>
        <Link href="/settings" className="block rounded-xl px-3 py-3 text-[#9ca6b4] hover:bg-white/[.04]">Settings</Link>
      </nav>
      <div className="mt-auto rounded-2xl border border-white/[.08] bg-white/[.025] p-3"><div className="flex items-center gap-2"><span className="grid h-8 w-8 place-items-center rounded-full bg-[#c4f56b]/10 text-xs font-semibold text-[#c4f56b]">{(u.name || u.email).slice(0,1).toUpperCase()}</span><div className="min-w-0"><p className="truncate text-[11px] font-semibold">{u.name || "Creator account"}</p><p className="truncate text-[9px] text-[#687383]">{u.email}</p></div></div></div>
    </aside>
    <section className="mx-auto max-w-[1600px] px-5 py-6 sm:px-8 lg:ml-[238px] lg:px-10 lg:py-9">
      <header className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
        <div><p className="cf-eyebrow">Creator workspace</p><h1 className="mt-2 text-3xl font-semibold tracking-[-.055em] sm:text-4xl">Good to see you{u.name ? `, ${u.name.split(" ")[0]}` : ""}.</h1><p className="mt-2 text-sm text-[#8792a1]">Your source videos, analysis jobs, and clips in one place.</p></div>
        <div className="flex gap-2"><Link href="/search" className="cf-button cf-button-secondary">⌕ <span className="hidden sm:inline">Search</span></Link><Link href="/project/new" className="cf-button cf-button-primary">＋ New project</Link></div>
      </header>
      <div className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="cf-panel rounded-2xl p-5"><div className="flex items-center justify-between text-[11px] text-[#8792a1]"><span>Projects</span><span className="text-[#c4f56b]">↗</span></div><p className="mt-4 text-3xl font-semibold tracking-tight">{projects.length}</p><p className="mt-2 text-[10px] text-[#687383]">Across your workspace</p></div>
        <div className="cf-panel rounded-2xl p-5"><div className="flex items-center justify-between text-[11px] text-[#8792a1]"><span>Active processing</span><span className="h-2 w-2 rounded-full bg-[#c4f56b]" /></div><p className="mt-4 text-3xl font-semibold tracking-tight">{active}</p><p className="mt-2 text-[10px] text-[#687383]">Based on latest job status</p></div>
        <div className="cf-panel rounded-2xl p-5"><div className="flex items-center justify-between text-[11px] text-[#8792a1]"><span>Minutes analyzed</span><span className="text-[#8792a1]">◷</span></div><p className="mt-4 text-3xl font-semibold tracking-tight">{Math.round(usage?.minutesAnalyzed ?? 0)}</p><p className="mt-2 text-[10px] text-[#687383]">Recorded usage</p></div>
        <div className="cf-panel rounded-2xl p-5"><div className="flex items-center justify-between text-[11px] text-[#8792a1]"><span>Exports</span><span className="text-[#8792a1]">↧</span></div><p className="mt-4 text-3xl font-semibold tracking-tight">{usage?.exports ?? 0}</p><p className="mt-2 text-[10px] text-[#687383]">Recorded export count</p></div>
      </div>
      <section className="mt-10">
        <div className="mb-4 flex items-end justify-between gap-3"><div><h2 className="text-lg font-semibold tracking-tight">Recent projects</h2><p className="mt-1 text-xs text-[#687383]">Continue where you left off.</p></div><span className="text-[10px] text-[#687383]">{projects.length} total</span></div>
        {projects.length === 0 ? <div className="cf-panel relative overflow-hidden rounded-3xl p-7 sm:p-12"><div className="cf-glow pointer-events-none absolute -right-10 -top-20 h-72 w-72" /><div className="relative max-w-xl"><span className="grid h-12 w-12 place-items-center rounded-2xl border border-[#c4f56b]/20 bg-[#c4f56b]/[.07] text-xl text-[#c4f56b]">↗</span><p className="cf-eyebrow mt-6">Start with a source</p><h3 className="mt-2 text-2xl font-semibold tracking-[-.045em]">Your next highlight starts here.</h3><p className="mt-3 max-w-lg text-sm leading-6 text-[#8792a1]">Paste a supported video URL or upload media you have permission to use. Clip Finder will show real processing states and only display clips produced from your source.</p><Link href="/project/new" className="cf-button cf-button-primary mt-6">Create your first project <span aria-hidden="true">↗</span></Link></div></div> : <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">{projects.map((p) => { const j = p.jobs[0]; const score = p.clips[0]?.score; return <Link key={p.id} href={"/project/" + p.id} className="cf-panel group rounded-2xl p-5 transition duration-200 hover:-translate-y-0.5 hover:border-[#c4f56b]/25"><div className="flex items-start justify-between gap-3"><div className="flex min-w-0 items-center gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-white/[.08] bg-white/[.035] text-lg text-[#c4f56b]">▶</span><div className="min-w-0"><h3 className="truncate text-sm font-semibold transition group-hover:text-[#c4f56b]">{p.name}</h3><p className="mt-1 truncate text-[10px] text-[#687383]">{p.source?.url ?? "Uploaded source"}</p></div></div><span className="shrink-0 rounded-full border border-white/[.08] px-2 py-1 text-[9px] text-[#9ca6b4]">{statusLabel(j?.status)}</span></div><div className="mt-7 flex items-end justify-between border-t border-white/[.06] pt-4"><div><p className="text-[10px] text-[#687383]">Top candidate score</p><p className="mt-1 text-lg font-semibold">{score == null ? "—" : score.toFixed(0)}<span className="ml-1 text-[10px] font-normal text-[#687383]">{score == null ? "No candidates yet" : "points"}</span></p></div><p className="text-[10px] text-[#687383]">Updated {fmt(p.updatedAt)}</p></div></Link>; })}</div>}
      </section>
      <footer className="mt-12 border-t border-white/[.07] pt-5 text-[10px] text-[#687383]">Clip Finder reports real project data. A missing result means processing has not produced one yet.</footer>
    </section>
  </main>;
}
