"use client";
import { useState } from "react";
import Link from "next/link";

const categories = ["AI Detect", "Reaction", "Funny", "Fail / Win", "Wholesome", "Drama", "Quotable", "Unexpected"];
type ApiResponse = { id?: string; error?: string };
async function readResponse(response: Response): Promise<ApiResponse> {
  const type = response.headers.get("content-type") ?? "";
  if (!type.includes("application/json")) throw new Error("The server returned an unexpected response. Check the terminal for the API error.");
  try { return await response.json() as ApiResponse; }
  catch { throw new Error("The server returned an empty or invalid response. Please try again."); }
}

export default function NewProject() {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState("SHORTS");
  const [language, setLanguage] = useState("en");
  const [timeframe, setTimeframe] = useState("full");
  const [instructions, setInstructions] = useState("");
  const [selected, setSelected] = useState<string[]>(["AI Detect"]);
  const [rights, setRights] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError("");
    if (!url.trim() && !file) { setError("Add a supported source URL or choose a media file."); return; }
    if (url.trim() && file) { setError("Choose either a URL or a file, not both."); return; }
    if (!rights) { setError("Confirm that you have the rights or permission to process this media."); return; }
    if (!name.trim()) { setError("Give your project a name."); return; }
    setBusy(true);
    try {
      const response = await fetch("/api/projects", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: name.trim(), sourceUrl: file ? undefined : (url.trim() || undefined), mode, outputLanguage: language, timeframe, customInstructions: instructions, categories: selected, rightsConfirmed: rights }),
      });
      const project = await readResponse(response);
      if (!response.ok) throw new Error(project.error ?? "Couldn't create the project.");
      if (!project.id) throw new Error("The server created no project ID. Check the API logs before retrying.");
      if (file) {
        const upload = await fetch("/api/projects/" + project.id + "/upload", {
          method: "POST",
          headers: { "content-type": file.type || "application/octet-stream", "x-file-name": encodeURIComponent(file.name) },
          body: file,
        });
        const result = await readResponse(upload);
        if (!upload.ok) throw new Error(result.error ?? "Project created, but the media upload failed. Open the project and retry with a supported file.");
      }
      window.location.assign("/project/" + project.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Something went wrong. Please try again.");
      setBusy(false);
    }
  }

  return <main className="relative min-h-screen overflow-hidden">
    <div className="pointer-events-none absolute inset-0 cf-grid opacity-40" />
    <header className="relative mx-auto flex max-w-[1120px] items-center justify-between px-5 py-5 sm:px-8"><Link href="/dashboard" className="flex items-center gap-2 text-xs text-[#9ca6b4] hover:text-white"><span className="text-[#c4f56b]">←</span> Back to workspace</Link><span className="text-[10px] text-[#687383]">NEW PROJECT · 01 / 01</span></header>
    <div className="relative mx-auto grid max-w-[1120px] gap-8 px-5 pb-16 pt-5 sm:px-8 lg:grid-cols-[.7fr_1.3fr] lg:gap-14 lg:pt-12">
      <section className="lg:sticky lg:top-10 lg:self-start"><p className="cf-eyebrow">Set up your analysis</p><h1 className="mt-4 text-4xl font-semibold leading-[1.02] tracking-[-.065em] sm:text-5xl">Let&apos;s find the <span className="text-[#c4f56b]">good parts.</span></h1><p className="mt-5 text-sm leading-7 text-[#8792a1]">Give your source a name, tell Clip Finder what matters, and send it through the real analysis pipeline.</p>
        <div className="mt-8 space-y-3">{[{n:"01",t:"Add your source",d:"Supported URL or local media file."},{n:"02",t:"Set the intent",d:"Choose format, language, and moments."},{n:"03",t:"Review real results",d:"Candidates appear after processing succeeds."}].map(x=><div key={x.n} className="flex gap-3 rounded-xl border border-white/[.07] bg-white/[.02] p-3"><span className="font-mono text-[10px] text-[#c4f56b]">{x.n}</span><div><p className="text-xs font-semibold">{x.t}</p><p className="mt-1 text-[10px] leading-5 text-[#687383]">{x.d}</p></div></div>)}</div>
        <p className="mt-6 text-[10px] leading-5 text-[#687383]">Only submit content you own or have permission to process. Large uploads may require configured storage and media tools.</p>
      </section>
      <form onSubmit={submit} className="cf-panel cf-rise rounded-3xl p-5 sm:p-8">
        <div className="flex items-center justify-between gap-3 border-b border-white/[.07] pb-5"><div><h2 className="text-lg font-semibold">Project details</h2><p className="mt-1 text-[11px] text-[#687383]">You can refine clips after analysis.</p></div><span className="rounded-full border border-white/[.08] px-3 py-1 text-[9px] text-[#8792a1]">CONFIGURATION</span></div>
        <div className="mt-6"><label className="cf-label" htmlFor="project-name">Project name</label><input id="project-name" required maxLength={120} value={name} onChange={e=>setName(e.target.value)} placeholder="Friday night stream highlights" className="cf-input" /></div>
        <div className="mt-6"><p className="cf-label">Source media</p><div className="grid gap-3 sm:grid-cols-2">
          <label className={`cursor-pointer rounded-2xl border p-4 transition ${file ? "border-[#c4f56b]/50 bg-[#c4f56b]/[.05]" : "border-white/[.09] bg-black/10 hover:border-white/20"}`}><span className="text-sm font-semibold">↑ Upload a file</span><p className="mt-1 text-[10px] leading-5 text-[#687383]">Video or audio from your device</p><input type="file" accept="video/*,audio/*" onChange={e=>{setFile(e.target.files?.[0]??null);if(e.target.files?.[0])setUrl("");}} className="mt-4 block w-full text-[10px] text-[#8792a1] file:mr-2 file:rounded-lg file:border-0 file:bg-white/10 file:px-3 file:py-2 file:text-[10px] file:text-white" /></label>
          <div className={`rounded-2xl border p-4 ${url ? "border-[#c4f56b]/50 bg-[#c4f56b]/[.05]" : "border-white/[.09] bg-black/10"}`}><label className="text-sm font-semibold" htmlFor="source-url">↗ Paste a source URL</label><p className="mt-1 text-[10px] leading-5 text-[#687383]">YouTube, Twitch, Kick, Google Drive</p><input id="source-url" type="url" value={url} onChange={e=>{setUrl(e.target.value);if(e.target.value)setFile(null);}} placeholder="https://…" className="cf-input mt-4 text-xs" /></div>
        </div>{file && <p className="mt-3 truncate text-[10px] text-[#c4f56b]">Selected: {file.name} · {(file.size / (1024*1024)).toFixed(1)} MB</p>}</div>
        <div className="mt-6 grid gap-4 sm:grid-cols-3"><div><label className="cf-label">Output mode</label><div className="grid grid-cols-2 gap-2">{["SHORTS","LONG_FORM"].map(x=><button type="button" key={x} onClick={()=>setMode(x)} aria-pressed={mode===x} className={`min-h-11 rounded-xl border px-2 text-[10px] font-semibold transition ${mode===x?"border-[#c4f56b]/40 bg-[#c4f56b]/[.08] text-[#c4f56b]":"border-white/[.08] text-[#8792a1] hover:bg-white/[.04]"}`}>{x==="SHORTS"?"Shorts":"Long form"}</button>)}</div></div>
          <div><label className="cf-label" htmlFor="language">Output language</label><select id="language" value={language} onChange={e=>setLanguage(e.target.value)} className="cf-input text-xs"><option value="en">English</option><option value="hi">Hindi</option><option value="es">Spanish</option><option value="fr">French</option></select></div>
          <div><label className="cf-label" htmlFor="timeframe">Timeframe</label><select id="timeframe" value={timeframe} onChange={e=>setTimeframe(e.target.value)} className="cf-input text-xs"><option value="full">Full source</option><option value="recent">Recent section</option></select></div>
        </div>
        <fieldset className="mt-7"><legend className="cf-label">What moments matter?</legend><div className="flex flex-wrap gap-2">{categories.map(category=><button type="button" key={category} aria-pressed={selected.includes(category)} onClick={()=>setSelected(old=>old.includes(category)?old.filter(x=>x!==category):old.length<8?[...old,category]:old)} className={`rounded-full border px-3 py-2 text-[10px] transition ${selected.includes(category)?"border-[#c4f56b]/35 bg-[#c4f56b]/[.08] text-[#c4f56b]":"border-white/[.09] text-[#8792a1] hover:border-white/20"}`}>{selected.includes(category)?"✓ ":""}{category}</button>)}</div><p className="mt-2 text-[10px] text-[#687383]">Choose up to eight categories. Your selection is passed into analysis.</p></fieldset>
        <div className="mt-7"><label className="cf-label" htmlFor="instructions">Custom instructions <span className="font-normal text-[#687383]">(optional)</span></label><textarea id="instructions" maxLength={2000} rows={4} value={instructions} onChange={e=>setInstructions(e.target.value)} placeholder="Look for surprising reactions, clear punchlines, or moments where the conversation changes direction…" className="cf-input resize-y leading-6" /><p className="mt-1 text-right text-[9px] text-[#687383]">{instructions.length}/2000</p></div>
        <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-xl border border-white/[.07] bg-black/10 p-3 text-[11px] leading-5 text-[#9ca6b4]"><input type="checkbox" checked={rights} onChange={e=>setRights(e.target.checked)} className="mt-1 accent-[#c4f56b]" /><span>I confirm I own this media or have permission to process it.</span></label>
        {error && <p role="alert" aria-live="polite" className="mt-4 rounded-xl border border-rose-400/20 bg-rose-400/[.07] p-3 text-xs leading-5 text-rose-300">{error}</p>}
        <button disabled={busy} className="cf-button cf-button-primary mt-6 w-full disabled:cursor-not-allowed disabled:opacity-60">{busy?"Creating project…":"Create project & analyze"} <span aria-hidden="true">↗</span></button>
        <p className="mt-3 text-center text-[9px] leading-5 text-[#687383]">Processing depends on source access, configured media tools, and available workers.</p>
      </form>
    </div>
  </main>;
}
