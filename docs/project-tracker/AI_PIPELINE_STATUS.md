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
| Transcription | IMPLEMENTED_UNVERIFIED | `ai/transcribe.py` uses faster-whisper, word_timestamps and VAD | Actual model download/runtime and language correctness not tested. |
| Transcript persistence | IMPLEMENTED_UNVERIFIED | Worker TRANSCRIBE creates Transcript + TranscriptSegment + TranscriptWord | Live database transaction and duplicate/retry behavior not tested. |
| Candidate generation | PARTIAL | `ai/highlights.py`, `ai/main.py /v1/analyze` | Heuristic keyword/linguistic cues are not proof of reliable semantic highlight quality. |
| Multimodal analysis | PARTIAL | `analyze_media`, semantic/visual/speaker/action modules | Optional dependencies/configuration and per-stage fallback behavior require testing. |
| LLM scoring | IMPLEMENTED_UNVERIFIED | `ai/services/llm.py`; optional OPENAI_API_KEY | API call is optional; exception handling falls back silently. Need observable signal when rescoring is skipped/failed. |
| Deduplication | IMPLEMENTED_UNVERIFIED | `ai/services/dedup.py` overlap-IoU filter | Candidate generation regression tests need to be run on current code. |
| Result persistence | IMPLEMENTED_UNVERIFIED | Worker ANALYZE writes Analysis, Highlight and Clip in nested Prisma create | No real job demonstrated. |
| Progress/errors/retry | IMPLEMENTED_UNVERIFIED | Prisma Job plus `web/lib/jobs.ts` and worker | Need verify worker deployment/liveness and UI reflects actual states. |
| Rendering | IMPLEMENTED_UNVERIFIED | `ai/services/render.py`, worker RENDER | Must validate output exists, is non-empty/playable, and timestamps match before READY. |
| Export/download | PARTIAL | Export/render schema and UI exist | Verify complete API/storage-to-browser download path. |

## Current high-risk integration boundary
The web worker calls the Python API using `AI_SERVICE_URL` and optional `AI_SERVICE_SECRET`. The worker also requires the same media path to be visible to the AI service or the configured storage adapter to stage media locally. A healthy web app alone does not prove that the worker process is running.

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
