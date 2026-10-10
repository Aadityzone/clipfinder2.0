import Link from "next/link";

const steps = [
  { n: "01", title: "Bring your source", text: "Start with a supported video URL or upload a file you have permission to use.", icon: "↗" },
  { n: "02", title: "Find the real moments", text: "Transcription and media analysis surface candidate moments from the actual source.", icon: "⌁" },
  { n: "03", title: "Make it yours", text: "Review ranked clips, refine timing, shape the frame, and prepare captions.", icon: "◫" },
  { n: "04", title: "Export with confidence", text: "Render and download when the real output is ready. No pretend progress.", icon: "↓" },
];
const tags = ["Streams", "Podcasts", "Gameplay", "Interviews", "Creator videos"];

export default function HomePage() {
  return <main className="min-h-screen overflow-hidden">
    <div className="pointer-events-none fixed inset-0 cf-grid opacity-60" aria-hidden="true" />
    <nav className="relative z-10 mx-auto flex max-w-[1320px] items-center justify-between px-5 py-5 sm:px-8 lg:px-12">
      <Link href="/" className="flex items-center gap-3" aria-label="Clip Finder home">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#c4f56b] text-lg font-black text-[#141b0b]">c.</span>
        <span className="text-[15px] font-semibold tracking-[-.04em]">clipfinder<span className="ml-1 text-[#9ca6b4]">/ studio</span></span>
      </Link>
      <div className="hidden items-center gap-8 text-[12px] text-[#9ca6b4] md:flex">
        <a href="#workflow" className="transition hover:text-white">Workflow</a>
        <a href="#principles" className="transition hover:text-white">Built for real work</a>
      </div>
      <div className="flex items-center gap-2">
        <Link href="/login" className="rounded-xl px-3 py-2 text-[12px] font-semibold text-[#c2c9d3] transition hover:text-white">Sign in</Link>
        <Link href="/signup" className="cf-button cf-button-primary">Get started <span aria-hidden="true">↗</span></Link>
      </div>
    </nav>

    <section className="relative z-[1] mx-auto grid max-w-[1320px] items-center gap-12 px-5 pb-20 pt-14 sm:px-8 md:pt-24 lg:grid-cols-[1.05fr_.95fr] lg:px-12 lg:pb-28">
      <div className="cf-rise">
        <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[.035] px-3 py-2 text-[10px] font-semibold tracking-wide text-[#c2c9d3]">
          <span className="h-1.5 w-1.5 rounded-full bg-[#c4f56b] shadow-[0_0_14px_#c4f56b]" />
          CREATOR WORKFLOW · SOURCE TO SHORT
        </div>
        <h1 className="max-w-[760px] text-[clamp(3.4rem,7.1vw,6.5rem)] font-semibold leading-[.94] tracking-[-.075em]">The good part is <span className="text-[#c4f56b]">in there.</span></h1>
        <p className="mt-7 max-w-xl text-[15px] leading-7 text-[#9ca6b4] sm:text-[17px] sm:leading-8">Find the moments worth sharing inside your long videos. Then shape them in a focused editing workspace built for creators who care about the cut.</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/signup" className="cf-button cf-button-primary min-h-[50px] px-5">Start finding clips <span aria-hidden="true">↗</span></Link>
          <Link href="/login" className="cf-button cf-button-secondary min-h-[50px] px-5">Open your workspace</Link>
        </div>
        <div className="mt-8 flex flex-wrap gap-2">{tags.map(tag => <span key={tag} className="rounded-full border border-white/[.08] px-3 py-1.5 text-[10px] text-[#8792a1]">{tag}</span>)}</div>
        <p className="mt-9 text-[10px] leading-5 text-[#697585]">Use media you own or have permission to process. Results reflect analysis of the source provided.</p>
      </div>

      <div className="relative mx-auto w-full max-w-[590px] cf-rise" style={{ animationDelay: "100ms" }}>
        <div className="cf-glow pointer-events-none absolute -inset-16" />
        <div className="cf-panel relative overflow-hidden rounded-[24px] p-3 sm:p-4">
          <div className="flex items-center justify-between border-b border-white/[.07] px-2 pb-4 pt-2">
            <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-[#c4f56b]" /><span className="text-[11px] font-semibold">Moment review</span></div>
            <span className="rounded-md border border-white/10 px-2 py-1 text-[9px] text-[#8792a1]">WORKSPACE PREVIEW</span>
          </div>
          <div className="relative mt-3 flex aspect-[16/9] items-center justify-center overflow-hidden rounded-[16px] border border-white/[.07] bg-[#151c25]">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_45%,rgba(196,245,107,.15),transparent_44%),linear-gradient(145deg,#222d38,#10151d_65%)]" />
            <div className="absolute inset-0 opacity-30" style={{backgroundImage:"linear-gradient(125deg,transparent 44%,rgba(255,255,255,.08) 45%,transparent 46%),linear-gradient(25deg,transparent 60%,rgba(255,255,255,.05) 61%,transparent 62%)"}} />
            <div className="relative grid h-14 w-14 place-items-center rounded-full border border-white/25 bg-black/25 text-xl backdrop-blur">▶</div>
            <span className="absolute bottom-3 left-3 rounded-md bg-black/55 px-2 py-1 font-mono text-[10px] text-white/80">00:04:18:12</span>
            <span className="absolute bottom-3 right-3 rounded-md bg-black/55 px-2 py-1 text-[9px] text-[#c4f56b]">SOURCE PREVIEW</span>
          </div>
          <div className="grid gap-3 p-2 pt-4 sm:grid-cols-[.85fr_1.15fr]">
            <div className="rounded-xl border border-white/[.07] bg-black/15 p-3">
              <p className="cf-eyebrow">Candidate moment</p><p className="mt-2 text-sm font-semibold">The unexpected turn</p><p className="mt-1 text-[10px] text-[#8792a1]">04:18 — 04:52 · 34 sec</p>
              <div className="mt-4 flex items-center gap-2"><span className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10"><span className="block h-full w-[82%] rounded-full bg-[#c4f56b]" /></span><span className="text-[10px] text-[#c4f56b]">Ranked</span></div>
            </div>
            <div className="rounded-xl border border-white/[.07] bg-black/15 p-3">
              <div className="flex items-center justify-between"><p className="text-[10px] font-semibold text-[#c2c9d3]">Timeline overview</p><span className="text-[9px] text-[#8792a1]">SOURCE TIME</span></div>
              <div className="mt-4 flex h-12 items-end gap-[3px]" aria-label="Illustrative timeline design, not processing results">{Array.from({length:46},(_,i)=><span key={i} className="flex-1 rounded-t-[2px]" style={{height:`${15+((i*19+7)%29)}%`,background:i>16&&i<29?"#c4f56b":"#3d4857",opacity:i>16&&i<29?1:.7}} />)}</div>
              <div className="mt-3 flex justify-between font-mono text-[9px] text-[#697585]"><span>00:00</span><span>10:00</span><span>20:00</span></div>
            </div>
          </div>
        </div>
        <p className="mt-3 text-center text-[9px] text-[#697585]">Illustrative interface preview · no generated results are implied</p>
      </div>
    </section>

    <section id="workflow" className="relative z-[1] border-y border-white/[.07] bg-white/[.018]">
      <div className="mx-auto max-w-[1320px] px-5 py-16 sm:px-8 lg:px-12 lg:py-20">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><p className="cf-eyebrow">A cleaner workflow</p><h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-[-.055em] sm:text-4xl">From hours of footage to a cut worth keeping.</h2></div><p className="max-w-md text-sm leading-6 text-[#8792a1]">Every stage has one job. Analyze the actual media, review the candidates, refine the edit, and export a real file.</p></div>
        <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{steps.map((step,i)=><article key={step.n} className="cf-panel rounded-2xl p-5 transition duration-200 hover:-translate-y-1 hover:border-[#c4f56b]/30"><div className="flex items-center justify-between"><span className="font-mono text-[10px] text-[#c4f56b]">{step.n}</span><span className="grid h-9 w-9 place-items-center rounded-xl bg-white/[.05] text-lg text-[#c4f56b]">{step.icon}</span></div><h3 className="mt-8 text-[15px] font-semibold">{step.title}</h3><p className="mt-2 text-[12px] leading-6 text-[#8792a1]">{step.text}</p></article>)}</div>
      </div>
    </section>

    <section id="principles" className="relative z-[1] mx-auto flex max-w-[1320px] flex-col gap-8 px-5 py-16 sm:px-8 md:flex-row md:items-center md:justify-between lg:px-12 lg:py-20">
      <div><p className="cf-eyebrow">Built around trust</p><h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-[-.055em] sm:text-4xl">Real media in. Real files out.</h2><p className="mt-4 max-w-2xl text-sm leading-7 text-[#8792a1]">Clip Finder never invents clip results or pretends a render has completed. If a processing step fails, the workspace should tell you what happened.</p></div>
      <Link href="/signup" className="cf-button cf-button-primary shrink-0 self-start md:self-auto">Build your first project <span aria-hidden="true">↗</span></Link>
    </section>
    <footer className="relative z-[1] border-t border-white/[.07] px-5 py-6 sm:px-8 lg:px-12"><div className="mx-auto flex max-w-[1320px] flex-col gap-2 text-[10px] text-[#697585] sm:flex-row sm:items-center sm:justify-between"><span>© {new Date().getFullYear()} Clip Finder Studio</span><span>Made for the moments worth sharing.</span></div></footer>
  </main>;
}
