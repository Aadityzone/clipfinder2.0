# Feature Inventory

Statuses reflect repository inspection only unless a test/result is explicitly recorded.

| Feature | Status | Main files / evidence | Next verification |
|---|---|---|---|
| Authentication / user ownership | IMPLEMENTED_UNVERIFIED | `web/lib/auth.ts`, authenticated API routes | Test auth, cross-user access, session expiry. |
| Project creation | IMPLEMENTED_UNVERIFIED | `web/app/api/projects/route.ts` creates project/source/INGEST job transactionally | Test valid/invalid URLs and job creation. |
| URL ingestion | IMPLEMENTED_UNVERIFIED | `web/worker.ts`, `ai/main.py`, `ai/services/download.py` | Real authorized test URL; verify worker and shared storage. |
| Direct upload | PARTIAL | `web/app/api/projects/[id]/upload/route.ts` writes file, probes it, persists source/asset/job | Verify cleanup and validation failures; ensure media storage is shared with worker/AI. |
| Durable jobs / retries | IMPLEMENTED_UNVERIFIED | `web/lib/jobs.ts`, `web/worker.ts`, Prisma Job | Test claim concurrency, stale recovery, retries, cancellation. |
| Whisper transcription | IMPLEMENTED_UNVERIFIED | `ai/transcribe.py`, `ai/schemas.py` | Run on test media; verify language, timestamps, persistence. |
| Highlight candidate generation | PARTIAL | `ai/highlights.py`, `ai/main.py` | Test categories, candidate count, timestamp bounds, overlap dedup. |
| LLM re-scoring | IMPLEMENTED_UNVERIFIED | `ai/services/llm.py`, `ai/main.py` | Test with configured key and with key absent; malformed output handling. |
| Visual/audio analysis | PARTIAL | `ai/services/media_intelligence.py`, `visual_intelligence.py`, related services | Inventory each optional model and verify behavior when dependency absent. |
| Long-form analysis | IMPLEMENTED_UNVERIFIED | `ai/longform.py`, worker LONGFORM_ANALYZE | Test actual transcript to story/chapters persistence. |
| Clip editing | IMPLEMENTED_UNVERIFIED | `web/app/project/[id]/Editor.tsx`, `web/app/api/clips/[id]/edit/route.ts` persist bounded, ordered source-time segments; trim controls now preserve adjacent-segment boundaries | DB save/reload and browser preview/render timestamp accuracy remain unverified. |
| Rendering / captions | IMPLEMENTED_UNVERIFIED | `ai/main.py`, `ai/services/render.py`, worker RENDER; route validates source ranges and ffprobes output before success; SRT export uses valid line breaks and cue times | A synthetic one-segment FFmpeg render was ffprobed successfully; multi-segment/caption cleanup and worker READY integration remain unverified. |
| Exports | PARTIAL | `web/app/api/clips/[id]/export/route.ts` verifies storage object size/type before creating export; edit saves stale existing render/export records | Verify authenticated storage round-trip and downloadable range responses against a real rendered artifact. |
| Usage tracking | PARTIAL | `web/worker.ts` increments analyzed minutes/renders; Usage model | Audit all job paths, plan caps, free trial abuse protection and monthly reset. |
| Stripe billing | PARTIAL | Stripe dependency, Subscription model | Verify checkout/webhooks/entitlements; do not assume connected from dependency alone. |
| Storage abstraction | IMPLEMENTED_UNVERIFIED | `web/lib/storage.ts` local/S3 helpers | Run health and upload/read/delete round-trip in each deployment mode. |
| Health checks | PARTIAL | `web/app/api/health/route.ts` checks DB, AI health and storage | Does not report web-worker liveness in inspected route. |
| Account action controls | IMPLEMENTED_UNVERIFIED | `web/app/usage/BillingActions.tsx` uses billing checkout/portal routes; `web/app/calendar/CancelButton.tsx` uses scheduled-post cancellation; `web/app/analytics/SyncButton.tsx` uses analytics sync | Verify authenticated provider-backed success and failure states in a browser; endpoint behavior remains unverified end to end. |
| Deployment / observability | PARTIAL | `.github/workflows/ci.yml`, npm scripts | Confirm worker and AI service deploy/run as separate processes with shared storage. |
