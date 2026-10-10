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

export default function Signup() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function go(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/auth/signup", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: form.get("name"), email: form.get("email"), password: form.get("password") }) });
      const data = await readApiResponse(response);
      if (!response.ok) { setError(data.error ?? "Unable to create your account. Please try again."); return; }
      if (!data.user) { setError("The server response was incomplete. Try signing in before creating another account."); return; }
      window.location.assign("/dashboard");
    } catch { setError("Couldn't reach Clip Finder. Check your connection and try again."); }
    finally { setBusy(false); }
  }
  return <main className="relative grid min-h-screen overflow-hidden lg:grid-cols-[1fr_.9fr]">
    <div className="pointer-events-none absolute inset-0 cf-grid opacity-50" />
    <section className="relative hidden min-h-screen flex-col justify-between border-r border-white/[.07] p-10 lg:flex xl:p-14">
      <Link href="/" className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-[#c4f56b] font-black text-[#141b0b]">c.</span><span className="text-sm font-semibold">clipfinder<span className="ml-1 text-[#8792a1]">/ studio</span></span></Link>
      <div className="relative max-w-xl"><p className="cf-eyebrow">Your ideas, in the cut</p><h1 className="mt-5 text-5xl font-semibold leading-[1.02] tracking-[-.07em] xl:text-6xl">Hours in. <span className="text-[#c4f56b]">Highlights out.</span></h1><p className="mt-6 max-w-md text-sm leading-7 text-[#8792a1]">Create your studio to analyze actual footage, review the best moments, and refine every cut yourself.</p><div className="mt-10 space-y-3">{["Analysis based on the source you provide","A real editor with timestamp-based controls","Honest processing status and export results"].map((x,i)=><div key={x} className="flex items-center gap-3 rounded-xl border border-white/[.07] bg-white/[.02] p-3 text-xs text-[#c2c9d3]"><span className="grid h-6 w-6 place-items-center rounded-lg bg-[#c4f56b]/10 text-[#c4f56b]">{i+1}</span>{x}</div>)}</div></div>
      <p className="text-[10px] text-[#697585]">Clip Finder Studio · Made for the moments worth sharing.</p>
    </section>
    <section className="relative flex min-h-screen items-center justify-center px-5 py-12 sm:px-8">
      <Link href="/" className="absolute left-5 top-6 flex items-center gap-2 text-xs text-[#8792a1] hover:text-white lg:hidden"><span className="text-[#c4f56b]">←</span> Back to home</Link>
      <form onSubmit={go} className="cf-rise w-full max-w-[410px]">
        <div className="mb-7"><p className="cf-eyebrow">Start your studio</p><h2 className="mt-3 text-3xl font-semibold tracking-[-.055em]">Make room for the good parts.</h2><p className="mt-2 text-sm leading-6 text-[#8792a1]">Create an account and start your first project.</p></div>
        <label className="cf-label" htmlFor="name">Your name <span className="font-normal text-[#697585]">(optional)</span></label><input id="name" name="name" autoComplete="name" placeholder="How should we call you?" className="cf-input" />
        <div className="mt-4"><label className="cf-label" htmlFor="email">Email address</label><input id="email" name="email" type="email" autoComplete="email" required placeholder="you@example.com" className="cf-input" /></div>
        <div className="mt-4"><label className="cf-label" htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete="new-password" minLength={8} maxLength={1024} required placeholder="At least 8 characters" className="cf-input" /><p className="mt-2 text-[10px] text-[#697585]">Use at least 8 characters. Keep it unique to Clip Finder.</p></div>
        {error && <p role="alert" aria-live="polite" className="mt-4 rounded-xl border border-rose-400/20 bg-rose-400/[.07] p-3 text-xs leading-5 text-rose-300">{error}</p>}
        <button disabled={busy} className="cf-button cf-button-primary mt-6 w-full disabled:cursor-not-allowed disabled:opacity-60">{busy ? "Creating your account…" : "Create account"} <span aria-hidden="true">↗</span></button>
        <p className="mt-6 text-center text-xs text-[#8792a1]">Already have an account? <Link href="/login" className="font-semibold text-[#c4f56b] hover:underline">Sign in</Link></p>
        <p className="mt-8 text-center text-[10px] leading-5 text-[#697585]">Continue only with media you own or have permission to process.</p>
      </form>
    </section>
  </main>;
}
