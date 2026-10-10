import Link from "next/link";
import type { ReactNode } from "react";

const primary = [
  { href: "/dashboard", label: "Overview", icon: "◫" },
  { href: "/search", label: "Search library", icon: "⌕" },
  { href: "/favorites", label: "Favorites", icon: "♡" },
  { href: "/exports", label: "Exports", icon: "↗" },
  { href: "/analytics", label: "Analytics", icon: "⌁" },
];
const manage = [
  { href: "/calendar", label: "Publishing calendar", icon: "▦" },
  { href: "/templates", label: "Templates", icon: "▤" },
  { href: "/usage", label: "Plan & usage", icon: "◉" },
  { href: "/settings", label: "Connections", icon: "⚙" },
  { href: "/profile", label: "Profile", icon: "◎" },
];

export default function WorkspaceFrame({ children, active, email, eyebrow, title, description, action }: {
  children: ReactNode;
  active: string;
  email?: string;
  eyebrow: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  const renderLinks = (items: typeof primary) => items.map(item => <Link key={item.href} href={item.href} aria-current={active === item.href ? "page" : undefined} className="cf-sidebar-link"><span className="grid w-5 place-items-center text-base">{item.icon}</span><span>{item.label}</span></Link>);
  return <main className="min-h-screen bg-[#080a0d] text-white">
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-[244px] flex-col border-r border-white/[.07] bg-[#0b0f14] px-4 py-5 lg:flex">
      <Link href="/dashboard" className="mb-9 flex items-center gap-2.5 px-2 font-semibold tracking-tight"><span className="grid h-8 w-8 place-items-center rounded-[10px] bg-[#c4f36b] text-[#12180a]">▶</span><span>clip<span className="text-[#c4f36b]">finder</span><span className="ml-1 text-[10px] text-zinc-600">2.0</span></span></Link>
      <div className="px-3 pb-3 text-[10px] font-bold tracking-[.18em] text-zinc-600">WORKSPACE</div><nav className="space-y-1" aria-label="Workspace">{renderLinks(primary)}</nav>
      <div className="mt-8 px-3 pb-3 text-[10px] font-bold tracking-[.18em] text-zinc-600">MANAGE</div><nav className="space-y-1" aria-label="Manage">{renderLinks(manage)}</nav>
      <div className="mt-auto rounded-2xl border border-white/[.08] bg-white/[.025] p-4"><div className="text-xs font-semibold">Turn streams into stories</div><p className="mt-1.5 text-[11px] leading-5 text-zinc-500">Start with a source you have permission to use.</p><Link href="/project/new" className="cf-button mt-3 w-full !min-h-10 !text-xs">＋ New project</Link></div>
      <div className="mt-4 flex items-center gap-3 border-t border-white/[.07] px-2 pt-4"><div className="grid h-9 w-9 place-items-center rounded-full bg-[#1d2930] text-sm font-semibold text-[#c4f36b]">{(email?.[0] ?? "C").toUpperCase()}</div><div className="min-w-0"><div className="truncate text-xs font-medium">{email ?? "Creator account"}</div><div className="mt-1 text-[10px] text-zinc-600">Creator workspace</div></div></div>
    </aside>
    <div className="min-h-screen lg:pl-[244px]">
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-white/[.07] bg-[#080a0d]/90 px-4 py-3 backdrop-blur-xl sm:px-7"><Link href="/dashboard" className="font-semibold tracking-tight lg:hidden">clip<span className="text-[#c4f36b]">finder</span></Link><div className="hidden text-xs text-zinc-500 lg:block">Workspace <span className="mx-2 text-zinc-700">/</span><span className="text-zinc-300">{title}</span></div><div className="flex items-center gap-2"><Link href="/search" className="cf-button-secondary !min-h-9 !rounded-[10px] !px-3 text-xs">⌕ Search</Link><Link href="/project/new" className="cf-button !min-h-9 !rounded-[10px] !px-3 text-xs">＋ New project</Link></div></header>
      <nav aria-label="Mobile workspace navigation" className="flex gap-1 overflow-x-auto border-b border-white/[.06] px-3 py-2 lg:hidden">{[...primary, ...manage].map(item => <Link key={item.href} href={item.href} aria-current={active === item.href ? "page" : undefined} className={`shrink-0 rounded-lg px-3 py-2 text-[10px] font-medium ${active === item.href ? "bg-[#c4f36b]/[.08] text-[#d7f9a7]" : "text-zinc-500 hover:bg-white/[.04] hover:text-zinc-200"}`}>{item.label}</Link>)}</nav>
      <div className="mx-auto max-w-[1450px] px-4 pb-14 sm:px-7">
        <div className="flex flex-col justify-between gap-4 border-b border-white/[.06] py-8 sm:flex-row sm:items-end"><div><p className="cf-kicker">{eyebrow}</p><h1 className="mt-3 text-3xl font-semibold tracking-[-.045em] sm:text-4xl">{title}<span className="text-[#c4f36b]">.</span></h1>{description && <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-500">{description}</p>}</div>{action && <div className="shrink-0">{action}</div>}</div>
        <div className="cf-enter pt-6">{children}</div>
      </div>
    </div>
  </main>;
}
