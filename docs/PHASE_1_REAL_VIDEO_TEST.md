# Phase 1: Real-video acceptance test

Use this runbook to verify the whole product path against real media. A successful Next.js build or unit-test suite is not acceptance.

## Test source

Twitch VOD: https://www.twitch.tv/videos/2889984350

Only run the test if the VOD is publicly accessible and you have permission to process it. Twitch availability, access restrictions, and provider changes can prevent ingestion even when the URL format is valid.

## Required services

- PostgreSQL configured through `DATABASE_URL`
- Python AI service with the packages in `ai/requirements.txt`
- `ffmpeg`, `ffprobe`, and `yt-dlp` installed and available on the AI service PATH
- A working Whisper model configuration; the first transcription may download model files
- The Next.js web app and its background worker
- A shared `MEDIA_STORAGE_ROOT` mounted at the same absolute path for the web worker and AI service when using local storage. If the services run in separate containers, mount the same volume or configure compatible object storage; a path from one container is not automatically readable in another.
- `AI_SERVICE_URL` and matching `AI_SERVICE_SECRET` values in the web and AI service environments

## Run

1. Apply the Prisma schema to the configured development database (this repo currently relies on schema push rather than a checked-in migration history):

   \`\`\`bash
   npx prisma db push --schema prisma/schema.prisma
   npm run prisma:generate
   \`\`\`
2. Start the AI service from the repository root:

   ```bash
   uvicorn ai.main:app --host 0.0.0.0 --port 8000
   ```

3. Start the web app:

   ```bash
   npm run dev
   ```

4. Start the background worker in another terminal:

   ```bash
   npm --workspace web run worker
   ```

5. Sign in, create a project, paste the test URL, confirm you have the rights to process the source, and submit it.
6. Wait for the actual ingestion, transcription, and analysis jobs to finish. Confirm that transcript segments and ranked candidates are persisted in PostgreSQL after refreshing the page.
7. Open a candidate, change its in/out points or aspect ratio, save the edit, render it, download the export, and play the MP4 locally.

## Acceptance checklist

- [ ] The URL downloads a complete media file; FFprobe reports a nonzero duration and video dimensions.
- [ ] Whisper produces a non-empty transcript with timestamped segments.
- [ ] Candidate start/end times are finite, within source duration, and ordered sensibly.
- [ ] The analysis, highlights, clips, transcript, and media metadata persist in PostgreSQL after a page refresh and service restart.
- [ ] A saved candidate opens in the editor and edited segment boundaries persist.
- [ ] Render status remains queued/processing until the output exists; the downloaded MP4 plays and has the expected duration/aspect ratio/captions.
- [ ] An invalid or unavailable URL produces a useful error rather than a false success.
- [ ] A failed job can be retried; automatic retries are bounded.
- [ ] Cancelling a queued job prevents the next pipeline stage from being enqueued. Active downloads/renders may finish their current external process before the next cancellation checkpoint.
- [ ] Restarting the worker recovers stale jobs without duplicating transcripts, candidate clips, or completed renders.

## Important failure interpretation

- If ingestion fails, inspect the AI service error for yt-dlp/provider access and FFmpeg availability.
- If the web worker says the media path is outside the shared storage root, align the web and AI service volume mounts or configure shared object storage.
- If transcription fails, check model download/cache access and available CPU/RAM.
- If rendering fails, keep the job error and AI service logs; do not mark the render READY manually.
- Never count a build, a mocked unit test, or a generated placeholder as a successful end-to-end run.
