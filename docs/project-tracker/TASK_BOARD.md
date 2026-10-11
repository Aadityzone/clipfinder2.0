# Task Board

Priorities: P0 blocks trustworthy processing; P1 reliability/quality; P2 product readiness. Status is current as of source audit.

| ID | Priority | Owner | Task | Dependencies | Acceptance criteria | Status |
|---|---|---|---|---|---|---|
| CF-001 | P0 | Lead/QA | Establish runnable baseline for web + Python tests | Access to repo runtime | Record exact test/typecheck/lint/build results; distinguish blocked external services | NOT_STARTED |
| CF-002 | P0 | Backend/Deploy | Verify worker process runs in deployed/local environment | CF-001 | Create test job and observe worker claim/state transitions; add worker liveness visibility | NOT_STARTED |
| CF-003 | P0 | AI/Backend | Run authorized real video end-to-end through ingest/transcribe/analyze | CF-002, configured dependencies | Persisted transcript + nonempty valid candidates displayed in workspace | NOT_STARTED |
| CF-004 | P0 | QA/AI | Re-run candidate overlap and LLM timestamp/index regression tests | CF-001 | Tests pass; regression tests cover bounded timestamps and overlap collapse | NOT_STARTED |
| CF-005 | P1 | AI | Make optional LLM fallback observable and validate model output | CF-001 | Missing key/timeout/malformed response produces explicit diagnostics without fabricated output | NOT_STARTED |
| CF-006 | P1 | Rendering | Verify render output before marking READY | CF-003 | File exists, non-empty, ffprobe/decode validation passes; otherwise FAILED | NOT_STARTED |
| CF-007 | P1 | Backend | Add worker health/heartbeat and operational diagnostics | CF-002 | Health/status distinguishes API, DB, storage and worker | NOT_STARTED |
| CF-008 | P1 | Backend/QA | Audit usage quotas, trial limits, duplicate-job protection | CF-003 | Server-enforced monthly source-hour quota, atomic reservation, 80% warning, hard cap | NOT_STARTED |
| CF-009 | P1 | Storage | Test local and S3 storage round trips and cleanup | CF-001 | Upload/read/delete tests pass; failed jobs clean temporary files safely | NOT_STARTED |
| CF-010 | P2 | Product | Verify subscription checkout/webhooks/entitlements | CF-008 | Paid plan entitlements are server-side and tested against Stripe events | NOT_STARTED |
| CF-011 | P2 | QA | Full pipeline integration fixture and failure matrix | CF-003, CF-006 | Invalid URL, corrupt media, no audio, provider failure, cancellation and retries tested | NOT_STARTED |

## Execution order
Start with CF-001 and CF-002. In parallel where genuine agents are available, CF-004 can run independently. Do not mark a task complete until evidence is appended to TEST_AND_FAILURE_LOG.md.
