"use client";

import { useState } from "react";
import Link from "next/link";

const cats = ["AI Detect", "Reaction", "Funny", "Fail / Win", "Wholesome", "Drama", "Quotable", "Unexpected"];
type ApiResult = { id?: string; error?: string };
async function readResult(response: Response): Promise<ApiResult> {
  const type = response.headers.get("content-type") ?? "";
  if (!type.includes("application/json")) return { error: "The server returned an unexpected response. Check the server terminal." };
  try { return await response.json() as ApiResult; } catch { return { error: "The server returned an empty or invalid response." }; }
}

export default function NewProject() {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState("SHORTS");
  const [language, setLanguage] = useState("en");
  const [timeframe, setTimeframe] = useState("full");
  const [custom, setCustom] = useState("");
  const [selected, setSelected] = useState<string[]>(["AI Detect"]);
  const [rights, setRights] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError("");
    if (!url.trim() && !file) { setError("Add a supported source URL or choose a media file."); return; }
    if (url.trim() && file) { setError("Choose either a source URL or an upload, not both."); return; }
    if (!rights) { setError("Confirm that you have the rights to process this media."); return; }
    setBusy(true);
    try {
      const response = await fetch("/api/projects", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: name.trim(), sourceUrl: file ? undefined : (url.trim() || undefined), mode, outputLanguage: language, timeframe, customInstructions: custom, categories: selected, rightsConfirmed: rights }) });
      const data = await readResult(response);
      if (!response.ok || !data.id) { setError(data.error ?? "Project creation failed. Please try again."); return; }
      if (file) {
        const upload = await fetch("/api/projects/" + data.id + "/upload", { method: "POST", headers: { "content-type": file.type || "application/octet-stream", "x-file-name": encodeURIComponent(file.name) }, body: file });
        const uploaded = await readResult(upload);
        if (!upload.ok) { setError(uploaded.error ?? "The project was created, but the upload failed. You can reopen it and retry."); return; }
      }
      window.location.assign("/project/" + data.id);
    } catch {
      setError("Couldn't reach Clip Finder. Check the server terminal and your connection.");
    } finally { setBusy(false); }
  }

  return <main className="min-h-screen bg-[#080a0d] px-4 pb-16 text-white sm:px-6">
    <header className="mx-auto flex max-w-6xl items-center justify-between border-b border-white/[.07] py-5"><Link href="/dashboard" className="inline-flex items-center gap-2 text-sm text-zinc-400 transition hover:text-white"><span aria-hidden="true">←</span> Back to workspace</Link><Link href="/" className="font-semibold tracking-tight">clip<span className="text-[#c4f36b]">finder</span><span className="ml-1 text-[10px] text-zinc-600">2.0</span></Link></header>
    <div className="mx-auto grid max-w-6xl gap-8 pt-9 lg:grid-cols-[.72fr_1.28fr] lg:gap-12 lg:pt-14">
      <aside className="cf-enter lg:sticky lg:top-10 lg:self-start"><p className="cf-kicker">New project / 01</p><h1 className="mt-4 text-4xl font-semibold leading-[1.02] tracking-[-.055em] sm:text-5xl">Find the<br/><span className="text-[#c4f36b]">moments</span><br/>that matter.</h1><p className="mt-5 max-w-sm text-sm leading-6 text-zinc-400">Give your source some context. Clip Finder creates a project and hands it to the real ingestion and analysis workflow.</p>
        <div className="mt-8 space-y-4">{[{n:"01",title:"Add a source",body:"Use a supported video URL or upload a media file."},{n:"02",title:"Set the intent",body:"Choose format, language, and moments to look for."},{n:"03",title:"Review the results",body:"Open the workspace to inspect candidates and fine-tune clips."}].map(s=><div key={s.n} className="flex gap-3"><div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/[.025] font-mono text-[11px] text-[#c4f36b]">{s.n}</div><div><div className="text-sm font-medium">{s.title}</div><div className="mt-1 text-xs leading-5 text-zinc-600">{s.body}</div></div></div>)}</div>
        <div className="mt-8 rounded-2xl border border-amber-300/15 bg-amber-300/[.035] p-4"><div className="flex items-center gap-2 text-xs font-semibold text-amber-100"><span>ⓘ</span> Media rights matter</div><p className="mt-2 text-xs leading-5 text-zinc-500">Only process content you own or have permission to use. Source providers may restrict downloading or processing.</p></div>
      </aside>
      <form onSubmit={submit} className="cf-card cf-enter p-5 sm:p-8">
        <div className="flex items-start justify-between gap-4"><div><p className="cf-kicker">Project setup</p><h2 className="mt-2 text-xl font-semibold">Configure your source</h2><p className="mt-1 text-xs text-zinc-500">Fields marked required must be completed.</p></div><span className="rounded-lg border border-white/10 px-2.5 py-1.5 font-mono text-[10px] text-zinc-500">STEP 01 / 01</span></div>
        <div className="mt-7"><label className="cf-label" htmlFor="project-name">Project name</label><input className="cf-input" id="project-name" required value={name} onChange={e=>setName(e.target.value)} maxLength={100} placeholder="Friday stream highlights"/></div>
        <div className="mt-6"><div className="cf-label">Source media</div><label className="flex cursor-pointer flex-col items-center rounded-2xl border border-dashed border-white/[.16] bg-white/[.015] px-4 py-6 text-center transition hover:border-[#c4f36b]/35 hover:bg-[#c4f36b]/[.025]"><span className="grid h-11 w-11 place-items-center rounded-xl border border-white/10 bg-white/[.035] text-xl text-[#c4f36b]">↑</span><span className="mt-3 text-sm font-medium">{file ? file.name : "Choose a video or audio file"}</span><span className="mt-1 text-xs text-zinc-600">{file ? `${(file.size/1024/1024).toFixed(1)} MB · selected` : "Select a local file · supported video/audio types"}</span><input className="sr-only" type="file" accept="video/*,audio/*" onChange={e=>setFile(e.target.files?.[0]??null)}/></label><div className="my-4 flex items-center gap-3 text-[10px] uppercase tracking-[.18em] text-zinc-600"><span className="h-px flex-1 bg-white/[.07]"/>Or paste a link<span className="h-px flex-1 bg-white/[.07]"/></div><label className="cf-label" htmlFor="source-url">Supported source URL</label><input className="cf-input" id="source-url" type="url" value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://www.youtube.com/watch?v=…"/><p className="mt-2 text-[11px] text-zinc-600">YouTube, Twitch, Kick, or Google Drive links currently supported by the API.</p></div>
        <div className="mt-7 grid gap-5 sm:grid-cols-2"><fieldset><legend className="cf-label">Output format</legend><div className="grid grid-cols-2 gap-2">{[{v:"SHORTS",label:"Vertical shorts",sub:"9:16 clips"},{v:"LONG_FORM",label:"Long form",sub:"Wider edits"}].map(o=><button key={o.v} type="button" onClick={()=>setMode(o.v)} aria-pressed={mode===o.v} className={`rounded-xl border p-3 text-left transition ${mode===o.v?"border-[#c4f36b]/45 bg-[#c4f36b]/[.07]":"border-white/[.08] bg-white/[.015] hover:bg-white/[.04]"}`}><span className="block text-xs font-semibold">{o.label}</span><span className="mt-1 block text-[10px] text-zinc-600">{o.sub}</span></button>)}</div></fieldset><div><label className="cf-label" htmlFor="language">Transcript language</label><select id="language" className="cf-input" value={language} onChange={e=>setLanguage(e.target.value)}><option value="en">English</option><option value="hi">Hindi</option><option value="es">Spanish</option><option value="fr">French</option></select><label className="cf-label mt-4" htmlFor="timeframe">Source range</label><select id="timeframe" className="cf-input" value={timeframe} onChange={e=>setTimeframe(e.target.value)}><option value="full">Full source</option><option value="recent">Recent section</option></select></div></div>
        <fieldset className="mt-7"><legend className="cf-label">Moments to look for</legend><div className="flex flex-wrap gap-2">{cats.map(c=><button type="button" key={c} aria-pressed={selected.includes(c)} onClick={()=>setSelected(s=>s.includes(c)?s.filter(v=>v!==c):[...s,c])} className={`rounded-full border px-3 py-2 text-xs transition ${selected.includes(c)?"border-[#c4f36b]/40 bg-[#c4f36b]/[.07] text-[#d7f9a7]":"border-white/[.09] text-zinc-400 hover:border-white/20"}`}>{selected.includes(c)?"✓ ":"＋ "}{c}</button>)}</div><p className="mt-2 text-[11px] text-zinc-600">Choose any combination. AI Detect is selected by default.</p></fieldset>
        <div className="mt-7"><label className="cf-label" htmlFor="instructions">Extra direction <span className="font-normal text-zinc-600">(optional)</span></label><textarea className="cf-input min-h-[104px] resize-y" id="instructions" value={custom} onChange={e=>setCustom(e.target.value)} maxLength={2000} placeholder="Example: prioritize surprising stories, sharp reactions, and moments that make sense without extra context."/></div>
        <label className="mt-6 flex cursor-pointer items-start gap-3 rounded-xl border border-white/[.07] bg-white/[.015] p-3.5"><input type="checkbox" checked={rights} onChange={e=>setRights(e.target.checked)} className="mt-1 accent-[#c4f36b]"/><span className="text-xs leading-5 text-zinc-400">I confirm I own this media or have the necessary rights or permission to process it.</span></label>
        {error && <p role="alert" aria-live="polite" className="mt-5 rounded-xl border border-red-400/20 bg-red-400/[.08] p-3 text-sm text-red-300">{error}</p>}
        <div className="mt-7 flex flex-col-reverse gap-3 border-t border-white/[.07] pt-5 sm:flex-row sm:items-center sm:justify-between"><p className="text-[11px] text-zinc-600">Your source is processed by the configured backend.</p><button disabled={busy} className="cf-button !min-h-12">{busy?"Creating project…":"Create & analyze source"} <span aria-hidden="true">↗</span></button></div>
      </form>
    </div>
  </main>;
}
