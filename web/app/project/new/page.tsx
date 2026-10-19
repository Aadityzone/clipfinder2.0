"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AnalysisRangeSelector, { type RangeMetadata } from "./AnalysisRangeSelector";

const categories = ["AI Detect", "Reaction", "Funny", "Fail / Win", "Wholesome", "Drama", "Quotable", "Unexpected"];
const formatDuration = (seconds: number) => [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, Math.floor(seconds) % 60].map((part) => String(part).padStart(2, "0")).join(":");
const genres = [
  ["auto", "Auto-detect"], ["general", "General"], ["gaming", "Gaming"], ["irl_stream", "IRL streams"],
  ["movies_tv", "Movies & TV"], ["anime", "Anime & manga"], ["tech", "Tech"], ["knowledge", "Education"],
  ["facts", "Facts"], ["podcast", "Podcasts"],
];
type ApiResult = { id?: string; error?: string };

async function readResult(response: Response): Promise<ApiResult & Record<string, unknown>> {
  if (!response.headers.get("content-type")?.includes("application/json")) return { error: "The server returned an unexpected response." };
  try { return await response.json() as ApiResult & Record<string, unknown>; }
  catch { return { error: "The server returned an empty or invalid response." }; }
}

export default function NewProject({ searchParams }: { searchParams: Promise<{ sourceUrl?: string }> }) {
  const router = useRouter();
  const { sourceUrl } = use(searchParams);
  const [name, setName] = useState("");
  const [url, setUrl] = useState(sourceUrl ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState("SHORTS");
  const [genre, setGenre] = useState("auto");
  const [language, setLanguage] = useState("en");
  const [custom, setCustom] = useState("");
  const [selected, setSelected] = useState<string[]>(["AI Detect"]);
  const [rights, setRights] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [metadata, setMetadata] = useState<RangeMetadata | null>(null);
  const [metadataBusy, setMetadataBusy] = useState(false);
  const [metadataError, setMetadataError] = useState("");
  const [selectedRange, setSelectedRange] = useState({ startSeconds: 0, endSeconds: 3600 });

  async function lookupMetadata() {
    if (!url.trim() || metadataBusy) return;
    setMetadataBusy(true);
    setMetadataError("");
    setMetadata(null);
    try {
      const response = await fetch("/api/sources/metadata", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ sourceUrl: url.trim() }) });
      const data = await readResult(response);
      if (!response.ok || !data.duration || !data.entitlement) throw new Error(data.error ?? "Could not retrieve source details.");
      setMetadata(data as unknown as RangeMetadata);
      setSelectedRange({ startSeconds: 0, endSeconds: Math.min(Number(data.duration), Number((data.entitlement as RangeMetadata["entitlement"]).maxDurationMs) / 1000) });
    } catch (cause) {
      setMetadataError(cause instanceof Error ? cause.message : "Could not retrieve source details.");
    } finally { setMetadataBusy(false); }
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError("");
    if (!url.trim() && !file) { setError("Add a supported source URL or choose a media file."); return; }
    if (url.trim() && file) { setError("Choose either a source URL or an upload, not both."); return; }
    if (url.trim() && !metadata) { setError("Load video details and confirm an analysis range before starting."); return; }
    if (!rights) { setError("Confirm that you have the rights to process this media."); return; }
    setBusy(true);
    try {
      const response = await fetch("/api/projects", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({
          name: name.trim(), sourceUrl: file ? undefined : (url.trim() || undefined), mode, genre,
          outputLanguage: language,
          ...(metadata ? { sourceStartSeconds: selectedRange.startSeconds, sourceEndSeconds: selectedRange.endSeconds, rangeConfirmed: true } : {}),
          customInstructions: custom, categories: selected, rightsConfirmed: rights,
        }),
      });
      const data = await readResult(response);
      if (!response.ok || !data.id) { setError(data.error ?? "Project creation failed. Please try again."); return; }
      if (file) {
        const upload = await fetch(`/api/projects/${data.id}/upload`, {
          method: "POST",
          headers: { "content-type": file.type || "application/octet-stream", "x-file-name": encodeURIComponent(file.name) },
          body: file,
        });
        const uploaded = await readResult(upload);
        if (!upload.ok) { setError(uploaded.error ?? "The project was created, but the upload failed. Reopen it and retry."); return; }
      }
      router.push(`/project/${data.id}`);
    } catch {
      setError("Could not reach Clip Finder. Check the server and your connection.");
    } finally { setBusy(false); }
  }

  return <main className="min-h-screen bg-[#080a08] px-4 pb-16 text-white sm:px-6">
    <header className="mx-auto flex max-w-6xl items-center justify-between border-b border-white/[.07] py-5">
      <Link href="/dashboard" className="text-sm text-zinc-400 transition hover:text-white">← Back to workspace</Link>
      <Link href="/" className="font-semibold tracking-tight">clip<span className="text-[#39ff14]">finder</span><span className="ml-1 text-[10px] text-zinc-600">2.0</span></Link>
    </header>
    <div className="mx-auto grid max-w-6xl gap-8 pt-9 lg:grid-cols-[.72fr_1.28fr] lg:gap-12 lg:pt-14">
      <aside className="lg:sticky lg:top-10 lg:self-start"><p className="cf-kicker">New project / 01</p><h1 className="mt-4 text-4xl font-semibold leading-[1.02] tracking-[-.055em] sm:text-5xl">Find the<br/><span className="text-[#39ff14]">moments</span><br/>that matter.</h1>
        <p className="mt-5 max-w-sm text-sm leading-6 text-zinc-400">Inspect the source first, choose the section that matters, then start the analysis.</p>
        <div className="mt-8 space-y-4">{[["01", "Add a source", "Paste a supported URL or choose a local media file."], ["02", "Choose a range", "Review the source duration and select the time window."], ["03", "Start analysis", "Only a confirmed range creates the processing job."]].map(([n, title, body]) => <div key={n} className="flex gap-3"><div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/[.025] font-mono text-[11px] text-[#39ff14]">{n}</div><div><div className="text-sm font-medium">{title}</div><div className="mt-1 text-xs leading-5 text-zinc-600">{body}</div></div></div>)}</div>
        <div className="mt-8 rounded-2xl border border-amber-300/15 bg-amber-300/[.035] p-4"><div className="text-xs font-semibold text-amber-100">Media rights matter</div><p className="mt-2 text-xs leading-5 text-zinc-500">Only process content you own or have permission to use.</p></div>
      </aside>
      <form onSubmit={submit} className="cf-card p-5 sm:p-8">
        <p className="cf-kicker">Project setup</p><h2 className="mt-2 text-xl font-semibold">Configure your source</h2>
        <div className="mt-6"><label className="cf-label" htmlFor="project-name">Project name</label><input className="cf-input" id="project-name" required value={name} onChange={(e) => setName(e.target.value)} maxLength={100} placeholder="Friday stream highlights"/></div>
        <div className="mt-6"><div className="cf-label">Source media</div>
          <label className="flex cursor-pointer flex-col items-center rounded-2xl border border-dashed border-white/[.16] bg-white/[.015] px-4 py-6 text-center transition hover:border-[#39ff14]/35"><span className="text-sm font-medium">{file ? file.name : "Choose a video or audio file"}</span><span className="mt-1 text-xs text-zinc-600">{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB · selected` : "Select local media"}</span><input className="sr-only" type="file" accept="video/*,audio/*" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setMetadata(null); }}/></label>
          <div className="my-4 flex items-center gap-3 text-[10px] uppercase tracking-[.18em] text-zinc-600"><span className="h-px flex-1 bg-white/[.07]"/>Or paste a link<span className="h-px flex-1 bg-white/[.07]"/></div>
          <label className="cf-label" htmlFor="source-url">Supported source URL</label><input className="cf-input" id="source-url" type="url" value={url} onChange={(e) => { setUrl(e.target.value); setMetadata(null); setMetadataError(""); }} placeholder="https://www.youtube.com/watch?v=…"/>
          <p className="mt-2 text-[11px] text-zinc-600">YouTube, Twitch, Kick, or connected Google Drive.</p>
          {url.trim() && !file && <button type="button" onClick={lookupMetadata} disabled={metadataBusy} className="cf-button-secondary mt-3">{metadataBusy ? "Fetching metadata…" : metadata ? "Refresh video details" : "Load video details"}</button>}
          {metadataError && <div role="alert" className="mt-3 rounded-xl border border-red-400/20 bg-red-400/[.06] p-3 text-xs text-red-300">{metadataError} <button type="button" onClick={lookupMetadata} className="ml-2 underline">Retry</button></div>}
          {metadata && <div className="mt-4 flex gap-3 rounded-xl border border-white/[.08] bg-white/[.025] p-3">{metadata.thumbnail && <img src={metadata.thumbnail} alt="" referrerPolicy="no-referrer" className="h-16 w-28 rounded-lg object-cover"/>}<div className="min-w-0"><div className="truncate text-sm font-medium">{metadata.title || "Untitled video"}</div><div className="mt-1 text-xs text-zinc-500">{metadata.platform} · {formatDuration(metadata.duration)}</div><div className="mt-1 text-[10px] text-emerald-300">Metadata only · no job has started</div></div></div>}
        </div>
        {metadata && <AnalysisRangeSelector key={`${metadata.title ?? "source"}:${metadata.duration}`} metadata={metadata} value={selectedRange} onChange={setSelectedRange}/>}
        <div className="mt-7 grid gap-5 sm:grid-cols-2"><fieldset><legend className="cf-label">Output format</legend><div className="grid grid-cols-2 gap-2">{[["SHORTS", "Vertical shorts", "9:16 clips"], ["LONG_FORM", "Long form", "Wider edits"]].map(([value, title, description]) => <button key={value} type="button" onClick={() => setMode(value)} aria-pressed={mode === value} className={`rounded-xl border p-3 text-left ${mode === value ? "border-[#39ff14]/45 bg-[#39ff14]/[.07]" : "border-white/[.08] bg-white/[.015]"}`}><span className="block text-xs font-semibold">{title}</span><span className="mt-1 block text-[10px] text-zinc-600">{description}</span></button>)}</div></fieldset>
          <div><label className="cf-label" htmlFor="language">Transcript language</label><select id="language" className="cf-input" value={language} onChange={(e) => setLanguage(e.target.value)}><option value="en">English</option><option value="hi">Hindi</option><option value="es">Spanish</option><option value="fr">French</option></select></div></div>
        <div className="mt-7"><label className="cf-label" htmlFor="genre">Content genre</label><select id="genre" className="cf-input" value={genre} onChange={(e) => setGenre(e.target.value)}>{genres.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
        <fieldset className="mt-7"><legend className="cf-label">Moments to look for</legend><div className="flex flex-wrap gap-2">{categories.map((category) => <button type="button" key={category} aria-pressed={selected.includes(category)} onClick={() => setSelected((current) => current.includes(category) ? current.filter((value) => value !== category) : [...current, category])} className={`rounded-full border px-3 py-2 text-xs ${selected.includes(category) ? "border-[#39ff14]/40 bg-[#39ff14]/[.07] text-[#b2ff9b]" : "border-white/[.09] text-zinc-400"}`}>{category}</button>)}</div></fieldset>
        <div className="mt-7"><label className="cf-label" htmlFor="instructions">Extra direction <span className="font-normal text-zinc-600">(optional)</span></label><textarea className="cf-input min-h-[104px] resize-y" id="instructions" value={custom} onChange={(e) => setCustom(e.target.value)} maxLength={2000} placeholder="Prioritize surprising stories, sharp reactions, and moments that make sense without extra context."/></div>
        <label className="mt-6 flex cursor-pointer items-start gap-3 rounded-xl border border-white/[.07] bg-white/[.015] p-3.5"><input type="checkbox" checked={rights} onChange={(e) => setRights(e.target.checked)} className="mt-1 accent-[#39ff14]"/><span className="text-xs leading-5 text-zinc-400">I confirm I own this media or have permission to process it.</span></label>
        {error && <p role="alert" aria-live="polite" className="mt-5 rounded-xl border border-red-400/20 bg-red-400/[.08] p-3 text-sm text-red-300">{error}</p>}
        <div className="mt-7 flex flex-col-reverse gap-3 border-t border-white/[.07] pt-5 sm:flex-row sm:items-center sm:justify-between"><p className="text-[11px] text-zinc-600">The selected range is checked again by the server before a job is created.</p><button disabled={busy || metadataBusy || (!!url.trim() && (!metadata || metadata.entitlement.maxDurationMs <= 0))} className="cf-button !min-h-12">{busy ? "Creating project…" : "Confirm range & analyze"} <span aria-hidden="true">↗</span></button></div>
      </form>
    </div>
  </main>;
}
