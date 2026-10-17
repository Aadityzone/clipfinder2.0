# AI Engineering Handoff — Clip Finder 2.0

Last updated: 2026-10-17
Repository: https://github.com/Aadityzone/clipfinder2.0
Working branch: `fix/real-video-acceptance`
Branch HEAD when this handoff was written: `4f310f2917878d55abce0de616e5ca398e8f1d6c`
Related PR: https://github.com/Aadityzone/clipfinder2.0/pull/19

This is the working handoff for another coding agent. Read this file and the linked project docs before changing the AI pipeline. Update this handoff when meaningful code or validation status changes.

## Product goal

Clip Finder accepts real long-form video sources (including supported YouTube/Twitch/Kick URLs), analyzes actual media, produces ranked candidate clips, lets the creator edit them, and renders playable short-form exports. Never fake AI results, progress, scores, renders, publishing, or benchmark numbers.

## Architecture

- `web/`: Next.js app, API routes, worker and editor.
- `ai/`: Python FastAPI media/AI service. The web app must call this service over HTTP; do not run models directly in browser code.
- `prisma/`: persistence schema.
- Main AI endpoint is in `ai/main.py`; inspect its current implementation before changing pipeline order or request/response contracts.

## AI pipeline already present in code

1. Media probing / audio and video handling, with FFmpeg/FFprobe and source ingestion paths.
2. Whisper transcription integration with timestamped transcript segments and optional word timestamps.
3. Transcript-centered candidate window generation and cue/category filtering in `ai/highlights.py`.
4. Media intelligence in `ai/services/media_intelligence.py`: audio energy/peaks/silence, scene changes, optional face sampling and visual features.
5. Bounded multimodal event proposals in `ai/services/visual_candidates.py`. These are evidence-based proposals from timestamped audio/visual/on-screen signals, not a trained semantic detector of specific events.
6. Story boundary and hook/tension/payoff signals in `ai/services/story_intelligence.py`.
7. Candidate contract validation in `ai/services/candidate_contract.py`.
8. Semantic enrichment / optional LLM scoring in the AI services; deterministic scores should remain useful when optional model credentials/providers are unavailable.
9. Deduplication in `ai/services/dedup.py`.
10. Genre heuristics and creator-specific preference adjustments in `ai/services/genre_intelligence.py` and `ai/services/creator_feedback.py`.
11. Candidate ranking/validation and response through the FastAPI service.
12. Web worker integrates source ranges and chunking logic; inspect current worker path before changing range semantics.

## Evaluation and smoke tooling

- `ai/services/evaluation.py`: interval IoU and ranked-candidate precision@K, recall@K, F1@K, mean matched IoU, plus aggregate/macro metrics.
- `ai/scripts/evaluate_highlights.py`: CLI for comparing predictions with human-labelled timestamp ranges; supports genre-level reporting.
- `ai/scripts/smoke_pipeline.py`: real-source/local-media smoke pipeline; intended to exercise media download/probe, transcription, analysis, render and report artifact creation.
- `.github/workflows/ai-real-video-smoke.yml`: manual real-video smoke workflow and artifact upload.
- `docs/GENRE_FOUNDATION.md`: shared pipeline, per-genre gaps and quality gates.
- `docs/PHASE_1_REAL_VIDEO_TEST.md`: local end-to-end acceptance checklist and required services.
- `docs/ROADMAP.md`: broader product implementation inventory and remaining gaps.
- `docs/ENVIRONMENT.md`: environment configuration guidance.

## Recent AI commits on this branch

- `26a8cdf` — guard candidate validation and dedup against malformed inputs; CI passed.
- `5ff2b35` — normalize whitespace in story cue matching. This run was cancelled by a subsequent push; later story changes were tested.
- `b85189c` — harden story boundary optimization and phrase matching; superseded by follow-up story hardening.
- `be9bc66` — handle invalid story text and duration values; CI passed.
- `bb9bc75` — isolate creator preference scoring from malformed inputs and avoid mutating original candidate/feature dictionaries; CI passed.

Always check current GitHub HEAD and Actions before relying on this list. The branch can move after this document is written.

## Known limitations — do not overclaim

- The genre profiles are explainable heuristics, not trained genre-specific classifiers.
- Visual/audio event proposals are not proof that the system understands a clutch, fight, reveal, joke, or emotional context.
- No representative human-labelled benchmark results have been established. Do not invent accuracy/precision numbers.
- The full real-video path from a public source through persisted candidates and a playable export has not yet been confirmed end-to-end in the available handoff.
- Provider-dependent features require real credentials/configuration. Never request or commit secrets.
- Transcript RAG (added on the active feature branch) is request-local and uses the existing sentence-transformers dependency with CPU inference and local-cache-only model loading. It does not persist transcript embeddings or require a vector database. If the model is not installed in the local Hugging Face cache, it reports unavailable and leaves deterministic ranking intact. RAG has not been evaluated against human-labeled clip relevance data.
- Passing unit tests or a Next.js build does not prove real-media acceptance.

## Current next priorities

1. Check latest branch head and CI. If the latest run failed, inspect logs and fix it before piling on new work.
2. Run the manual `ai-real-video-smoke` workflow on a rights-authorized, accessible public source or local fixture. Inspect its report artifact; record the exact stage and error if it fails.
3. Improve stage-specific diagnostics in `ai/scripts/smoke_pipeline.py` so reports identify the actual failed stage (download, probe, transcription, analysis, render) rather than a broad generic failure.
4. Verify real media outputs and timestamp invariants: finite start/end, start < end, within source duration, sensible deduplication, rendered MP4 plays.
5. Build a small human-labelled benchmark from representative videos across genres. Keep evaluation videos separate from any videos used to tune weights.
6. Use measured errors to improve ranking. Prioritize measured clip quality over adding arbitrary heuristic weights.
7. Keep tests for each change and update this handoff when status changes.

## Working rules for the next agent

- Work on `build/universal-genre-foundation` / PR #19 unless the owner explicitly requests otherwise. Do not push to `main`.
- Fetch the latest branch HEAD before creating commits; use the actual latest SHA as the parent and update the ref with an expected-SHA guard.
- Inspect existing implementations/tests first. Keep changes small, cohesive and testable.
- Run relevant Python tests locally if the environment is available, plus CI. Never report tests as passed unless the run confirms it.
- Do not rewrite architecture or public API contracts without checking callers in `web/`, `ai/main.py`, and tests.
- Do not ask the owner to paste secrets. Use environment variable names/placeholders only.
- At the end of work, report commit(s), changed files, tests/CI status, unresolved risks and next concrete task.

## Quick start for an agent

1. Read this file, `docs/GENRE_FOUNDATION.md`, `docs/PHASE_1_REAL_VIDEO_TEST.md`, and `docs/ROADMAP.md`.
2. Fetch current branch HEAD and recent GitHub Actions runs.
3. Inspect `ai/scripts/smoke_pipeline.py` and its tests; improve stage-level diagnostics and test report output.
4. Run relevant tests and check CI.
5. Update this document with verified results, not assumptions.

## Latest local audit and smoke-runner change (2026-10-16)

- Audited the shared pipeline and web worker on `build/universal-genre-foundation` at `f263ebf`. The working tree also contained pre-existing user changes in `web/next-env.d.ts`, `web/tsconfig.json`, and an untracked `package-lock.json`; these were left untouched.
- Updated `ai/scripts/smoke_pipeline.py` to report stable failure stages for source validation, media probing, transcription, analysis, and rendering. The runner now probes each rendered file with FFprobe and rejects output without positive duration and video dimensions.
- Added regression cases in `ai/tests/test_smoke_pipeline.py` for URL analysis-stage attribution and unprobeable rendered output.
- Verification: `python -m pytest -q -p no:cacheprovider ai/tests/test_smoke_pipeline.py` — 6 passed. The run required an installed `opencv-python-headless` dependency and execution outside the sandbox because its temporary-directory fixture was denied inside the sandbox.
- No real-media smoke run was performed: no local video fixture was found, and a rights-authorized source URL was not provided. The workflow is manual (`workflow_dispatch`); the named workflow was not available through the workflow-specific Actions query on the current default branch. The latest general branch CI run observed before this local change was green for `f263ebf` (run `38901133353`); it does not verify these uncommitted changes.
- The current source confirms the limits described above: candidate and genre decisions remain mostly transcript/media-signal heuristics; visual action is sampled and shallow; no human-labelled benchmark set or measured quality results were found. Web worker/database persistence, chunked jobs, editing and rendering code exist, but their combined real-media path remains unverified.

## Follow-up verification (2026-10-16)

- Complete local AI suite: `python -m pytest -q -p no:cacheprovider ai/tests` — **160 passed**, one `StarletteDeprecationWarning`, 1.76 seconds. The command required execution outside the sandbox because pytest's temporary-directory fixture was denied inside it.
- GitHub Actions for `ae2cb084c010316e12f46e98f6bd884deafe0b0d` (run `38903972293`): Python job passed, including dependency installation, `py_compile`, and `PYTHONPATH=. pytest -q`; web job failed at `npm run build` because `lightningcss` could not load `lightningcss.linux-x64-gnu.node`. This is a web dependency/build failure, not an AI test failure. Overall run conclusion: failure.
- Workflow inputs and outputs: `.github/workflows/ai-real-video-smoke.yml` is manual (`workflow_dispatch`). It requires `source_url`, genre, and top count (choices 1/2/3/5/10); language is optional. It runs Ubuntu with Python 3.12, FFmpeg/FFprobe, `ai/requirements-ci.txt`, and Faster Whisper small/CPU/int8, with a 120-minute timeout. It uploads `artifacts/ai-smoke/` as `clipfinder-real-video-smoke` for 7 days, including `transcript.json`, `report.json`, and any rendered clips.
- No local video fixture was found in the repository file inventory, and no rights-authorized public URL was provided. Therefore no real-media run was attempted. Real output playability and timestamps from actual model-generated candidates remain unverified. The smoke runner rejects invalid/empty candidate intervals by skipping intervals where clipped end is not after start, and probes rendered outputs; regression tests cover these guards only with mocks.
- To run the real-media integration path, provide one rights-authorized source video, either a supported public URL or a local video file.

## Transcript retrieval augmentation

- `ai/services/transcript_rag.py` creates overlapping word-window transcript chunks with source timestamps and retrieves request-local semantic context for up to 20 candidates. The request boundary is the privacy boundary: only the segments already supplied to one authorized analysis call are considered, so there is no cross-user/project shared index.
- RAG is controlled with `RAG_ENABLED` (defaults to enabled). `RAG_ENABLED=false` disables retrieval. `RAG_EMBEDDING_MODEL` selects the sentence-transformers model; it must already be cached locally. Loading is CPU-only and `local_files_only`; missing dependencies/cache, malformed embeddings, or retrieval errors are diagnostics and do not fail analysis.
- Chunk defaults are 110 words with 20 words of overlap (`RAG_CHUNK_WORDS`, `RAG_CHUNK_OVERLAP_WORDS`). Embeddings are batched by 32 (`RAG_EMBEDDING_BATCH_SIZE`) and normalized, with a process-local LRU capped at 4,096 vectors and an estimated 32 MiB. Retrieval returns at most three chunks (`RAG_RETRIEVAL_LIMIT`) and 600 characters (`RAG_CONTEXT_MAX_CHARS`) per candidate; candidate retrieval is capped at 20 per analysis. The optional existing LLM scorer receives those chunks as transcript evidence in its existing call. RAG adds no LLM calls and does not change deterministic candidate scores.
- Candidate and retrieved context timestamps are in source-media coordinates. Bounded analysis already clips the supplied transcript to the selected range; the range wrapper shifts retrieved context timestamps back to source coordinates.
- Unit tests use deterministic test-only embeddings. There is no human-labeled RAG quality benchmark or real-video RAG integration result yet, and RAG cannot establish visual evidence from transcripts.
- Repeatable technical harness: `python ai/scripts/benchmark_transcript_rag.py --test-embeddings` reports candidate/context counts, latency, extra LLM calls, and baseline versus no-LLM ranking. It is synthetic and does not measure clip quality. Omit the flag to exercise an already-cached local model.
- Focused test command: `python -m pytest -q -p no:cacheprovider ai/tests/test_transcript_rag.py ai/tests/test_llm_scoring.py`.

## Core boundary correctness fix (2026-10-16)

- On the shared worktree (`feature/premium-black-green-ui`, HEAD `2c71410`), reviewing `ai/services/story_intelligence.py` exposed a setup-window loop bug: with continuous four-second transcript rows and an anchor at 100 seconds, `find_boundaries` returned `(0, 75)`, dropping the event anchor.
- The left-context loop now measures each prior segment against the fixed anchor timestamp. Sentence-boundary snapping also falls back to the already bounded interval if snapping would exceed the configured maximum duration.
- Regression coverage in `ai/tests/test_story_intelligence.py` checks anchor inclusion on a long continuous transcript and verifies punctuation snapping respects the 75-second cap.
- Verification on the complete shared worktree, including the visible RAG and time-range changes: `python -m pytest -q -p no:cacheprovider ai/tests` — **181 passed**, one `StarletteDeprecationWarning`, 1.33 seconds. Pytest was run outside the sandbox because its temporary-directory fixture is blocked inside it.
- No real media was processed. The boundary change is verified against deterministic transcript fixtures; real-video candidate quality remains unmeasured.

## Real AI API acceptance and optional face-signal fallback (2026-10-17)

- Source: official Blender Foundation upload, [Sintel - Open Movie](https://www.youtube.com/watch?v=eRsGyueVLvQ). The AI API returned metadata for the 888-second video. The test downloaded only the selected 90-second interval `[90, 180]` through `/v1/ingest`; FFprobe reported H.264, 2048×872, audio present, and the response retained `sourceDuration=888`, `sourceStartS=90`, `sourceEndS=180`.
- Started the FastAPI service with `WHISPER_MODEL=tiny`, `WHISPER_DEVICE=cpu`, and `WHISPER_COMPUTE_TYPE=int8`, then called `/v1/transcribe`. Faster Whisper returned six real English segments with word timestamps. The first, music-heavy `[0, 90]` sample returned no segments and was not treated as a successful end-to-end run. The configured `small` model was not cached; its initial weight download stalled. Automatic GPU transcription of the later interval exceeded a 60-second client timeout, while CPU/int8 with cached `tiny` completed in 3.7 seconds.
- `/v1/analyze` initially returned HTTP 500 because the installed OpenCV 5.0 module has `VideoCapture` but no `CascadeClassifier`. Face detection is optional; `face_features` now reports `available=false` with a reason when the cascade API or cascade data is unavailable. Repeating the same real request returned seven ranked candidates. All seven had finite, ordered intervals within the 90-second downloaded file, scores in `[0, 100]`, and descending rank order. RAG reported unavailable because `sentence-transformers` is not installed.
- The web worker's existing `toSourceTimestamps`/`toMediaLocalSegments` mapping and `mediaOffsetSeconds` contract adds the 90-second source offset to media-local timestamps; `web/lib/analysis-range.test.ts` passed all eight tests. The selected local candidate `[43.5, 73.5]` therefore maps to original source interval `[133.5, 163.5]`.
- `/v1/render` returned a 30-second MP4, 8,180,871 bytes, 1080×1920. FFprobe confirmed its video stream and duration; `ffmpeg -v error -i <clip> -f null -` decoded it successfully.
- Regression and full-suite verification after the OpenCV fallback: `python -m pytest -q -p no:cacheprovider ai/tests/test_media_intelligence.py` — **3 passed**; `python -m pytest -q -p no:cacheprovider ai/tests` — **188 passed**, one Starlette/httpx deprecation warning. Web offset tests: `npm --workspace web exec -- tsx --test lib/analysis-range.test.ts` — **8 passed**. These commands required execution outside the sandbox because its process/temp-directory restrictions blocked pytest and Node's test runner.
- This verifies URL metadata, bounded AI-service ingestion, real transcription, candidate generation/ranking, range-offset mapping logic, and playable rendering through the AI HTTP API. It does **not** verify web authentication, job enqueue/recovery, PostgreSQL persistence, project refresh, editor saves, or the full web worker: this environment had no `DATABASE_URL`, `AI_SERVICE_URL`, or `AI_SERVICE_SECRET` configured. Candidate quality was not evaluated against human labels. GitHub Actions were not run for this local change.
