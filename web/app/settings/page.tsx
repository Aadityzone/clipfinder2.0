import Link from "next/link";
import { requireUser } from "../../lib/auth";
import { db } from "../../lib/db";
import WorkspaceFrame from "../../components/WorkspaceFrame";

const providers = [
  { id: "youtube", name: "YouTube", detail: "Connect your channel to publish finished clips and sync available performance data.", mark: "YT" },
  { id: "tiktok", name: "TikTok", detail: "Connect a creator account to enable supported publishing workflows.", mark: "TT" },
  { id: "google-drive", name: "Google Drive", detail: "Browse media stored in Drive and bring an eligible source into your workspace.", mark: "GD" },
];

export default async function Settings({ searchParams }: { searchParams: Promise<{ connected?: string; error?: string }> }) {
  const user = await requireUser();
  const query = await searchParams;
  const rows = await db.socialConnection.findMany({ where: { userId: user.id }, select: { id: true, provider: true, accountId: true, metadata: true, expiresAt: true } });
  return <WorkspaceFrame active="/settings" email={user.email} eyebrow="Workspace settings" title="Connections" description="Manage the creator accounts and storage providers Clip Finder can access.">
    {query.connected && <div role="status" className="mb-5 rounded-xl border border-emerald-300/20 bg-emerald-300/[.06] p-4 text-sm text-emerald-200">Connected {query.connected} successfully.</div>}
    {query.error && <div role="alert" className="mb-5 rounded-xl border border-red-300/20 bg-red-300/[.05] p-4 text-sm text-red-200">Connection was not completed. {query.error}</div>}
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]"><section className="space-y-3">{providers.map(provider => {
      const row = rows.find(item => item.provider === provider.id);
      const metadata = row?.metadata as Record<string, unknown> | null;
      const expired = row?.expiresAt ? row.expiresAt.getTime() < Date.now() : false;
      return <article key={provider.id} className="rounded-2xl border border-white/[.08] bg-[#10141a] p-5 sm:p-6"><div className="flex flex-col gap-4 sm:flex-row sm:items-center"><div className="grid h-12 w-12 shrink-0 place-items-center rounded-xl border border-white/[.08] bg-white/[.025] font-mono text-xs font-bold text-[#c4f36b]">{provider.mark}</div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h2 className="font-semibold">{provider.name}</h2><span className={`rounded-full border px-2 py-1 text-[9px] font-semibold uppercase tracking-wider ${row && !expired ? "border-emerald-300/20 bg-emerald-300/[.06] text-emerald-200" : "border-white/10 bg-white/[.025] text-zinc-500"}`}>{row ? expired ? "Reconnect needed" : "Connected" : "Not connected"}</span></div><p className="mt-1.5 max-w-2xl text-xs leading-5 text-zinc-500">{provider.detail}</p>{row && <p className="mt-2 truncate text-[10px] text-zinc-600">{String(metadata?.title ?? metadata?.displayName ?? row.accountId ?? "Connected account")}</p>}</div><a href={`/api/connections/${provider.id}/start`} className={row ? "cf-button-secondary !min-h-10 !text-xs" : "cf-button !min-h-10 !text-xs"}>{row ? "Reconnect" : "Connect"} ↗</a></div></article>;
    })}</section><aside className="space-y-3"><div className="rounded-2xl border border-white/[.08] bg-[#10141a] p-5"><div className="text-xs font-semibold">Connection health</div><div className="mt-4 text-3xl font-semibold">{rows.length}<span className="ml-2 text-sm font-normal text-zinc-500">connected</span></div><p className="mt-2 text-xs leading-5 text-zinc-500">Connected providers appear here based on saved account records. Platform capabilities can vary by account and authorization.</p></div><div className="rounded-2xl border border-amber-300/15 bg-amber-300/[.025] p-5"><div className="text-xs font-semibold text-amber-100">Keep access secure</div><p className="mt-2 text-xs leading-5 text-zinc-500">OAuth credentials are handled server-side. Never paste provider tokens into chat or source files.</p><Link href="/profile" className="mt-4 inline-flex text-xs font-semibold text-[#c4f36b]">View account profile →</Link></div></aside></div>
  </WorkspaceFrame>;
}
