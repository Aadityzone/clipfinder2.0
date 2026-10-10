import Link from "next/link";

const features = [
  { number: "01", title: "Find the moment", body: "Transcribe the source and rank real moments by energy, context, and payoff." },
  { number: "02", title: "Make it yours", body: "Fine-tune in and out points, shape the crop, and keep the story intact." },
  { number: "03", title: "Ship everywhere", body: "Turn one long recording into a focused batch of vertical-ready clips." },
];

function Brand({ light = false }: { light?: boolean }) {
  return <Link href="/" className="inline-flex items-center gap-2.5 font-semibold tracking-tight"><span className="grid h-8 w-8 place-items-center rounded-[10px] bg-[#c4f36b] text-[#12180a]"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true"><path d="M7 5.5v13l11-6.5L7 5.5Z" fill="currentColor"/><path d="M3.5 8v8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg></span><span className={light ? "text-white" : "text-white"}>clip<span className="text-[#c4f36b]">finder</span><span className="ml-1 text-[10px] font-medium text-zinc-500">2.0</span></span></Link>;
}

export default function HomePage() {
  return <main className="min-h-screen overflow-hidden bg-[#080a0d] text-white">
    <div className="pointer-events-none absolute inset-x-0 top-0 h-[760px] cf-grid opacity-70" />
    <div className="pointer-events-none absolute -top-64 left-1/2 h-[680px] w-[900px] -translate-x-1/2 rounded-full cf-glow" />
    <header className="relative z-10 mx-auto flex max-w-[1240px] items-center justify-between px-5 py-5 md:px-8 md:py-7">
      <Brand />
      <nav className="hidden items-center gap-8 text-sm text-zinc-400 md:flex" aria-label="Main navigation"><a className="transition hover:text-white" href="#workflow">Workflow</a><a className="transition hover:text-white" href="#features">Why Clip Finder</a><a className="transition hover:text-white" href="#faq">FAQ</a></nav>
      <div className="flex items-center gap-2.5"><Link href="/login" className="hidden rounded-xl px-4 py-2.5 text-sm text-zinc-300 transition hover:text-white sm:inline-flex">Sign in</Link><Link href="/signup" className="cf-button !min-h-10 !rounded-[10px] !px-4 text-xs sm:text-sm">Start creating <span aria-hidden="true">↗</span></Link></div>
    </header>
    <section className="relative z-10 mx-auto grid max-w-[1240px] items-center gap-14 px-5 pb-20 pt-16 md:px-8 md:pb-28 md:pt-24 lg:grid-cols-[1.03fr_.97fr] lg:gap-10">
      <div className="cf-enter">
        <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-[#c4f36b]/20 bg-[#c4f36b]/[.07] px-3.5 py-2 text-xs text-[#d7f9a7]"><span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#c4f36b] opacity-50"/><span className="relative inline-flex h-2 w-2 rounded-full bg-[#c4f36b]"/></span> From long-form to scroll-stopping</div>
        <h1 className="max-w-[760px] text-[clamp(3.25rem,7vw,6.7rem)] font-semibold leading-[.94] tracking-[-.075em]">The best part<br/>is <span className="text-[#c4f36b]">in there.</span></h1>
        <p className="mt-7 max-w-[540px] text-base leading-7 text-zinc-400 md:text-lg md:leading-8">Find the moments people will actually watch. Clip Finder analyzes your source, ranks the strongest beats, and gives you an editor to shape every cut.</p>
        <div className="mt-9 flex flex-wrap items-center gap-3"><Link href="/signup" className="cf-button !min-h-12 !rounded-[13px] !px-6">Find my clips <span aria-hidden="true">↗</span></Link><Link href="/login" className="cf-button-secondary !min-h-12 !rounded-[13px] !px-6">Open workspace <span aria-hidden="true">→</span></Link></div>
        <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-3 text-xs text-zinc-500"><span className="flex items-center gap-2"><span className="text-[#c4f36b]">✓</span> Real source analysis</span><span className="flex items-center gap-2"><span className="text-[#c4f36b]">✓</span> Editable clip timing</span><span className="flex items-center gap-2"><span className="text-[#c4f36b]">✓</span> Creator-first workflow</span></div>
      </div>
      <div className="cf-enter relative mx-auto w-full max-w-[560px] lg:ml-auto" style={{animationDelay:"100ms"}}>
        <div className="absolute -inset-5 rounded-[34px] bg-[#c4f36b]/[.055] blur-2xl"/>
        <div className="cf-card relative overflow-hidden rounded-[26px] border-white/10 bg-[#0e1218]/95 p-4 shadow-[0_35px_100px_rgba(0,0,0,.45)] sm:p-5">
          <div className="flex items-center justify-between border-b border-white/[.07] pb-4"><div><div className="text-sm font-semibold">Moment overview</div><div className="mt-1 text-xs text-zinc-500">Creator session · 01:42:18</div></div><span className="rounded-full border border-[#c4f36b]/20 bg-[#c4f36b]/[.08] px-2.5 py-1 text-[10px] font-semibold text-[#d7f9a7]">ANALYSIS READY</span></div>
          <div className="relative mt-4 flex h-[210px] items-center justify-center overflow-hidden rounded-2xl border border-white/[.07] bg-[#171d25] sm:h-[260px]">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_30%,rgba(139,183,255,.22),transparent_40%),linear-gradient(140deg,#222c39,#10141a_55%,#202c1c)]"/>
            <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/65 to-transparent"/>
            <div className="relative grid h-16 w-16 place-items-center rounded-full border border-white/25 bg-black/30 shadow-xl backdrop-blur"><svg viewBox="0 0 24 24" width="22" height="22" fill="white" aria-hidden="true"><path d="M8 5.5v13L18 12 8 5.5Z"/></svg></div>
            <span className="absolute bottom-4 left-4 text-xs font-medium text-white/80">SOURCE PREVIEW</span><span className="absolute bottom-4 right-4 rounded-md bg-black/50 px-2 py-1 font-mono text-[11px] text-white/80">01:42:18</span>
          </div>
          <div className="mt-4 flex items-center justify-between"><div><div className="text-xs text-zinc-500">TOP MOMENTS</div><div className="mt-1 text-sm font-semibold">3 clips worth keeping</div></div><span className="text-xs text-zinc-500">Ranked by AI score</span></div>
          <div className="mt-3 space-y-2">
            {[{n:"01",title:"The unexpected comeback",time:"00:18:24 – 00:19:02",score:"96",w:"94%"},{n:"02",title:"The reaction says it all",time:"00:42:10 – 00:42:38",score:"91",w:"86%"},{n:"03",title:"Chat did not see this coming",time:"01:06:51 – 01:07:22",score:"87",w:"78%"}].map(c=><div key={c.n} className="flex items-center gap-3 rounded-xl border border-white/[.055] bg-white/[.025] p-3"><span className="font-mono text-[11px] text-zinc-600">{c.n}</span><div className="min-w-0 flex-1"><div className="truncate text-xs font-medium text-zinc-200">{c.title}</div><div className="mt-1 font-mono text-[10px] text-zinc-500">{c.time}</div><div className="mt-2 h-1 overflow-hidden rounded-full bg-white/[.07]"><div className="h-full rounded-full bg-[#c4f36b]" style={{width:c.w}}/></div></div><div className="text-right"><div className="text-sm font-semibold text-[#c4f36b]">{c.score}</div><div className="text-[9px] text-zinc-600">SCORE</div></div></div>)}
          </div>
          <div className="mt-4 flex items-center justify-between border-t border-white/[.07] pt-4"><span className="text-[11px] text-zinc-500">Illustrative workspace preview</span><span className="flex items-center gap-1.5 text-[11px] text-zinc-300"><span className="h-1.5 w-1.5 rounded-full bg-[#c4f36b]"/> Built for real workflows</span></div>
        </div>
      </div>
    </section>
    <section id="workflow" className="relative border-y border-white/[.07] bg-white/[.015]"><div className="mx-auto grid max-w-[1240px] gap-7 px-5 py-8 sm:grid-cols-3 md:px-8">{[{label:"INPUT",value:"Your source",detail:"YouTube, Twitch and supported media"},{label:"INTELLIGENCE",value:"Ranked moments",detail:"Transcript-led candidate discovery"},{label:"OUTPUT",value:"Editable clips",detail:"Fine-tune before you export"}].map((x,i)=><div key={x.label} className="flex items-start gap-4"><div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-white/10 bg-white/[.035] font-mono text-xs text-[#c4f36b]">0{i+1}</div><div><div className="text-[10px] font-bold tracking-[.17em] text-zinc-500">{x.label}</div><div className="mt-1.5 text-base font-semibold">{x.value}</div><div className="mt-1 text-xs text-zinc-500">{x.detail}</div></div></div>)}</div></section>
    <section id="features" className="mx-auto max-w-[1240px] px-5 py-20 md:px-8 md:py-28"><div className="max-w-2xl"><p className="cf-kicker">Less scrubbing. More creating.</p><h2 className="mt-4 text-3xl font-semibold tracking-[-.045em] sm:text-5xl">A workflow built around the moment.</h2><p className="mt-5 max-w-xl leading-7 text-zinc-400">From the first transcript to the final render, keep discovery and editing in one place.</p></div><div className="mt-10 grid gap-4 md:grid-cols-3">{features.map(f=><article key={f.number} className="cf-card p-6 transition duration-300 hover:-translate-y-1 hover:border-white/20 md:p-7"><div className="font-mono text-xs text-[#c4f36b]">{f.number} / WORKFLOW</div><h3 className="mt-8 text-xl font-semibold">{f.title}</h3><p className="mt-3 text-sm leading-6 text-zinc-400">{f.body}</p></article>)}</div></section>
    <section id="faq" className="mx-auto max-w-[1240px] px-5 pb-24 md:px-8"><div className="cf-card flex flex-col items-start justify-between gap-8 overflow-hidden p-7 md:flex-row md:items-center md:p-12"><div><p className="cf-kicker">Ready when you are</p><h2 className="mt-3 text-3xl font-semibold tracking-tight">Your next great clip is already recorded.</h2><p className="mt-3 max-w-xl text-sm leading-6 text-zinc-400">Bring a source you’re authorized to process. We’ll help you find the moments worth editing.</p></div><Link href="/signup" className="cf-button shrink-0 !min-h-12 !px-6">Create your workspace ↗</Link></div><div className="mt-8 flex flex-col justify-between gap-3 text-xs text-zinc-600 sm:flex-row"><Brand/><span>© {new Date().getFullYear()} Clip Finder 2.0 · Made for creators.</span><span>Use media you have rights to process.</span></div></section>
  </main>;
}
