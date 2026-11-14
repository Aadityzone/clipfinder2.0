import Link from "next/link";
import { redirect } from "next/navigation";
import { getCurrentUser } from "../lib/auth";

const useCases = ["Gaming streams", "Podcasts", "Interviews", "Gameplay", "Creator videos"];

const steps = [
  {
    number: "01",
    title: "Bring your source",
    description: "Paste a supported YouTube, Twitch or Kick link, connect Google Drive, or upload a video.",
    icon: "↗",
  },
  {
    number: "02",
    title: "Find the moments",
    description: "Clip Finder analyzes the actual source and surfaces candidate moments worth reviewing.",
    icon: "⌁",
  },
  {
    number: "03",
    title: "Shape the clip",
    description: "Choose the moment, refine the timing, reframe the shot and prepare your captions.",
    icon: "◫",
  },
  {
    number: "04",
    title: "Export your edit",
    description: "Render a real video file when your cut is ready. You stay in control of the final result.",
    icon: "↓",
  },
];

const exampleMoments = [
  { title: "The unexpected turn", time: "04:18 – 04:52", type: "Unexpected", mark: "A" },
  { title: "That reaction", time: "12:06 – 12:31", type: "Reaction", mark: "B" },
  { title: "The one-line takeaway", time: "21:42 – 22:08", type: "Quotable", mark: "C" },
];

function Brand() {
  return (
    <Link href="/" className="inline-flex items-center gap-3" aria-label="Clip Finder home">
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#baf36b] text-[#10170b] shadow-[0_0_28px_rgba(186,243,107,.18)]">
        <svg viewBox="0 0 24 24" width="19" height="19" fill="none" aria-hidden="true">
          <path d="M7 5.5v13l11-6.5L7 5.5Z" fill="currentColor" />
          <path d="M3.5 8v8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </span>
      <span className="text-[15px] font-semibold tracking-[-.04em]">
        clip<span className="text-[#baf36b]">finder</span>
        <span className="ml-1.5 text-[10px] font-medium text-[#778274]">STUDIO</span>
      </span>
    </Link>
  );
}

export default async function HomePage() {
  const user = await getCurrentUser();
  if (user) redirect("/dashboard");

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#080b09] text-[#f3f6f1]">
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 opacity-50"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,.027) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.027) 1px, transparent 1px)",
          backgroundSize: "52px 52px",
          maskImage: "linear-gradient(to bottom, black, transparent 78%)",
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-72 left-[68%] h-[720px] w-[900px] -translate-x-1/2 rounded-full blur-3xl"
        style={{ background: "radial-gradient(ellipse, rgba(157,230,91,.13), transparent 68%)" }}
      />

      <header className="relative z-20 mx-auto flex max-w-[1380px] items-center justify-between px-5 py-5 sm:px-8 lg:px-12">
        <Brand />
        <nav aria-label="Main navigation" className="hidden items-center gap-8 text-[12px] font-medium text-[#9aa69a] md:flex">
          <a href="#how-it-works" className="transition hover:text-white">How it works</a>
          <a href="#features" className="transition hover:text-white">Features</a>
          <a href="#creators" className="transition hover:text-white">Made for creators</a>
        </nav>
        <div className="flex items-center gap-2">
          <Link href="/login" className="rounded-xl px-3 py-2.5 text-[12px] font-semibold text-[#b4beb3] transition hover:text-white">
            Log in
          </Link>
          <Link href="/signup" className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-[#baf36b] px-4 text-[12px] font-bold text-[#11180c] shadow-[0_8px_28px_rgba(186,243,107,.12)] transition hover:-translate-y-0.5 hover:bg-[#ceff8b]">
            Get started <span aria-hidden="true">↗</span>
          </Link>
        </div>
      </header>

      <section className="relative z-10 mx-auto grid max-w-[1380px] items-center gap-12 px-5 pb-20 pt-12 sm:px-8 md:pt-20 lg:grid-cols-[.92fr_1.08fr] lg:gap-14 lg:px-12 lg:pb-28">
        <div className="relative z-10">
          <div className="mb-7 inline-flex items-center gap-2.5 rounded-full border border-[#baf36b]/20 bg-[#baf36b]/[.055] px-3.5 py-2 text-[10px] font-semibold tracking-[.12em] text-[#c9f69a]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#baf36b] shadow-[0_0_12px_#baf36b]" />
            AI CLIP DISCOVERY · SOURCE TO SHORT
          </div>
          <h1 className="max-w-[720px] text-[clamp(3.15rem,6.3vw,6.35rem)] font-semibold leading-[.94] tracking-[-.075em]">
            The best part
            <br />
            is <span className="text-[#baf36b]">in your video.</span>
          </h1>
          <p className="mt-7 max-w-[550px] text-[15px] leading-7 text-[#a0aca0] sm:text-[17px] sm:leading-8">
            Turn long streams, podcasts and recordings into clips worth sharing. Find the moments with AI, shape every cut in your editor, and export when it feels right.
          </p>

          <form action="/project/new" method="get" className="mt-8 flex max-w-[650px] flex-col gap-2 rounded-2xl border border-white/[.11] bg-[#111713]/90 p-2 shadow-[0_28px_90px_rgba(0,0,0,.38)] sm:flex-row sm:items-center">
            <label className="sr-only" htmlFor="hero-source-url">Paste a supported video URL</label>
            <div className="flex min-w-0 flex-1 items-center gap-3 px-3">
              <svg className="shrink-0 text-[#7d8a7d]" viewBox="0 0 24 24" width="19" height="19" fill="none" aria-hidden="true">
                <path d="M10.5 4.5h-4a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-4M13 4h7v7M20 4l-9 9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <input
                id="hero-source-url"
                className="min-h-12 min-w-0 flex-1 bg-transparent py-3 text-[13px] text-white outline-none placeholder:text-[#718071]"
                type="url"
                name="sourceUrl"
                required
                placeholder="Paste a YouTube, Twitch or Kick link"
              />
            </div>
            <button type="submit" className="inline-flex min-h-12 shrink-0 items-center justify-center gap-2 rounded-xl bg-[#baf36b] px-5 text-[13px] font-bold text-[#11180c] transition hover:bg-[#ceff8b]">
              Find my clips <span aria-hidden="true">↗</span>
            </button>
          </form>
          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 px-1 text-[11px] text-[#788579]">
            <span>Or <Link href="/project/new" className="font-semibold text-[#c5ed9b] underline decoration-[#c5ed9b]/30 underline-offset-4 hover:text-white">upload a video</Link></span>
            <span className="text-[#465247]">·</span>
            <span>YouTube · Twitch · Kick · Google Drive</span>
          </div>

          <div className="mt-8 flex flex-wrap gap-2">
            {useCases.map((item) => (
              <span key={item} className="rounded-full border border-white/[.09] bg-white/[.025] px-3 py-1.5 text-[10px] font-medium text-[#a1ada1]">
                {item}
              </span>
            ))}
          </div>
          <p className="mt-7 max-w-md text-[10px] leading-5 text-[#687568]">
            Use media you own or have permission to process. You review every candidate before exporting.
          </p>
        </div>

        <div className="relative mx-auto w-full max-w-[700px]">
          <div aria-hidden="true" className="pointer-events-none absolute -inset-10 rounded-[40px] blur-3xl" style={{ background: "radial-gradient(ellipse, rgba(151,226,87,.12), transparent 68%)" }} />
          <div className="relative overflow-hidden rounded-[25px] border border-white/[.12] bg-[#0e1410]/95 p-3 shadow-[0_35px_110px_rgba(0,0,0,.55)] sm:p-4">
            <div className="flex items-center justify-between gap-3 border-b border-white/[.08] px-2 pb-4 pt-1">
              <div className="flex items-center gap-2.5">
                <span className="h-2 w-2 rounded-full bg-[#baf36b] shadow-[0_0_10px_#baf36b]" />
                <span className="text-[11px] font-semibold tracking-wide text-[#e4ebe1]">CLIP FINDER WORKSPACE</span>
              </div>
              <span className="rounded-md border border-white/[.1] bg-white/[.025] px-2.5 py-1 text-[9px] font-semibold tracking-[.1em] text-[#94a091]">PRODUCT PREVIEW</span>
            </div>

            <div className="grid gap-3 pt-3 lg:grid-cols-[1.2fr_.8fr]">
              <div className="relative flex aspect-[16/10] min-h-[230px] items-center justify-center overflow-hidden rounded-2xl border border-white/[.08] bg-[#151e18]">
                <div aria-hidden="true" className="absolute inset-0" style={{ background: "radial-gradient(ellipse at 70% 25%, rgba(173,239,103,.18), transparent 35%), radial-gradient(ellipse at 20% 80%, rgba(55,117,74,.22), transparent 45%), linear-gradient(145deg,#24332a,#101713 68%)" }} />
                <div aria-hidden="true" className="absolute inset-0 opacity-25" style={{ backgroundImage: "linear-gradient(125deg, transparent 43%, rgba(255,255,255,.12) 44%, transparent 45%), linear-gradient(25deg, transparent 60%, rgba(255,255,255,.08) 61%, transparent 62%)" }} />
                <div className="relative grid h-14 w-14 place-items-center rounded-full border border-white/30 bg-black/30 text-lg text-white shadow-xl backdrop-blur">
                  <span className="translate-x-px">▶</span>
                </div>
                <span className="absolute bottom-3 left-3 rounded-md border border-white/10 bg-black/55 px-2 py-1 font-mono text-[9px] text-white/80">SOURCE VIDEO · 24:18</span>
                <span className="absolute bottom-3 right-3 rounded-md bg-[#baf36b] px-2 py-1 text-[9px] font-bold text-[#11180c]">16:9 SOURCE</span>
              </div>

              <aside className="rounded-2xl border border-white/[.08] bg-[#090e0b]/70 p-3.5">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-bold tracking-[.13em] text-[#b9c5b7]">MOMENTS TO REVIEW</p>
                  <span className="text-[9px] text-[#788579]">EXAMPLE</span>
                </div>
                <div className="mt-3 space-y-2.5">
                  {exampleMoments.map((moment) => (
                    <div key={moment.mark} className="rounded-xl border border-white/[.07] bg-white/[.025] p-3">
                      <div className="flex items-start gap-2.5">
                        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-[#baf36b]/20 bg-[#baf36b]/[.07] font-mono text-[10px] text-[#c5ef9c]">{moment.mark}</span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[11px] font-semibold text-[#e6ece3]">{moment.title}</p>
                          <p className="mt-1 text-[9px] text-[#7d897c]">{moment.time}</p>
                        </div>
                      </div>
                      <div className="mt-2.5 flex items-center justify-between">
                        <span className="rounded-full border border-white/[.08] px-2 py-1 text-[8px] text-[#9ba797]">{moment.type}</span>
                        <span className="text-[9px] text-[#baf36b]">Review candidate ↗</span>
                      </div>
                    </div>
                  ))}
                </div>
              </aside>
            </div>

            <div className="mt-3 rounded-2xl border border-white/[.08] bg-[#090e0b]/70 p-3.5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[10px] font-bold tracking-[.13em] text-[#b9c5b7]">EDIT TIMELINE</p>
                  <p className="mt-1 text-[9px] text-[#788579]">Refine the in-point and out-point</p>
                </div>
                <span className="rounded-md border border-white/[.08] px-2 py-1 font-mono text-[9px] text-[#9ba797]">00:00 — 24:18</span>
              </div>
              <div className="mt-3 flex h-10 items-end gap-[3px]" aria-label="Illustrative timeline design, not actual analysis results">
                {Array.from({ length: 48 }, (_, index) => (
                  <span
                    key={index}
                    className="flex-1 rounded-t-[2px]"
                    style={{
                      height: `${16 + ((index * 17 + 11) % 28)}%`,
                      background: index > 17 && index < 29 ? "#baf36b" : "#536052",
                      opacity: index > 17 && index < 29 ? 1 : 0.62,
                    }}
                  />
                ))}
              </div>
              <div className="mt-2 flex justify-between font-mono text-[8px] text-[#647064]"><span>00:00</span><span>08:06</span><span>16:12</span><span>24:18</span></div>
            </div>
            <p className="px-1 pb-1 pt-3 text-center text-[9px] text-[#687568]">Illustrative interface preview · example content, not generated results</p>
          </div>
        </div>
      </section>

      <section id="how-it-works" className="relative z-10 border-y border-white/[.07] bg-[#0d130f]/70">
        <div className="mx-auto max-w-[1380px] px-5 py-16 sm:px-8 lg:px-12 lg:py-20">
          <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
            <div>
              <p className="text-[10px] font-bold tracking-[.2em] text-[#baf36b]">HOW IT WORKS</p>
              <h2 className="mt-3 max-w-2xl text-3xl font-semibold leading-tight tracking-[-.055em] sm:text-4xl">From hours of footage to a cut worth keeping.</h2>
            </div>
            <p className="max-w-md text-[13px] leading-6 text-[#8f9c8f]">A simple workflow that keeps the creator in control, from the original source to the final export.</p>
          </div>
          <div className="mt-9 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {steps.map((step) => (
              <article key={step.number} className="group rounded-2xl border border-white/[.08] bg-white/[.025] p-5 transition duration-200 hover:-translate-y-1 hover:border-[#baf36b]/25 hover:bg-white/[.04]">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-[#baf36b]">{step.number}</span>
                  <span className="grid h-9 w-9 place-items-center rounded-xl border border-white/[.08] bg-black/20 text-lg text-[#baf36b] transition group-hover:border-[#baf36b]/25">{step.icon}</span>
                </div>
                <h3 className="mt-7 text-[14px] font-semibold text-[#edf2eb]">{step.title}</h3>
                <p className="mt-2 text-[11px] leading-5 text-[#899689]">{step.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="features" className="relative z-10 mx-auto max-w-[1380px] px-5 py-16 sm:px-8 lg:px-12 lg:py-20">
        <div className="max-w-2xl">
          <p className="text-[10px] font-bold tracking-[.2em] text-[#baf36b]">BUILT FOR THE CUT</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-[-.055em] sm:text-4xl">More than finding a timestamp.</h2>
          <p className="mt-4 text-[13px] leading-6 text-[#8f9c8f]">Discover a moment, understand its context, and turn it into an edit you are happy to publish.</p>
        </div>
        <div className="mt-8 grid gap-3 md:grid-cols-3">
          <article className="rounded-2xl border border-white/[.08] bg-[#0e1510] p-6">
            <span className="text-[10px] font-mono text-[#baf36b]">01 / DISCOVER</span>
            <h3 className="mt-6 text-lg font-semibold">Find the moment, not just loud audio.</h3>
            <p className="mt-3 text-[12px] leading-6 text-[#8f9c8f]">Transcript, audio and visual signals help surface candidate moments from the actual source.</p>
          </article>
          <article className="rounded-2xl border border-white/[.08] bg-[#0e1510] p-6">
            <span className="text-[10px] font-mono text-[#baf36b]">02 / REFINE</span>
            <h3 className="mt-6 text-lg font-semibold">Keep the story intact.</h3>
            <p className="mt-3 text-[12px] leading-6 text-[#8f9c8f]">Review the context, trim the timing, reframe the shot and prepare captions in your workspace.</p>
          </article>
          <article className="rounded-2xl border border-white/[.08] bg-[#0e1510] p-6">
            <span className="text-[10px] font-mono text-[#baf36b]">03 / EXPORT</span>
            <h3 className="mt-6 text-lg font-semibold">Make it ready for short-form.</h3>
            <p className="mt-3 text-[12px] leading-6 text-[#8f9c8f]">Render your finished edit as a video file for Shorts, Reels and TikTok.</p>
          </article>
        </div>
      </section>

      <section id="creators" className="relative z-10 mx-auto max-w-[1380px] px-5 pb-12 sm:px-8 lg:px-12 lg:pb-16">
        <div className="relative overflow-hidden rounded-[26px] border border-[#baf36b]/15 bg-[#111a12] p-7 sm:p-10 lg:p-12">
          <div aria-hidden="true" className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 rounded-full blur-3xl" style={{ background: "radial-gradient(ellipse, rgba(186,243,107,.13), transparent 68%)" }} />
          <div className="relative flex flex-col items-start justify-between gap-7 md:flex-row md:items-center">
            <div>
              <p className="text-[10px] font-bold tracking-[.2em] text-[#baf36b]">YOUR NEXT CLIP STARTS HERE</p>
              <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-[-.05em] sm:text-4xl">The moment is already recorded. Find it.</h2>
              <p className="mt-3 max-w-xl text-[12px] leading-6 text-[#9aa697]">Bring a source you have permission to use. Clip Finder helps you find the moments and shape the final cut.</p>
            </div>
            <Link href="/signup" className="relative inline-flex min-h-12 shrink-0 items-center gap-2 rounded-xl bg-[#baf36b] px-5 text-[13px] font-bold text-[#11180c] transition hover:-translate-y-0.5 hover:bg-[#ceff8b]">
              Start creating <span aria-hidden="true">↗</span>
            </Link>
          </div>
        </div>
        <footer className="mt-8 flex flex-col justify-between gap-3 border-t border-white/[.07] pt-5 text-[10px] text-[#6f7c6e] sm:flex-row sm:items-center">
          <Brand />
          <span>© {new Date().getFullYear()} Clip Finder Studio · Made for the moments worth sharing.</span>
          <span>Use media you own or have permission to process.</span>
        </footer>
      </section>
    </main>
  );
}
