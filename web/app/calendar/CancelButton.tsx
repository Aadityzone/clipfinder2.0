"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type CancelResponse = { error?: string };

export default function CancelButton({ id }: { id: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function cancel() {
    if (busy || !window.confirm("Cancel this scheduled post?")) return;
    setBusy(true);
    setError("");

    try {
      const response = await fetch(`/api/scheduled-posts/${encodeURIComponent(id)}`, { method: "POST" });
      let data: CancelResponse = {};
      try {
        data = (await response.json()) as CancelResponse;
      } catch {
        if (response.ok) throw new Error("The server returned an empty response.");
      }
      if (!response.ok) throw new Error(data.error || "The scheduled post could not be cancelled.");
      router.refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Couldn't cancel the scheduled post. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-2 sm:items-end">
      <button
        type="button"
        onClick={() => void cancel()}
        disabled={busy}
        aria-busy={busy}
        className="cf-button min-h-10 border border-rose-300/20 bg-rose-300/[.04] px-4 text-xs text-rose-200 transition hover:border-rose-300/40 hover:bg-rose-300/[.08] disabled:cursor-wait disabled:opacity-50"
      >
        {busy ? "Cancelling…" : "Cancel post"}
      </button>
      {error && <p role="alert" aria-live="assertive" className="max-w-56 text-xs leading-5 text-rose-300">{error}</p>}
    </div>
  );
}
