import { requireUser } from "../../lib/auth";
import { db } from "../../lib/db";
import WorkspaceFrame from "../../components/WorkspaceFrame";

const swatches = ["from-[#c4f36b]/20 to-[#c4f36b]/[.02]", "from-[#8bb7ff]/20 to-[#8bb7ff]/[.02]", "from-[#f4a6d7]/20 to-[#f4a6d7]/[.02]"];

export default async function Templates() {
  const user = await requireUser();
  const rows = await db.template.findMany({ where: { userId: user.id }, orderBy: { updatedAt: "desc" } });
  return <WorkspaceFrame active="/templates" email={user.email} eyebrow="Creative toolkit" title="Templates" description="Your saved edit presets. Reuse a template when the backend supports applying it to a new clip.">
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><div className="text-xs text-zinc-500">{rows.length} saved template{rows.length === 1 ? "" : "s"}</div><span className="rounded-lg border border-white/[.07] px-3 py-2 text-[10px] text-zinc-500">PERSONAL LIBRARY</span></div>
    {rows.length === 0 ? <div className="rounded-2xl border border-dashed border-white/[.12] bg-white/[.012] px-6 py-16 text-center"><div className="mx-auto grid h-12 w-12 place-items-center rounded-xl border border-white/[.08] text-xl text-[#c4f36b]">▤</div><h2 className="mt-4 text-lg font-semibold">Your template shelf is ready</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-zinc-500">Saved templates from your account will appear here. The library is empty right now; we will not seed it with fake presets.</p><a href="/dashboard" className="cf-button mt-5">Open a project ↗</a></div> : <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{rows.map((row, index) => <article key={row.id} className="overflow-hidden rounded-2xl border border-white/[.08] bg-[#10141a]"><div className={`relative h-36 bg-gradient-to-br ${swatches[index % swatches.length]}`}><div className="absolute inset-4 grid grid-cols-[1fr_.55fr] gap-2 opacity-70"><div className="rounded-lg border border-white/10 bg-black/25"/><div className="space-y-2"><div className="h-1/2 rounded-lg border border-white/10 bg-black/20"/><div className="h-1/3 rounded-lg border border-white/10 bg-black/20"/></div></div><span className="absolute bottom-3 left-3 rounded-md border border-white/10 bg-black/40 px-2 py-1 text-[9px] uppercase tracking-wider">Saved preset</span></div><div className="p-5"><h2 className="font-semibold">{row.name}</h2><p className="mt-2 text-xs text-zinc-500">Updated {row.updatedAt.toLocaleDateString("en-IN", { dateStyle: "medium" })}</p><div className="mt-4 border-t border-white/[.07] pt-3 text-[10px] text-zinc-600">Template ID · {row.id.slice(0, 10)}</div></div></article>)}</div>}
  </WorkspaceFrame>;
}
