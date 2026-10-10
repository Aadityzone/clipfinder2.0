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

  return <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#080a0d] px-5 py-12 text-white">
    <div className="pointer-events-none absolute inset-0 cf-grid opacity-50"/><div className="pointer-events-none absolute -top-48 left-1/2 h-[550px] w-[700px] -translate-x-1/2 rounded-full cf-glow"/>
    <div className="relative z-10 grid w-full max-w-[960px] overflow-hidden rounded-[28px] border border-white/10 bg-[#0e1218]/95 shadow-2xl md:grid-cols-[.95fr_1.05fr]">
      <aside className="relative hidden flex-col justify-between overflow-hidden border-r border-white/[.07] bg-[#11171d] p-9 md:flex"><div className="absolute -right-24 top-24 h-72 w-72 rounded-full bg-[#c4f36b]/[.07] blur-3xl"/><Brand/><div className="relative py-12"><p className="cf-kicker">Your creative workspace</p><h1 className="mt-5 text-4xl font-semibold leading-[1.06] tracking-[-.05em]">Good to have you <span className="text-[#c4f36b]">back.</span></h1><p className="mt-5 max-w-xs text-sm leading-6 text-zinc-400">Pick up where you left off. Your projects and selected moments are waiting.</p></div><div className="relative flex items-center gap-3 text-xs text-zinc-500"><span className="h-2 w-2 rounded-full bg-[#c4f36b]"/> A calmer way to find the moment</div></aside>
      <section className="p-6 sm:p-10 md:p-12"><div className="md:hidden"><Brand/></div><div className="mt-7 md:mt-4"><p className="cf-kicker">Welcome back</p><h2 className="mt-3 text-3xl font-semibold tracking-[-.04em]">Sign in to your account</h2><p className="mt-2 text-sm text-zinc-400">Continue turning long videos into standout clips.</p></div>
        <form onSubmit={go} className="mt-8 space-y-5">
          <div><label className="cf-label" htmlFor="email">Email address</label><input className="cf-input" id="email" name="email" type="email" autoComplete="email" required placeholder="you@example.com"/></div>
          <div><div className="mb-2 flex items-center justify-between"><label className="cf-label !mb-0" htmlFor="password">Password</label></div><input className="cf-input" id="password" name="password" type="password" autoComplete="current-password" required placeholder="Enter your password"/></div>
          {error && <p role="alert" aria-live="polite" className="rounded-xl border border-red-400/20 bg-red-400/[.08] p-3 text-sm text-red-300">{error}</p>}
          <button disabled={busy} className="cf-button w-full !min-h-12">{busy ? "Signing in…" : "Sign in"} <span aria-hidden="true">↗</span></button>
        </form>
        <p className="mt-7 text-center text-sm text-zinc-500">New to Clip Finder? <Link href="/signup" className="font-medium text-[#c4f36b] hover:underline">Create an account</Link></p>
        <Link href="/" className="mt-8 block text-center text-xs text-zinc-600 transition hover:text-zinc-300">← Back to home</Link>
      </section>
    </div>
  </main>;
}