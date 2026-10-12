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
| LLM scoring | IMPLEMENTED_UNVERIFIED | `ai/services/llm.py` preserves deterministic scores on fallback and records per-candidate applied/skipped/failed diagnostics in `features.llmScoring`; mocked tests cover missing key, request/malformed response, and invalid model rows. | No live API request was made; provider behavior, timeout characteristics and model ranking quality remain unverified. |
| Deduplication | IMPLEMENTED_UNVERIFIED | `ai/services/dedup.py` ranks by score, rejects invalid intervals, and suppresses high-IoU or substantially overlapping similar-length windows; focused regression tests pass. | The overlap threshold is heuristic and has not been evaluated against a real transcript corpus. |
| Result persistence | IMPLEMENTED_UNVERIFIED | Worker ANALYZE writes Analysis, Highlight and Clip in nested Prisma create | No real job demonstrated. |
| Progress/errors/retry | IMPLEMENTED_UNVERIFIED | Prisma Job plus `web/lib/jobs.ts` and worker | Need verify worker deployment/liveness and UI reflects actual states. |
| Rendering | IMPLEMENTED_UNVERIFIED | `ai/services/render.py`, worker RENDER | Must validate output exists, is non-empty/playable, and timestamps match before READY. |
| Export/download | PARTIAL | Export/render schema and UI exist | Verify complete API/storage-to-browser download path. |

## Current high-risk integration boundary
The web worker calls the Python API using `AI_SERVICE_URL` and optional `AI_SERVICE_SECRET`. The worker also requires the same media path to be visible to the AI service or the configured storage adapter to stage media locally. A healthy web app alone does not prove that the worker process is running.

## Local AI reliability verification (2026-10-12)
- Command: `python -m pytest -q -p no:cacheprovider ai/tests/test_pipeline.py ai/tests/test_advanced_ai.py ai/tests/test_transcription.py ai/tests/test_boundary_optimization.py ai/tests/test_story_intelligence.py ai/tests/test_creator_feedback.py` — exit 0, 24 passed.
- Command: `python -m py_compile ai/transcribe.py ai/highlights.py ai/services/dedup.py ai/services/story_intelligence.py` — exit 0.
- `git diff --check` for the AI files changed in this task — exit 0.
- Tests use fake Whisper/LLM responses and synthetic transcript windows. No Whisper model, external LLM, database, worker, media file, or rendered artifact was exercised. The full AI test suite remains blocked in this Python 3.13 environment because `cv2` is unavailable during collection.

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


## Multimodal event candidate work (2026-10-12)

- Added `ai/services/event_candidates.py`: proposes timestamp-bounded candidates from audio-energy windows, sampled visual change/motion, scene changes, on-screen action/OCR cues, and optional semantic frame scores. It can propose candidates when transcript segments are empty or sparse.
- Integrated event candidates into `POST /v1/analyze` after transcript story optimization so event windows keep their own timestamps. Existing deduplication remains the overlap gate.
- Exposes candidate provenance through `features.candidateSource=media_events`, `eventTypes`, and `eventEvidenceScore`. The LLM compact payload now receives these features and has explicit instructions not to treat loudness/motion alone as proof of clip quality.
- Added focused tests in `ai/tests/test_event_candidates.py` for audio-only and visual/on-screen signals, short media bounds, absent data, and semantic-category non-fabrication.
- Change under review: [PR #18](https://github.com/Aadityzone/clipfinder2.0/pull/18). The latest GitHub Actions run is pending; no pass is claimed.
- Limits: event signals are candidate proposals, not semantic understanding. Current audio-energy, motion, scene and OCR heuristics need validation against labelled cross-genre videos. No live video or end-to-end persisted/exported clip has been tested by this patch.
