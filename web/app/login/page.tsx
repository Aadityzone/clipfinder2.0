"use client";

import { useState } from "react";
import Link from "next/link";

type ApiResponse = { error?: string; user?: { id: string } };
async function readApiResponse(response: Response): Promise<ApiResponse> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return { error: "The server returned an unexpected response. Check the server logs." };
  try { return await response.json() as ApiResponse; }
  catch { return { error: "The server returned an empty or invalid response. Please try again." }; }
}

export default function Login() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function go(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/auth/login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: form.get("email"), password: form.get("password") }) });
      const data = await readApiResponse(response);
      if (!response.ok) { setError(data.error ?? "Unable to sign in. Check your details and try again."); return; }
      if (!data.user) { setError("The server response was incomplete. Please try again."); return; }
      window.location.assign("/dashboard");
    } catch { setError("Couldn't reach Clip Finder. Check your connection and try again."); }
    finally { setBusy(false); }
  }
  return <main className="relative grid min-h-screen overflow-hidden lg:grid-cols-[1fr_.9fr]">
    <div className="pointer-events-none absolute inset-0 cf-grid opacity-50" />
    <section className="relative hidden min-h-screen flex-col justify-between border-r border-white/[.07] p-10 lg:flex xl:p-14">
      <Link href="/" className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-[#c4f56b] font-black text-[#141b0b]">c.</span><span className="text-sm font-semibold">clipfinder<span className="ml-1 text-[#8792a1]">/ studio</span></span></Link>
      <div className="relative max-w-xl"><p className="cf-eyebrow">Your creative control room</p><h1 className="mt-5 text-5xl font-semibold leading-[1.02] tracking-[-.07em] xl:text-6xl">Good cuts start with <span className="text-[#c4f56b]">good instincts.</span></h1><p className="mt-6 max-w-md text-sm leading-7 text-[#8792a1]">Pick up where you left off. Your projects, real analysis results, and editing workflow live in one place.</p><div className="cf-panel mt-10 rounded-2xl p-5"><div className="flex items-center justify-between"><span className="text-xs font-semibold">Your workflow</span><span className="text-[10px] text-[#8792a1]">SOURCE → SHORT</span></div><div className="mt-5 grid grid-cols-4 gap-2">{["Analyze","Discover","Edit","Export"].map((x,i)=><div key={x} className="rounded-xl border border-white/[.07] bg-white/[.025] p-3"><span className="font-mono text-[10px] text-[#c4f56b]">0{i+1}</span><p className="mt-3 text-[10px] font-medium">{x}</p></div>)}</div></div></div>
      <p className="text-[10px] text-[#697585]">Clip Finder Studio · Real media, honest results.</p>
    </section>
    <section className="relative flex min-h-screen items-center justify-center px-5 py-12 sm:px-8">
      <Link href="/" className="absolute left-5 top-6 flex items-center gap-2 text-xs text-[#8792a1] hover:text-white lg:hidden"><span className="text-[#c4f56b]">←</span> Back to home</Link>
      <form onSubmit={go} className="cf-rise w-full max-w-[410px]">
        <div className="mb-8"><p className="cf-eyebrow">Welcome back</p><h2 className="mt-3 text-3xl font-semibold tracking-[-.055em]">Sign in to your studio.</h2><p className="mt-2 text-sm leading-6 text-[#8792a1]">Your next great cut is waiting.</p></div>
        <label className="cf-label" htmlFor="email">Email address</label><input id="email" name="email" type="email" autoComplete="email" required placeholder="you@example.com" className="cf-input" />
        <div className="mt-5"><label className="cf-label" htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete="current-password" required placeholder="Your password" className="cf-input" /></div>
        {error && <p role="alert" aria-live="polite" className="mt-4 rounded-xl border border-rose-400/20 bg-rose-400/[.07] p-3 text-xs leading-5 text-rose-300">{error}</p>}
        <button disabled={busy} className="cf-button cf-button-primary mt-6 w-full disabled:cursor-not-allowed disabled:opacity-60">{busy ? "Signing in…" : "Sign in"} <span aria-hidden="true">↗</span></button>
        <p className="mt-6 text-center text-xs text-[#8792a1]">New to Clip Finder? <Link href="/signup" className="font-semibold text-[#c4f56b] hover:underline">Create an account</Link></p>
        <p className="mt-10 text-center text-[10px] leading-5 text-[#697585]">By continuing, use only media you own or have permission to process.</p>
      </form>
    </section>
  </main>;
}
