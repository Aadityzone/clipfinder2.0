# AI Engineering Handoff — Clip Finder 2.0

Last updated: 2026-10-16
Repository: https://github.com/Aadityzone/clipfinder2.0
Working branch: `build/universal-genre-foundation`
Branch HEAD when this handoff was written: `bb9bc7578f072ff1babdcb809b302cd26539f76d`
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
