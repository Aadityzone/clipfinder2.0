import Image from "next/image";
import Link from "next/link";

const moments = [
  { number: "01", title: "The unexpected comeback", range: "00:18:24 — 00:19:02", score: "96", width: "94%" },
  { number: "02", title: "The reaction says it all", range: "00:42:10 — 00:42:38", score: "91", width: "86%" },
  { number: "03", title: "Chat did not see this coming", range: "01:06:51 — 01:07:22", score: "87", width: "78%" },
];

function Brand() {
  return <Link href="/" className="inline-flex items-center gap-2.5 font-semibold tracking-tight" aria-label="Clip Finder home"><span className="grid h-8 w-8 place-items-center rounded-[10px] bg-[#39ff14] text-[#081008]"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true"><path d="M7 5.5v13l11-6.5L7 5.5Z" fill="currentColor"/><path d="M3.5 8v8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg></span><span>clip<span className="text-[#39ff14]">finder</span><span className="ml-1 text-[10px] font-medium text-zinc-500">2.0</span></span></Link>;
}

export default function HomePage() {
  return <main className="relative min-h-screen overflow-hidden bg-[#080a08] text-[#f5f7f5]">
    <div className="pointer-events-none absolute inset-x-0 top-0 h-[780px] cf-grid opacity-60" aria-hidden="true" />
    <div className="pointer-events-none absolute -top-72 left-[58%] h-[700px] w-[900px] -translate-x-1/2 rounded-full cf-glow" aria-hidden="true" />
    <header className="relative z-10 mx-auto flex max-w-[1280px] items-center justify-between px-5 py-5 md:px-9 md:py-7">
      <Brand />
      <nav className="hidden items-center gap-8 text-sm text-[#a0aaa1] md:flex" aria-label="Main navigation"><a className="transition hover:text-white" href="#workflow">How it works</a><a className="transition hover:text-white" href="#features">Features</a></nav>
      <div className="flex items-center gap-2.5"><Link href="/login" className="hidden rounded-xl px-4 py-2.5 text-sm text-[#a0aaa1] transition hover:text-white sm:inline-flex">Sign in</Link><Link href="/signup" className="cf-button !min-h-10 !rounded-[10px] !px-4 text-xs sm:text-sm">Create account <span aria-hidden="true">↗</span></Link></div>
    </header>

    <section className="relative z-10 mx-auto grid max-w-[1280px] items-center gap-10 px-5 pb-20 pt-12 md:px-9 md:pb-28 md:pt-20 lg:grid-cols-[.94fr_1.06fr] lg:gap-8">
      <div className="cf-enter relative z-10">
        <div className="mb-7 inline-flex items-center gap-2.5 rounded-full border border-[#39ff14]/20 bg-[#39ff14]/[.06] px-3.5 py-2 text-xs text-[#b2ff9b]"><span className="h-1.5 w-1.5 rounded-full bg-[#39ff14] shadow-[0_0_12px_#39ff14]" /> AI-assisted clip discovery</div>
        <h1 className="max-w-[700px] text-[clamp(3.2rem,7vw,6.35rem)] font-semibold leading-[.94] tracking-[-.075em]">Turn long videos into <span className="text-[#39ff14]">viral clips.</span></h1>
        <p className="mt-6 max-w-[560px] text-base leading-7 text-[#a0aaa1] md:text-lg md:leading-8">Drop a YouTube or Twitch link. Let AI find the best moments, then refine and export clips ready for Shorts, Reels, and TikTok.</p>

        <form action="/project/new" method="get" className="cf-card mt-8 max-w-[610px] rounded-2xl p-2.5 shadow-[0_24px_70px_rgba(0,0,0,.38)] sm:flex sm:items-center sm:gap-2">
          <label className="sr-only" htmlFor="hero-source-url">YouTube or Twitch video URL</label>
          <div className="flex min-w-0 flex-1 items-center gap-3 px-3"><svg className="shrink-0 text-[#69756b]" viewBox="0 0 24 24" width="19" height="19" fill="none" aria-hidden="true"><path d="M10.5 4.5h-4a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-4M13 4h7v7M20 4l-9 9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg><input id="hero-source-url" className="cf-hero-input min-w-0 flex-1 bg-transparent py-3.5 text-sm text-white outline-none placeholder:text-[#68736a]" type="url" name="sourceUrl" required placeholder="Paste a YouTube or Twitch link" /></div>
          <button className="cf-button w-full !min-h-12 !rounded-xl !px-5 sm:w-auto">Find My Clips <span aria-hidden="true">↗</span></button>
        </form>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 px-1 text-[11px] text-[#69756b]"><span>Supported: YouTube, Twitch, Kick, Google Drive</span><span aria-hidden="true" className="hidden text-[#465047] sm:inline">·</span><span>Only process media you have permission to use</span></div>
        <div className="mt-7"><Link href="/dashboard" className="inline-flex items-center gap-2 text-sm text-[#a0aaa1] transition hover:text-white">Explore the workspace <span className="text-[#39ff14]" aria-hidden="true">→</span></Link></div>
      </div>

      <div className="cf-enter relative mx-auto w-full max-w-[650px] lg:ml-auto" style={{ animationDelay: "90ms" }}>
        <div className="absolute -inset-10 rounded-[40px] bg-[#39ff14]/[.045] blur-3xl" aria-hidden="true" />
        <div className="cf-card relative overflow-hidden rounded-[25px] border-white/[.09] bg-[#0d110e]/95 p-3.5 shadow-[0_35px_100px_rgba(0,0,0,.55)] sm:p-5">
          <div className="flex items-center justify-between border-b border-white/[.07] pb-4"><div><div className="text-sm font-semibold">Moment overview</div><div className="mt-1 text-xs text-[#768078]">Creator session · 01:42:18</div></div><span className="rounded-full border border-[#20c96b]/20 bg-[#20c96b]/[.08] px-2.5 py-1 text-[10px] font-semibold tracking-wide text-[#6ee59c]">ANALYSIS READY</span></div>
          <div className="cf-preview-scene relative mt-4 flex h-[190px] items-center justify-center overflow-hidden rounded-2xl border border-white/[.07] sm:h-[250px]">
            <div className="absolute inset-0 cf-preview-light" aria-hidden="true" />
            <div className="absolute inset-0 bg-[linear-gradient(180deg,transparent_45%,rgba(0,0,0,.66))]" aria-hidden="true" />
            <div className="relative grid h-14 w-14 place-items-center rounded-full border border-white/25 bg-black/30 shadow-xl backdrop-blur"><svg viewBox="0 0 24 24" width="21" height="21" fill="white" aria-hidden="true"><path d="M8 5.5v13L18 12 8 5.5Z"/></svg></div>
            <span className="absolute bottom-3.5 left-4 text-[10px] font-medium tracking-[.14em] text-white/75">SOURCE PREVIEW · ILLUSTRATIVE</span><span className="absolute bottom-3.5 right-4 rounded-md bg-black/50 px-2 py-1 font-mono text-[11px] text-white/80">01:42:18</span>
            <div className="cf-mascot-float absolute -right-2 -top-4 z-[1] h-[128px] w-[128px] sm:-right-3 sm:-top-5 sm:h-[166px] sm:w-[166px]"><Image src="/images/luffy-mascot.gif" alt="Luffy cheering beside your clip preview" fill sizes="(max-width: 640px) 128px, 166px" unoptimized className="object-contain drop-shadow-[0_9px_24px_rgba(57,255,20,.17)]" priority /></div>
          </div>
          <div className="mt-4 flex items-end justify-between gap-3"><div><div className="text-[10px] font-semibold tracking-[.16em] text-[#768078]">TOP MOMENTS</div><div className="mt-1 text-sm font-semibold">3 clips worth reviewing</div></div><span className="text-right text-[11px] text-[#768078]">Ranked by AI score</span></div>
          <div className="mt-3 space-y-2">{moments.map(moment => <div key={moment.number} className="flex items-center gap-3 rounded-xl border border-white/[.055] bg-white/[.025] p-3"><span className="font-mono text-[11px] text-[#606b61]">{moment.number}</span><div className="min-w-0 flex-1"><div className="truncate text-xs font-medium text-[#e5eae5]">{moment.title}</div><div className="mt-1 font-mono text-[10px] text-[#768078]">{moment.range}</div><div className="mt-2 h-1 overflow-hidden rounded-full bg-white/[.07]"><div className="h-full rounded-full bg-[#39ff14]" style={{ width: moment.width }} /></div></div><div className="text-right"><div className="text-sm font-semibold text-[#39ff14]">{moment.score}</div><div className="text-[9px] tracking-wide text-[#606b61]">SCORE</div></div></div>)}</div>
          <div className="mt-4 flex items-center justify-between border-t border-white/[.07] pt-3.5"><span className="text-[10px] text-[#69756b]">Illustrative product preview</span><span className="flex items-center gap-1.5 text-[10px] text-[#a0aaa1]"><span className="h-1.5 w-1.5 rounded-full bg-[#20c96b]"/> Built for real workflows</span></div>
        </div>
      </div>
    </section>

    <section id="workflow" className="relative border-y border-white/[.07] bg-[#0d110e]/65"><div className="mx-auto grid max-w-[1280px] gap-7 px-5 py-8 sm:grid-cols-3 md:px-9">{[{ label: "INPUT", value: "Your source", detail: "Supported links or a media upload" }, { label: "INTELLIGENCE", value: "Ranked moments", detail: "Transcript-led candidate discovery" }, { label: "OUTPUT", value: "Editable clips", detail: "Fine-tune before you export" }].map((item, i) => <div key={item.label} className="cf-enter flex items-start gap-4" style={{ animationDelay: `${i * 65}ms` }}><div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-white/10 bg-white/[.025] font-mono text-xs text-[#39ff14]">0{i + 1}</div><div><div className="text-[10px] font-bold tracking-[.17em] text-[#768078]">{item.label}</div><div className="mt-1.5 text-base font-semibold">{item.value}</div><div className="mt-1 text-xs text-[#768078]">{item.detail}</div></div></div>)}</div></section>
    <section id="features" className="mx-auto max-w-[1280px] px-5 py-20 md:px-9 md:py-28"><div className="max-w-2xl"><p className="cf-kicker">Less scrubbing. More creating.</p><h2 className="mt-4 text-3xl font-semibold tracking-[-.045em] sm:text-5xl">A workflow built around the moment.</h2><p className="mt-5 max-w-xl leading-7 text-[#a0aaa1]">From the first transcript to the final render, keep discovery and editing in one place.</p></div><div className="mt-10 grid gap-4 md:grid-cols-3">{[{ number: "01", title: "Find the moment", body: "Transcribe the source and rank real moments by energy, context, and payoff." }, { number: "02", title: "Make it yours", body: "Fine-tune in and out points, shape the crop, and keep the story intact." }, { number: "03", title: "Ship everywhere", body: "Turn one long recording into a focused batch of vertical-ready clips." }].map((item, i) => <article key={item.number} className="cf-card cf-enter p-6 transition duration-300 hover:-translate-y-1 hover:border-[#39ff14]/20 md:p-7" style={{ animationDelay: `${i * 75}ms` }}><div className="font-mono text-xs text-[#39ff14]">{item.number} / WORKFLOW</div><h3 className="mt-8 text-xl font-semibold">{item.title}</h3><p className="mt-3 text-sm leading-6 text-[#a0aaa1]">{item.body}</p></article>)}</div></section>
    <section className="mx-auto max-w-[1280px] px-5 pb-12 md:px-9 md:pb-16"><div className="cf-card relative flex flex-col items-start justify-between gap-8 overflow-hidden p-7 md:flex-row md:items-center md:p-12"><div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-[#39ff14]/[.055] blur-3xl" aria-hidden="true"/><div className="relative"><p className="cf-kicker">Ready when you are</p><h2 className="mt-3 text-3xl font-semibold tracking-tight">Your next great clip is already recorded.</h2><p className="mt-3 max-w-xl text-sm leading-6 text-[#a0aaa1]">Bring a source you’re authorized to process. We’ll help you find the moments worth editing.</p></div><Link href="/project/new" className="cf-button relative shrink-0 !min-h-12 !px-6">Explore the workspace <span aria-hidden="true">→</span></Link></div><footer className="mt-8 flex flex-col justify-between gap-3 text-xs text-[#69756b] sm:flex-row"><Brand/><span>© {new Date().getFullYear()} Clip Finder 2.0 · Made for creators.</span><span>Use media you have rights to process.</span></footer></section>
  </main>;
}
