# Actual Architecture (Source Audit)

## Components
- **Web:** Next.js App Router + TypeScript under `web/`; browser calls Next.js routes.
- **Database:** PostgreSQL accessed through Prisma 7 with generated client under `web/generated/prisma`; schema at `prisma/schema.prisma`.
- **Persistent job queue:** Prisma `Job` rows; `web/lib/jobs.ts` claims runnable jobs, retries with backoff, and recovers stale active jobs.
- **Worker:** `web/worker.ts`, launched by the web workspace script `npm --workspace web run worker`. It polls once per second and calls the Python service over HTTP.
- **AI/media service:** FastAPI at `ai/main.py`; endpoints include health, ingest, probe, thumbnail, transcribe, analyze, long-form, render, and capabilities.
- **Storage:** `web/lib/storage.ts` supports local storage or S3-compatible object storage; environment must be consistent across web/worker/AI media staging.
- **CI:** `.github/workflows/ci.yml` includes web validation/build and Python compile/test jobs.

## Job flow observed
1. `POST /api/projects` validates a supported URL, creates Source and Project, and creates an `INGEST` job in a DB transaction.
2. Worker claims job and invokes `POST /v1/ingest`.
3. Worker persists MediaAsset, then atomically finishes INGEST and queues TRANSCRIBE.
4. Worker calls `POST /v1/transcribe`, persists Transcript, segments and words, then queues ANALYZE or LONGFORM_ANALYZE.
5. Worker calls `POST /v1/analyze` and persists Analysis, Highlight and Clip rows.
6. Rendering uses `POST /v1/render`; worker stores media and updates render/clip state.

## Critical runtime dependencies
- PostgreSQL via `DATABASE_URL`.
- Python packages from `ai/requirements.txt`.
- System binaries: FFmpeg, FFprobe, yt-dlp; optional Tesseract and model libraries.
- AI service URL/secret: `AI_SERVICE_URL`, `AI_SERVICE_SECRET`.
- Optional LLM rescoring: `OPENAI_API_KEY`, optionally `OPENAI_BASE_URL`, `OPENAI_MODEL`.
- Storage configuration: local root or S3-compatible `STORAGE_PROVIDER`, `S3_BUCKET`, `S3_REGION`, `S3_ENDPOINT`, credentials as applicable.
- Worker must run as its own long-lived process; a running Next.js web server does not automatically prove the polling worker is alive.

## Integration caveats
- Health route `web/app/api/health/route.ts` checks DB, AI health and storage, but inspected code does not check worker liveness.
- Source ingestion uses yt-dlp. Availability and permitted access differ by provider; do not promise every URL can be processed.
- Upload route persists media and enqueues TRANSCRIBE; validate cleanup/error paths and shared storage behavior.
- No production environment values are documented here; variable names only.
