# AI Pipeline Status

## Intended path
Authorized source URL or uploaded media → media validation/FFprobe → durable INGEST job → download/storage → TRANSCRIBE job → audio transcription with word timestamps → persisted transcript/segments/words → ANALYZE or LONGFORM_ANALYZE → persisted candidates/clips → workspace → edit → RENDER → stored, validated output → export.

## Stage audit
| Stage | Status | Evidence | Missing proof / risk |
|---|---|---|---|
| Source URL validation | IMPLEMENTED_UNVERIFIED | `web/app/api/projects/route.ts`, `ai/services/download.py` | Host allowlist exists; provider access and terms/rights must be respected. |
| Download / ingestion | IMPLEMENTED_UNVERIFIED | `ai/main.py /v1/ingest`, yt-dlp adapter, worker INGEST | Real download not tested; deployment needs yt-dlp, FFmpeg/FFprobe, writable shared working storage. |
| FFprobe | IMPLEMENTED_UNVERIFIED | `ai/services/media.py`; upload route invokes ffprobe | Corrupt/no-stream media and timeout behavior need tests. |
| Audio extraction | PARTIAL / VERIFY | Transcription adapter receives media path; no separate extraction call was proven in the inspected adapter | Confirm faster-whisper can process configured media formats efficiently; explicit FFmpeg extraction may be needed. |
| Transcription | IMPLEMENTED_UNVERIFIED | `ai/transcribe.py` lazily loads faster-whisper, uses word_timestamps and VAD, filters malformed timestamps, and bounds word/segment times to the reported or derived duration; focused fake-model tests pass. | Actual model download/runtime, language correctness and persisted word alignment are not tested. |
| Transcript persistence | IMPLEMENTED_UNVERIFIED | Worker TRANSCRIBE creates Transcript + TranscriptSegment + TranscriptWord | Live database transaction and duplicate/retry behavior not tested. |
| Candidate generation | PARTIAL | `ai/highlights.py` normalizes transcript intervals and caps expanded candidate windows at the last valid transcript boundary; story optimization reuses the same normalizer. Unit tests cover malformed and bounded timestamps. | Heuristic keyword/linguistic cues are not proof of reliable semantic highlight quality; real media duration and candidate quality remain unverified. |
| Multimodal analysis | PARTIAL | `analyze_media`, semantic/visual/speaker/action modules | Optional dependencies/configuration and per-stage fallback behavior require testing. |
| Event candidate proposals | PARTIAL | `ai/services/event_candidates.py` proposes timestamp-bounded candidates from audio energy, visual change/motion, scene changes, OCR/action cues and optional semantic frame scores; integrates with `POST /v1/analyze` even with no transcript. | Proposals remain heuristic activity signals, not proof of semantic quality; no labelled real-video benchmark yet. |
| LLM scoring | IMPLEMENTED_UNVERIFIED | `ai/services/llm.py` preserves deterministic scores on fallback and records per-candidate applied/skipped/failed diagnostics in `features.llmScoring`; event provenance is included in compact model context. | No live API request was made; provider behavior, timeout characteristics and model ranking quality remain unverified. |
| Deduplication | IMPLEMENTED_UNVERIFIED | `ai/services/dedup.py` ranks by score, rejects invalid intervals, and suppresses high-IoU or substantially overlapping similar-length windows; focused regression tests pass. | The overlap threshold is heuristic and has not been evaluated against a real transcript corpus. |
| Candidate evaluation | METRICS IMPLEMENTED / DATA MISSING | `ai/services/evaluation.py` calculates temporal IoU, precision@k, recall@k, mean best IoU and per-genre/macro recall. Genre-labelled predictions are evaluated only against their own genre. | No curated ground-truth video set or baseline-vs-new-model comparison exists, so these metrics do not establish model quality. |
| Result persistence | IMPLEMENTED_UNVERIFIED | Worker ANALYZE writes Analysis, Highlight and Clip in nested Prisma create | No real job demonstrated. |
| Progress/errors/retry | IMPLEMENTED_UNVERIFIED | Prisma Job plus `web/lib/jobs.ts` and worker | Need verify worker deployment/liveness and UI reflects actual states. |
| Rendering | IMPLEMENTED_UNVERIFIED | `ai/services/render.py`, worker RENDER | Must validate output exists, is non-empty/playable, and timestamps match before READY. |
| Export/download | PARTIAL | Export/render schema and UI exist | Verify complete API/storage-to-browser download path. |

## Current high-risk integration boundary
The web worker calls the Python API using `AI_SERVICE_URL` and optional `AI_SERVICE_SECRET`. The worker also requires the same media path to be visible to the AI service or the configured storage adapter to stage media locally. A healthy web app alone does not prove that the worker process is running.

## Local AI reliability verification (2026-10-12)
- Command: `python -m pytest -q -p no:cacheprovider ai/tests/test_pipeline.py ai/tests/test_advanced_ai.py ai/tests/test_transcription.py ai/tests/test_boundary_optimization.py ai/tests/test_story_intelligence.py ai/tests/test_creator_feedback.py` — exit 0, 24 passed.
- Command: `python -m py_compile ai/transcribe.py ai/highlights.py ai/services/dedup.py ai/services/story_intelligence.py` — exit 0.
- `git diff --check` for the AI files changed in that task — exit 0.
- Tests use fake Whisper/LLM responses and synthetic transcript windows. No Whisper model, external LLM, database, worker, media file, or rendered artifact was exercised. The full AI test suite remains blocked in this Python 3.13 environment because `cv2` is unavailable during collection.

## Multimodal event candidate work (2026-10-12)
- Added `ai/services/event_candidates.py`: proposes bounded candidates from audio-energy windows, sampled visual change/motion, scene changes, on-screen action/OCR cues, and optional semantic frame scores.
- Integrated event candidates into `POST /v1/analyze` after transcript story optimization. Transcript text is attached when it overlaps the event window; empty transcripts remain supported.
- Event provenance is exposed via `features.candidateSource=media_events`, `eventTypes`, and `eventEvidenceScore`. The LLM compact payload receives event evidence and is explicitly told not to treat loudness/motion alone as proof of quality.
- Improved event feature aggregation so modalities do not overwrite one another; candidates preserve mean/peak audio and visual signals, scene counts, gameplay ratio, OCR text and action labels for downstream preference/ranking logic.
- Added `ai/services/temporal_ranking.py` and integrated it into `/v1/analyze` after LLM/speaker scoring and before creator preferences. The deterministic baseline records available story/transcript/multimodal signals, rewards independent modality agreement modestly, does not penalize absent audio/transcript, and preserves its diagnostics in `features.temporalRanking`.
- Added focused tests for audio-only, visual/on-screen, bounded short-media windows, absent data, category non-fabrication, empty-transcript route behavior, preservation of multimodal evidence, and temporal ranking determinism/modality availability.
- Added dependency-free temporal IoU, precision@k, recall@k, and per-genre/macro recall metrics. Genre-labelled predictions are isolated from other genres to avoid evaluation leakage.
- Also fixed four existing JSX apostrophe lint errors in calendar, favorites, long-form, and templates pages so CI can proceed past the previously failing lint step.
- Change under review: [PR #18](https://github.com/Aadityzone/clipfinder2.0/pull/18). Latest GitHub Actions run is queued; no pass is claimed.
- Limits: no live video, external model, database, worker, or rendered export has been exercised by this patch. A curated labelled cross-genre benchmark is still needed before judging ranking quality.

## Acceptance test
On a legal, accessible test video:
1. Create project; assert exactly one durable initial job exists.
2. Observe worker claim and state transitions with increasing progress.
3. Confirm media metadata is persisted.
4. Confirm transcript text and timestamped segments/words persist.
5. Confirm non-empty ranked candidates have bounded, valid start/end times.
6. Confirm clips/highlights persist and appear in the authenticated workspace.
7. Render at least one clip; verify actual output file exists and can be decoded/played.
8. Confirm job terminal state, error semantics, usage increment and downloadable export.


## Labelled benchmark runner (2026-10-12)
- Added `ai/services/benchmark.py`, a CLI that validates a versioned manifest of human-curated source-video labels, evaluates original candidate order and deterministic reranking, and emits JSON metrics.
- Metrics are calculated independently per source video before averaging by genre; timestamps from different videos are never compared. The runner rejects duplicate IDs, invalid intervals, missing labels, and unsupported manifest versions rather than silently skipping bad data.
- Added `ai/tests/test_benchmark.py` for manifest validation and per-video/per-genre aggregation.
- Added `docs/project-tracker/AI_BENCHMARKING.md` with the schema, command, and methodology.
- Latest GitHub Actions run for PR #18 head `d5f9ec6` completed successfully: Python and web jobs both succeeded. This is CI evidence only; it is not a real-video end-to-end result.
- Still no curated label dataset checked into the repository. Benchmark runner correctness is testable, but ranking quality is not established until real labelled videos are supplied.


## Media-analysis reliability hardening (2026-10-12)
- Fixed `audio_features()` to always return the same `(summary, windows)` tuple contract, including missing files. Previously the missing-file branch returned a dict and could break unpacking in `analyze_media()`.
- Added subprocess timeouts and independent fallbacks for FFmpeg audio summary, scene-change analysis, and auxiliary visual/on-screen/face stages. A failed optional media stage now returns explicit unavailable metadata and should not discard other available signals.
- Bounded audio probing with FFprobe/FFmpeg timeouts. A failed individual audio sample preserves its timestamp interval but uses null dB values and zero energy rather than fabricated loudness.
- Added regression tests for missing files, FFmpeg/FFprobe timeouts, probe parsing, partial-stage failure, and correct peak aggregation.
- CI for this reliability patch is running; no pass is claimed until the latest head completes. Real media performance and deployment behavior remain unverified.


## Render and real-video smoke hardening (2026-10-12)
- Added a 300-second timeout to each FFmpeg render/concat/caption subprocess and to thumbnail generation. Timeout exceptions propagate into the existing job failure/retry path rather than leaving a child process unbounded.
- Render output validation now requires a non-empty artifact, finite positive duration, finite positive numeric dimensions, and duration within tolerance of the requested edit.
- Added endpoint tests for invalid source metadata, invalid segments, missing artifacts, malformed output metadata, and FFprobe/FFmpeg timeouts.
- Added `ai/scripts/smoke_real_video.py`, an opt-in real integration smoke test for authorized media. It calls ingestion → transcription → multimodal analysis → rendering and reports source metadata, transcript/candidate counts, and output size/duration/resolution. It does not mock AI calls when invoked; unit tests mock only the HTTP orchestration.
- Added tests for the smoke runner's endpoint order and fail-closed behavior when analysis returns no candidates.
- Latest fully green CI head before the smoke runner was `11da6b4`: Python and web jobs passed. The smoke-runner commits are currently under fresh CI and must be rechecked.
- Real source download, live model execution, Prisma-backed worker transitions, and authenticated web export remain unverified until the smoke script is run against configured services and a permitted source URL.
