import Link from "next/link";
export default function HomePage(){
  return <main className="min-h-screen px-6 py-24"><div className="mx-auto max-w-5xl">
    <p className="mb-5 font-mono text-xs uppercase tracking-[0.25em] text-lime-300">Clip Finder 2.0</p>
    <h1 className="max-w-4xl text-5xl font-semibold tracking-tight md:text-7xl">AI finds the moments. You make the calls.</h1>
    <p className="mt-7 max-w-2xl text-lg text-zinc-400">Analyze real long-form video, discover high-value moments, edit them precisely, and render real clips.</p>
    <div className="mt-10 flex gap-4"><Link className="rounded-full bg-lime-300 px-6 py-3 font-semibold text-black" href="/signup">Get started</Link><Link className="rounded-full border border-white/15 px-6 py-3" href="/login">Sign in</Link></div>
  </div></main>
}