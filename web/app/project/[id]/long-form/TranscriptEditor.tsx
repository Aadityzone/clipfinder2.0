"use client";
import { useEffect, useState } from "react";

type Seg = { id: string; transcriptId: string; startS: number; endS: number; text: string };

export default function TranscriptEditor({ projectId }: { projectId: string }) {
  const [rows, setRows] = useState<Seg[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => {
    fetch("/api/projects/" + projectId + "/transcript")
      .then((response) => response.json())
      .then((data) => setRows(data?.segments || []))
      .catch(() => {});
  }, [projectId]);
  async function save(segment: Seg) {
    setBusy(segment.id);
    try {
      await fetch(`/api/transcripts/${segment.transcriptId}/segments/${segment.id}`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text: segment.text }),
      });
    } finally {
      setBusy(null);
    }
  }
  return <div className="mt-8 rounded-3xl border border-white/10 p-6"><h2 className="text-lg font-semibold">Transcript</h2><div className="mt-4 max-h-[520px] space-y-3 overflow-auto">{rows.map((segment) => <div key={segment.id} className="rounded-xl bg-white/[.03] p-3"><div className="text-[10px] text-zinc-600">{Math.floor(segment.startS / 60).toString().padStart(2, "0")}:{Math.floor(segment.startS % 60).toString().padStart(2, "0")}</div><textarea value={segment.text} onChange={(event) => setRows((current) => current.map((row) => row.id === segment.id ? { ...row, text: event.target.value } : row))} onBlur={() => void save(segment)} className="mt-2 min-h-16 w-full resize-y rounded-lg bg-black/20 p-2 text-sm text-zinc-300 outline-none" />{busy === segment.id && <span className="text-[10px] text-zinc-600">Saving…</span>}</div>)}</div></div>;
}
