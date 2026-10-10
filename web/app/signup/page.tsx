"use client";

import { useState } from "react";
import Link from "next/link";

type ApiResponse = { error?: string; user?: { id: string } };

async function readApiResponse(response: Response): Promise<ApiResponse> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return { error: "The server returned an unexpected response. Check the terminal for the API error." };
  }

  try {
    return (await response.json()) as ApiResponse;
  } catch {
    return { error: "The server returned an empty or invalid response. Check the terminal for the API error." };
  }
}

export default function Signup() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function go(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;

    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);

    try {
      const response = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          name: form.get("name"),
          email: form.get("email"),
          password: form.get("password"),
        }),
      });
      const data = await readApiResponse(response);

      if (!response.ok) {
        setError(data.error ?? "Unable to create your account. Please try again.");
        return;
      }

      if (!data.user) {
        setError("Your account may have been created, but the server response was incomplete. Try signing in.");
        return;
      }

      window.location.assign("/dashboard");
    } catch {
      setError("Couldn't reach Clip Finder. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen p-8">
      <form onSubmit={go} className="mx-auto mt-20 max-w-md rounded-3xl border border-white/10 p-8">
        <h1 className="text-3xl font-semibold">Create your account</h1>
        <p className="mt-2 text-sm text-zinc-400">Start turning long videos into standout clips.</p>
        <label className="mt-8 block text-sm text-zinc-300" htmlFor="name">Name (optional)</label>
        <input id="name" name="name" autoComplete="name" placeholder="Your name" className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 p-4" />
        <label className="mt-4 block text-sm text-zinc-300" htmlFor="email">Email</label>
        <input id="email" name="email" type="email" autoComplete="email" required placeholder="you@example.com" className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 p-4" />
        <label className="mt-4 block text-sm text-zinc-300" htmlFor="password">Password</label>
        <input id="password" name="password" type="password" autoComplete="new-password" minLength={8} maxLength={1024} required placeholder="At least 8 characters" className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 p-4" />
        {error && <p role="alert" aria-live="polite" className="mt-4 rounded-xl border border-red-400/20 bg-red-400/10 p-3 text-sm text-red-300">{error}</p>}
        <button disabled={busy} className="mt-6 w-full rounded-full bg-lime-300 px-5 py-3 font-semibold text-black disabled:cursor-not-allowed disabled:opacity-60">
          {busy ? "Creating account…" : "Create account"}
        </button>
        <p className="mt-5 text-center text-sm text-zinc-500">
          Already have an account? <Link href="/login" className="text-lime-300">Sign in</Link>
        </p>
      </form>
    </main>
  );
}
