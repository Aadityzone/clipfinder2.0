"use client";

import { useEffect, useState } from "react";

export default function LongFormRender({ projectId, initialStatus }: { projectId: string; initialStatus: string }) {
  const [status, setStatus] = useState(initialStatus);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    if (["READY", "FAILED"].includes(status)) return;
    const timer = setInterval(() => {
      fetch(`/api/projects/${projectId}/long-form`).then(r => r.ok ? r.json() : null).then(data => {
        if (data?.renderStatus) setStatus(data.renderStatus);
      }).catch(() => {});
    }, 3000);
    return () => clearInterval(timer);
  }, [projectId, status]);
  async function render() {
    setBusy(true); setMessage("");
    try {
      const response = await fetch(`/api/projects/${projectId}/long-form`, { method: "POST" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error ?? "Could not queue long-form render.");
      setStatus("QUEUED");
      setMessage("Render queued. This status will update while the worker processes the video.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Render request failed."); }
    finally { setBusy(false); }
  }
  const tone = status === "READY" ? "text-emerald-200 bg-emerald-300/[.07]" : status === "FAILED" ? "text-red-200 bg-red-300/[.07]" : "text-[#d7f9a7] bg-[#c4f36b]/[.06]";
  return <div><div className="flex items-center justify-between gap-3"><span className="text-xs text-zinc-500">Render status</span><span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${tone}`}>{status.toLowerCase()}</span></div><button onClick={() => void render()} disabled={busy || ["QUEUED", "PROCESSING"].includes(status)} className="cf-button mt-4 w-full">{busy ? "Queueing render…" : status === "READY" ? "↻ Re-render long-form" : "▶ Render long-form"}</button>{message && <p role="status" className="mt-3 text-xs leading-5 text-zinc-500">{message}</p>}</div>;
}
