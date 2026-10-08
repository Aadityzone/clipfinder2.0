# Clip Finder Build Status

The implementation is intentionally real-only.

## Built
- Authentication, password hashing, signed sessions, ownership checks, login lockout
- PostgreSQL/Prisma persistence
- Upload streaming + FFprobe metadata
- YouTube/Twitch/Kick URL ingestion through yt-dlp
- Google Drive OAuth + authenticated media download
- Durable worker jobs with retries, cancellation, stale-job recovery and delayed jobs
- Whisper transcription with timestamps and word timestamps
- Transcript candidate detection and category filtering
- Audio intelligence: volume, peak and silence intervals
- Visual intelligence: scene-change detection and optional face detection
- Deterministic ranking + optional LLM rescoring
- Overlap deduplication
- Real waveform generation
- Multi-segment editor, trim, split, delete, undo/redo, autosave
- Subject-aware short-form reframing when faces are detected
- SRT captions + persisted caption tracks
- Burned-in captions
- FFmpeg H.264/AAC rendering and loudness normalization
- Local or S3/R2-compatible durable object storage
- MP4 preview/export
- YouTube publishing
- TikTok publishing with chunked upload + async status tracking
- Scheduled publishing + cancellation
- YouTube analytics sync
- Long-form analysis, title, description, chapters and source thumbnail
- Long-form rendering and preview
- Templates CRUD
- Profile surface
- Stripe checkout, customer portal and webhook state synchronization
- CI: Prisma validation, TypeScript, ESLint, Next build, Python compile and AI tests

## Credential-gated
These code paths are implemented but require real provider credentials before activation:
- S3/R2 object storage
- Google Drive OAuth
- Semantic LLM rescoring
- Stripe billing
- YouTube/TikTok publishing

The application must remain honest when these credentials are absent.

## Next advanced expansion
- Speaker diarization
- More robust visual action/gameplay models
- Semantic embeddings/vector search
- Additional publishing providers
- Platform-specific analytics beyond YouTube
- Email verification/password reset delivery
- Distributed worker locking for multi-worker deployments
