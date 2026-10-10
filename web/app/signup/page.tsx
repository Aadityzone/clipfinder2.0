"use client";

import { useState } from "react";
import Link from "next/link";

type ApiResponse = { error?: string; user?: { id: string } };

async function readApiResponse(response: Response): Promise<ApiResponse> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return { error: "The server returned an unexpected response. Check the server terminal for details." };
  try { return (await response.json()) as ApiResponse; }
  catch { return { error: "The server returned an empty or invalid response. Please try again." }; }
}

function Brand() {
  return <Link href="/" className="inline-flex items-center gap-2.5 font-semibold tracking-tight"><span className="grid h-9 w-9 place-items-center rounded-xl bg-[#c4f36b] text-[#12180a]"><svg viewBox="0 0 24 24" width="19" height="19" fill="none" aria-hidden="true"><path d="M7 5.5v13l11-6.5L7 5.5Z" fill="currentColor"/></svg></span><span>clip<span className="text-[#c4f36b]">finder</span><span className="ml-1 text-[10px] text-zinc-500">2.0</span></span></Link>;
}

export default function Signup() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function go(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/auth/signup", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: form.get("name"), email: form.get("email"), password: form.get("password") }) });
      const data = await readApiResponse(response);
      if (!response.ok) { setError(data.error ?? "Unable to create your account. Please try again."); return; }
      if (!data.user) { setError("Your account may have been created, but the response was incomplete. Try signing in."); return; }
      window.location.assign("/dashboard");
    } catch { setError("Couldn't reach Clip Finder. Check your connection and try again."); }
    finally { setBusy(false); }
  }
  return <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#080a0d] px-5 py-12 text-white">
    <div className="pointer-events-none absolute inset-0 cf-grid opacity-50"/><div className="pointer-events-none absolute -top-48 left-1/2 h-[550px] w-[700px] -translate-x-1/2 rounded-full cf-glow"/>
    <div className="relative z-10 grid w-full max-w-[960px] overflow-hidden rounded-[28px] border border-white/10 bg-[#0e1218]/95 shadow-2xl md:grid-cols-[.95fr_1.05fr]">
      <aside className="relative hidden flex-col justify-between overflow-hidden border-r border-white/[.07] bg-[#11171d] p-9 md:flex"><div className="absolute -right-24 top-24 h-72 w-72 rounded-full bg-[#c4f36b]/[.07] blur-3xl"/><Brand/><div className="relative py-12"><p className="cf-kicker">Made for the moments</p><h1 className="mt-5 text-4xl font-semibold leading-[1.06] tracking-[-.05em]">Less scrubbing.<br/><span className="text-[#c4f36b]">More creating.</span></h1><p className="mt-5 max-w-xs text-sm leading-6 text-zinc-400">Bring a source you can use. Discover the strongest moments, then make the final cut your own.</p></div><div className="relative text-xs text-zinc-500">Your creator workspace starts here.</div></aside>
      <section className="p-6 sm:p-10 md:p-12"><div className="md:hidden"><Brand/></div><div className="mt-7 md:mt-4"><p className="cf-kicker">Get started</p><h2 className="mt-3 text-3xl font-semibold tracking-[-.04em]">Create your workspace</h2><p className="mt-2 text-sm text-zinc-400">One account for every project and clip.</p></div>
        <form onSubmit={go} className="mt-7 space-y-4">
          <div><label className="cf-label" htmlFor="name">Name <span className="text-zinc-600">(optional)</span></label><input className="cf-input" id="name" name="name" autoComplete="name" placeholder="How should we call you?"/></div>
          <div><label className="cf-label" htmlFor="email">Email address</label><input className="cf-input" id="email" name="email" type="email" autoComplete="email" required placeholder="you@example.com"/></div>
          <div><label className="cf-label" htmlFor="password">Password</label><input className="cf-input" id="password" name="password" type="password" autoComplete="new-password" minLength={8} maxLength={1024} required placeholder="At least 8 characters"/><p className="mt-2 text-[11px] text-zinc-600">Use at least 8 characters.</p></div>
          {error && <p role="alert" aria-live="polite" className="rounded-xl border border-red-400/20 bg-red-400/[.08] p-3 text-sm text-red-300">{error}</p>}
          <button disabled={busy} className="cf-button w-full !min-h-12">{busy ? "Creating account…" : "Create account"} <span aria-hidden="true">↗</span></button>
        </form>
        <p className="mt-6 text-center text-sm text-zinc-500">Already have an account? <Link href="/login" className="font-medium text-[#c4f36b] hover:underline">Sign in</Link></p>
        <p className="mt-5 text-center text-[11px] leading-5 text-zinc-600">By creating an account, you agree to process only media you have permission to use.</p>
      </section>
    </div>
  </main>;
}